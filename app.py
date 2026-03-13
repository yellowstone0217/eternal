# app.py（完整修复版 + 隐藏卡支持）
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room
import json
import random
import copy
import os
import time
import threading
import uuid
import auth
import shop
import spells
#import camellia
import new_1_spells
import starter_cards
import redeem
#import veteran_simple
import functools

#import monkey_patch_tank

app = Flask(__name__)
app.secret_key = 'my-secret-key-123456'   # 使用固定密钥

# 初始化 SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# 配置
DECK_SIZE = 40

# 加载卡牌数据
with open('cards.json', 'r', encoding='utf-8') as f:
    CARDS_DATA = json.load(f)
CARDS_MAP = {c['name']: c for c in CARDS_DATA}

# ========== 隐藏卡过滤辅助函数 ==========
def is_card_visible(card):
    """判断卡牌是否可见（非隐藏）"""
    return not card.get('hidden', False)

def filter_visible_cards(card_map=None):
    """返回可见卡牌的映射（默认过滤全局CARDS_MAP）"""
    if card_map is None:
        card_map = CARDS_MAP
    return {name: card for name, card in card_map.items() if is_card_visible(card)}

# 游戏状态存储
games = {}

# 内存存储挑战
challenges = {}
challenges_lock = threading.Lock()

class Game:
    """双人对战游戏类（支持法术音效和随从部署动画）"""
    
    @staticmethod
    def _clean_username(username):
        if not isinstance(username, str):
            return username
        import re, unicodedata
        cleaned = re.sub(r'[\u0000-\u001F\u007F-\u009F\u200B-\u200D\uFEFF\u202A-\u202E]', '', username)
        cleaned = cleaned.strip()
        cleaned = unicodedata.normalize('NFC', cleaned)
        return cleaned

    def __init__(self, game_id, player1, player2, deck1, deck2, cards_map, spells_module):
        self.game_id = game_id
        self.player1 = self._clean_username(player1)
        self.player2 = self._clean_username(player2)
        print(f"[Game] 初始化: player1='{self.player1}', player2='{self.player2}'")
        self.cards_map = cards_map
        self.spells = spells_module

        # 牌库
        self.player_deck = []
        self.enemy_deck = []

        for name in deck1:
            if name in self.cards_map:
                card = self.cards_map[name]
                if card.get('hidden', False):
                    continue
                self.player_deck.append(copy.deepcopy(card))
        for name in deck2:
            if name in self.cards_map:
                card = self.cards_map[name]
                if card.get('hidden', False):
                    continue
                self.enemy_deck.append(copy.deepcopy(card))

        # 牌库为空时填充默认卡牌（只使用可见卡）
        if not self.player_deck:
            from starter_cards import STARTER_CARDS
            for card_name in STARTER_CARDS:
                if card_name in self.cards_map and not self.cards_map[card_name].get('hidden', False):
                    self.player_deck.append(copy.deepcopy(self.cards_map[card_name]))
                    break
            else:
                visible = {n: c for n, c in self.cards_map.items() if not c.get('hidden', False)}
                if visible:
                    self.player_deck.append(copy.deepcopy(next(iter(visible.values()))))

        if not self.enemy_deck:
            from starter_cards import STARTER_CARDS
            for card_name in STARTER_CARDS:
                if card_name in self.cards_map and not self.cards_map[card_name].get('hidden', False):
                    self.enemy_deck.append(copy.deepcopy(self.cards_map[card_name]))
                    break
            else:
                visible = {n: c for n, c in self.cards_map.items() if not c.get('hidden', False)}
                if visible:
                    self.enemy_deck.append(copy.deepcopy(next(iter(visible.values()))))

        random.shuffle(self.player_deck)
        random.shuffle(self.enemy_deck)

        # 手牌和战场
        self.player_hand = []
        self.player_board = []
        self.enemy_hand = []
        self.enemy_board = []
        self.player_health = 30
        self.enemy_health = 30

        # ===== 指挥槽管理（上限24）=====
        self.player_commander_slot = 1      # 玩家1当前指挥槽
        self.enemy_commander_slot = 1       # 玩家2当前指挥槽
        self.player_max_commander_slot = 1  # 玩家1最大指挥槽
        self.enemy_max_commander_slot = 1   # 玩家2最大指挥槽

        # ===== 战争债券延迟抽牌标记 =====
        self.delayed_draw = {'player': 0, 'enemy': 0}
        print(f"[Game] 初始化 delayed_draw: {self.delayed_draw}")

        # 回合相关
        self.current_player = self.player1
        self.round_count = 1
        self.MAX_HAND_SIZE = 5

        # 游戏状态
        self.game_over = False
        self.winner = None
        self.message = ""
        self.pending_spell = None
        
        # ===== 动画相关属性 =====
        # 法术动画
        self.spell_for_opponent = None      # 要发给对方的法术（用于翻面动画）
        self.sound_for_opponent = None       # 存储音效（用于双方播放）
        self.sound_sent_to_caster = False    # 音效是否已发送给施法者
        self.sound_sent_to_opponent = False  # 音效是否已发送给对手
        
        # ===== 随从部署动画 =====
        self.minion_deployed = None          # 新部署的随从信息
        self.deploy_sent_to_owner = False    # 是否已发送给部署者
        self.deploy_sent_to_opponent = False # 是否已发送给对手

        # AI相关
        self.ai_player = None    # AI玩家实例
        self.ai_side = None      # AI控制的阵营: 'player' 或 'enemy'

        # 初始抽牌
        self.draw_card(2, is_player=True)
        self.draw_card(2, is_player=False)

    # ---------- AI相关方法 ----------
    def set_ai(self, ai_player, ai_side):
        """设置AI玩家"""
        self.ai_player = ai_player
        self.ai_side = ai_side
        print(f"[Game] AI已设置: 阵营={ai_side}")
        
    def is_ai_turn(self):
        """检查当前是否是AI的回合"""
        if not self.ai_player or self.game_over:
            return False
            
        if self.ai_side == 'player' and self.current_player == self.player1:
            return True
        elif self.ai_side == 'enemy' and self.current_player == self.player2:
            return True
        return False
        
    def trigger_ai_turn(self):
        """触发AI执行回合"""
        if self.is_ai_turn() and self.ai_player:
            print(f"[Game] 触发AI回合: {self.ai_side}")
            # 在新线程中执行AI回合，避免阻塞
            def run_ai():
                import time
                time.sleep(0.5)  # 给前端一点时间更新
                self.ai_player.take_turn()
            
            thread = threading.Thread(target=run_ai)
            thread.daemon = True
            thread.start()
            return True
        return False

    # ---------- 辅助方法 ----------
    def _is_current_player(self, username):
        cleaned = self._clean_username(username)
        return cleaned == self.current_player

    def _set_message(self, msg):
        self.message = msg

    def _get_player_hand(self, username):
        cleaned = self._clean_username(username)
        if cleaned == self.player1:
            return self.player_hand
        elif cleaned == self.player2:
            return self.enemy_hand
        return None

    def _get_player_board(self, username):
        cleaned = self._clean_username(username)
        if cleaned == self.player1:
            return self.player_board
        elif cleaned == self.player2:
            return self.enemy_board
        return None

    def _get_enemy_board(self, username):
        cleaned = self._clean_username(username)
        if cleaned == self.player1:
            return self.enemy_board
        elif cleaned == self.player2:
            return self.player_board
        return None

    def _get_current_commander_slot(self, username):
        """获取指定玩家的当前指挥槽"""
        cleaned = self._clean_username(username)
        if cleaned == self.player1:
            return self.player_commander_slot
        elif cleaned == self.player2:
            return self.enemy_commander_slot
        return 0

    def _get_current_max_commander_slot(self, username):
        """获取指定玩家的最大指挥槽"""
        cleaned = self._clean_username(username)
        if cleaned == self.player1:
            return self.player_max_commander_slot
        elif cleaned == self.player2:
            return self.enemy_max_commander_slot
        return 0

    def _use_commander_slot(self, username, cost):
        """消耗指定玩家的指挥槽"""
        cleaned = self._clean_username(username)
        if cleaned == self.player1:
            self.player_commander_slot -= cost
        elif cleaned == self.player2:
            self.enemy_commander_slot -= cost

    # ---------- 核心游戏逻辑 ----------
    def draw_card(self, count=1, is_player=True):
        hand = self.player_hand if is_player else self.enemy_hand
        deck = self.player_deck if is_player else self.enemy_deck
        drawn = 0
        for _ in range(count):
            if len(hand) >= self.MAX_HAND_SIZE:
                if not deck:
                    if is_player:
                        self.player_health = max(0, self.player_health - 1)
                        self._set_message("牌库已空，你受到1点疲劳伤害！")
                    else:
                        self.enemy_health = max(0, self.enemy_health - 1)
                        self._set_message("敌方牌库已空，敌方受到1点疲劳伤害！")
                    continue
                deck.pop()
                self._set_message("手牌已满，抽到的牌被弃掉")
                continue
            if not deck:
                if is_player:
                    self.player_health = max(0, self.player_health - 1)
                    self._set_message("牌库已空，你受到1点疲劳伤害！")
                else:
                    self.enemy_health = max(0, self.enemy_health - 1)
                    self._set_message("敌方牌库已空，敌方受到1点疲劳伤害！")
                continue
            card = copy.deepcopy(deck.pop())
            card.setdefault('health', 1)
            card.setdefault('attack', 0)
            card.setdefault('cost', 1)
            card.setdefault('effect', [])

            if 'effect' in card and any(e.startswith('抽到时：') for e in card['effect']):
                self.spells.apply_draw_effect(self, card, 'player' if is_player else 'enemy')
                drawn += 1
                self._set_message(f"抽到 {card.get('name')}，触发抽取效果！")
            else:
                hand.append(card)
                drawn += 1
        return drawn

    def _can_play_card(self, board):
        if len(board) >= 4:
            return False, "场上最多只能有4个随从"
        return True, ""

    def _has_taunt(self, board):
        for card in board:
            if 'effect' in card and '守护' in card['effect']:
                return True
        return False

    def play_card(self, username, card_index):
        """打出卡牌（支持法术和随从，包含部署动画）"""
        cleaned = self._clean_username(username)
        hand = self._get_player_hand(cleaned)
        board = self._get_player_board(cleaned)
        if hand is None or board is None:
            return False, False

        if self.game_over:
            self._set_message("游戏已结束")
            return False, False
        if not self._is_current_player(cleaned):
            self._set_message("现在不是你的回合")
            return False, False
        if card_index < 0 or card_index >= len(hand):
            self._set_message("无效的卡牌索引")
            return False, False

        card = hand[card_index]
        cost = card.get('cost', 1)
        
        # 使用当前玩家的指挥槽进行检查
        current_slot = self._get_current_commander_slot(cleaned)
        if cost > current_slot:
            self._set_message("指挥槽不足")
            return False, False

        # 法术牌处理
        if self.spells.is_spell_card(card):
            target_type = self.spells.get_spell_target_type(card)
            print(f"[play_card] 法术牌: {card.get('name')}, target_type={target_type}, 使用者={username}")

            if target_type == 'none':
                # 消耗指挥槽
                self._use_commander_slot(cleaned, cost)
                hand.pop(card_index)
                caster = 'player' if cleaned == self.player1 else 'enemy'
                self.spells.apply_spell_effect(self, card, caster)
                self._set_message(f"使用技能 {card.get('name')}")

                # 记录法术（用于翻面动画）
                recorded = copy.deepcopy(card)
                recorded['caster'] = caster
                self.spell_for_opponent = recorded
                print(f"[play_card] ★ 已记录法术给对手: {recorded.get('name')} 施法者={caster}")
                
                # 单独记录音效（双方都能听到）
                if 'sound' in card:
                    self.sound_for_opponent = {
                        'path': card['sound'],
                        'caster': caster,
                        'card_name': card.get('name'),
                        'id': str(time.time())  # 添加唯一ID防止重复
                    }
                    # 重置发送标记
                    self.sound_sent_to_caster = False
                    self.sound_sent_to_opponent = False
                    print(f"[play_card] ★ 已记录音效: {self.sound_for_opponent}")

                return True, False
            else:
                self.pending_spell = {
                    'card': card,
                    'index': card_index,
                    'target_type': target_type,
                    'caster': username
                }
                self._set_message(f"请选择 {card.get('name')} 的目标")
                return False, True

        # ===== 随从牌处理（带部署动画）=====
        ok, msg = self._can_play_card(board)
        if not ok:
            self._set_message(msg)
            return False, False

        # 消耗指挥槽
        self._use_commander_slot(cleaned, cost)
        card = hand.pop(card_index)
        card.setdefault('health', 1)
        card.setdefault('attack', 0)
        card['original_health'] = card['health']
        card['original_attack'] = card['attack']
        card['can_attack'] = ('effect' in card and '闪击' in card['effect'])
        board.append(card)
        
        # ===== 记录随从部署（用于翻面动画）=====
        deploy_info = copy.deepcopy(card)
        deploy_info['deployer'] = 'player' if cleaned == self.player1 else 'enemy'
        deploy_info['position'] = len(board) - 1  # 记录在战场上的位置
        self.minion_deployed = deploy_info
        self.deploy_sent_to_owner = False
        self.deploy_sent_to_opponent = False
        print(f"[play_card] ★ 已记录随从部署: {deploy_info.get('name')} 部署者={deploy_info['deployer']} 位置={deploy_info['position']}")
        
        self._set_message(f"打出随从 {card.get('name')}")
        
        # 音效处理
        if 'sound' in card:
            self.sound_for_opponent = {
                'path': card['sound'],
                'caster': 'player' if cleaned == self.player1 else 'enemy',
                'card_name': card.get('name'),
                'type': 'minion',
                'id': str(time.time())
            }
            self.sound_sent_to_caster = False
            self.sound_sent_to_opponent = False
            print(f"[play_card] ★ 已记录随从音效: {self.sound_for_opponent}")
        
        return True, False

    def play_spell_with_target(self, username, target_index):
        """使用需要目标的法术牌（修复：目标索引自适应 + 消耗战动画）"""
        if not self.pending_spell:
            self._set_message("没有待使用的技能")
            return False
        if self.pending_spell['caster'] != username:
            self._set_message("技能不属于你")
            return False

        spell = self.pending_spell['card']
        card_index = self.pending_spell['index']
        target_type = self.pending_spell['target_type']
        cleaned = self._clean_username(username)
        hand = self._get_player_hand(cleaned)
        caster = 'player' if cleaned == self.player1 else 'enemy'

        cost = spell.get('cost', 1)
        
        # 使用当前玩家的指挥槽进行检查
        current_slot = self._get_current_commander_slot(cleaned)
        if cost > current_slot:
            self._set_message("指挥槽不足")
            self.pending_spell = None
            return False

        # ===== 定义目标变量（用于消耗战动画）=====
        target_unit = None
        owner = None
        target_idx = None

        # 对于需要指向随从的技能
        if target_type == 'minion':
            # 确定目标应该在哪一方
            if caster == 'player':
                # 玩家使用，目标是敌方随从
                enemy_board = self._get_enemy_board(cleaned)
                print(f"[play_spell_with_target] 敌方场上有 {len(enemy_board)} 个随从，目标索引={target_index}")
                
                # 检查敌方场上是否有随从
                if len(enemy_board) == 0:
                    self._set_message("敌方场上没有随从，无法使用此技能")
                    self.pending_spell = None
                    return False
                
                # 检查目标索引是否有效
                if target_index is None or target_index < 0:
                    self._set_message("无效的目标")
                    self.pending_spell = None
                    return False
                
                # 如果目标索引超出范围，可能是因为随从死亡导致的
                if target_index >= len(enemy_board):
                    print(f"[play_spell_with_target] 警告：目标索引 {target_index} 超出范围，敌方场上有 {len(enemy_board)} 个随从")
                    if len(enemy_board) > 0:
                        target_index = len(enemy_board) - 1
                        print(f"[play_spell_with_target] 调整目标索引为最后一个随从: {target_index}")
                    else:
                        self._set_message("目标随从已不存在")
                        self.pending_spell = None
                        return False
                
                # ===== 保存目标信息用于动画 =====
                target_unit = enemy_board[target_index]
                owner = 'enemy'
                target_idx = target_index
                
            else:
                # 敌方使用，目标是玩家随从
                player_board = self._get_player_board(cleaned)
                print(f"[play_spell_with_target] 玩家场上有 {len(player_board)} 个随从，目标索引={target_index}")
                
                # 检查玩家场上是否有随从
                if len(player_board) == 0:
                    self._set_message("你场上没有随从，无法使用此技能")
                    self.pending_spell = None
                    return False
                
                # 检查目标索引是否有效
                if target_index is None or target_index < 0:
                    self._set_message("无效的目标")
                    self.pending_spell = None
                    return False
                
                # 如果目标索引超出范围，可能是因为随从死亡导致的
                if target_index >= len(player_board):
                    print(f"[play_spell_with_target] 警告：目标索引 {target_index} 超出范围，玩家场上有 {len(player_board)} 个随从")
                    if len(player_board) > 0:
                        target_index = len(player_board) - 1
                        print(f"[play_spell_with_target] 调整目标索引为最后一个随从: {target_index}")
                    else:
                        self._set_message("目标随从已不存在")
                        self.pending_spell = None
                        return False
                
                # ===== 保存目标信息用于动画 =====
                target_unit = player_board[target_index]
                owner = 'player'
                target_idx = target_index

        # 消耗指挥槽
        self._use_commander_slot(cleaned, cost)
        
        # 重要：检查卡牌是否还在手牌中（可能被其他效果移除了）
        if card_index >= len(hand) or hand[card_index].get('name') != spell.get('name'):
            print(f"[play_spell_with_target] 警告：卡牌可能已被移除，重新查找卡牌位置")
            # 尝试根据卡牌名称重新查找
            found_index = -1
            for i, c in enumerate(hand):
                if c.get('name') == spell.get('name'):
                    found_index = i
                    break
            if found_index >= 0:
                card_index = found_index
                print(f"[play_spell_with_target] 在索引 {found_index} 重新找到卡牌")
            else:
                self._set_message("卡牌已不存在")
                self.pending_spell = None
                return False
        
        # 移除手牌中的卡牌
        hand.pop(card_index)
        
        # 应用法术效果
        self.spells.apply_spell_effect(self, spell, caster, target_index)
        self._set_message(f"使用技能 {spell.get('name')}")

        # 记录法术（用于翻面动画）
        recorded = copy.deepcopy(spell)
        recorded['caster'] = caster
        self.spell_for_opponent = recorded
        print(f"[play_spell_with_target] ★ 已记录法术给对手: {recorded.get('name')} 施法者={caster}")
        
        # 单独记录音效（双方都能听到）
        if 'sound' in spell:
            self.sound_for_opponent = {
                'path': spell['sound'],
                'caster': caster,
                'card_name': spell.get('name'),
                'id': str(time.time())
            }
            self.sound_sent_to_caster = False
            self.sound_sent_to_opponent = False
            print(f"[play_spell_with_target] ★ 已记录音效: {self.sound_for_opponent}")

        # ===== 消耗战动画 =====
        if spell.get('name') == '消耗战' and target_unit is not None:
            try:
                from app import socketio
                socketio.emit('consume_animation', {
                    'unit': target_unit.get('name', '未知'),
                    'owner': owner,
                    'index': target_idx,
                    'timestamp': time.time()
                }, room=self.game_id)
                print(f"[消耗战] 发送移除动画: {target_unit.get('name')}")
            except Exception as e:
                print(f"[消耗战] 发送动画失败: {e}")

        self.pending_spell = None
        return True

    def attack(self, username, attacker_index, target_index=None):
        cleaned = self._clean_username(username)
        attacker_board = self._get_player_board(cleaned)
        if attacker_board is None:
            return False

        if self.game_over:
            self._set_message("游戏已结束")
            return False
        if not self._is_current_player(cleaned):
            self._set_message("现在不是你的回合")
            return False
        if attacker_index < 0 or attacker_index >= len(attacker_board):
            return False

        attacker = attacker_board[attacker_index]
        if not attacker.get('can_attack'):
            self._set_message("该随从本回合无法攻击")
            return False

        enemy_board = self._get_enemy_board(cleaned)
        is_siege_tank = (attacker.get('name') == '攻城坦克')

        # 激光防御处理函数
        def handle_laser_defense(target_side, target_idx, damage_amount):
            try:
                if target_side == 'player':
                    defenders = self.player_board
                else:
                    defenders = self.enemy_board
                
                laser_indices = [i for i, unit in enumerate(defenders) 
                               if unit.get('name') == '激光防御装置' and unit.get('health', 0) > 0]
                
                if not laser_indices:
                    return target_side, target_idx, damage_amount, False
                
                laser_idx = laser_indices[0]
                laser_unit = defenders[laser_idx]
                
                absorbed = min(damage_amount, laser_unit['health'])
                remaining = damage_amount - absorbed
                
                laser_unit['health'] -= absorbed
                
                if laser_unit['health'] <= 0:
                    defenders.pop(laser_idx)
                
                if remaining > 0:
                    return target_side, target_idx, remaining, True
                else:
                    return None, None, 0, True
                    
            except Exception as e:
                print(f"[激光防御错误] {e}")
                return target_side, target_idx, damage_amount, False

        # ===== 攻击英雄 =====
        if target_index is None:
            if self._has_taunt(enemy_board):
                self._set_message("敌方有守护随从，不能直接攻击英雄")
                return False
                
            damage = 4 if is_siege_tank else attacker['attack']
            
            if cleaned == self.player1:
                target_side = 'enemy'
            else:
                target_side = 'player'
            
            new_side, new_idx, remaining, redirected = handle_laser_defense(target_side, None, damage)
            
            if redirected:
                if remaining == 0:
                    self._set_message("激光防御装置吸收了全部伤害！")
                else:
                    self._set_message(f"激光防御装置吸收了 {damage - remaining} 点伤害")
            
            if remaining > 0:
                if cleaned == self.player1:
                    self.enemy_health -= remaining
                    self.enemy_health = max(0, self.enemy_health)
                else:
                    self.player_health -= remaining
                    self.player_health = max(0, self.player_health)
            
            # ===== 奋战逻辑（攻击英雄）=====
            if attacker.get('name') == '青少年爆发' or ('effect' in attacker and '奋战' in attacker['effect']):
                if 'attacks_this_turn' not in attacker:
                    attacker['attacks_this_turn'] = 0
                attacker['attacks_this_turn'] += 1
                
                if attacker['attacks_this_turn'] >= 2:
                    attacker['can_attack'] = False
                    print(f"  {attacker.get('name')} 已完成两次攻击")
                else:
                    attacker['can_attack'] = True
                    print(f"  {attacker.get('name')} 奋战第一次攻击，还可以再攻击一次")
            else:
                attacker['can_attack'] = False

            # ===== 触发散弹火炮效果（攻击英雄）=====
            try:
                from new_1_spells import trigger_shotgun_effect
                trigger_shotgun_effect(self, attacker, attacker_index, None, 'hero')
            except Exception as e:
                print(f"[散弹火炮] 触发失败: {e}")

            if (cleaned == self.player1 and self.enemy_health <= 0) or \
               (cleaned == self.player2 and self.player_health <= 0):
                self._end_game(cleaned)
            return True

        # ===== 攻击随从 =====
        else:
            if target_index < 0 or target_index >= len(enemy_board):
                return False
                
            target = enemy_board[target_index]
            
            if cleaned == self.player1:
                target_side = 'enemy'
            else:
                target_side = 'player'
            
            attacker_damage = 4 if is_siege_tank else attacker['attack']
            target_damage = target['attack']
            attacker_initial_health = attacker['health']
            target_initial_health = target['health']
            
            new_side, new_idx, remaining, redirected = handle_laser_defense(target_side, target_index, attacker_damage)
            
            if redirected:
                if remaining == 0:
                    self._set_message("激光防御装置吸收了全部伤害！")
                    attacker['health'] -= target_damage
                    attacker['health'] = max(0, attacker['health'])
                else:
                    self._set_message(f"激光防御装置吸收了 {attacker_damage - remaining} 点伤害")
                    target['health'] -= remaining
                    attacker['health'] -= target_damage
                    target['health'] = max(0, target['health'])
                    attacker['health'] = max(0, attacker['health'])
            else:
                target['health'] -= attacker_damage
                attacker['health'] -= target_damage
                target['health'] = max(0, target['health'])
                attacker['health'] = max(0, attacker['health'])

            # 游击队员效果
            if attacker.get('name') == '游击队员':
                if target.get('health', 0) < target_initial_health:
                    self._set_message(f"游击队员与 {target.get('name')} 同归于尽！")
                    print(f"[游击队员] {attacker.get('name')} 与 {target.get('name')} 同归于尽")
                    target['health'] = 0
                    attacker['health'] = 0

            if target.get('name') == '游击队员':
                if attacker.get('health', 0) < attacker_initial_health:
                    self._set_message(f"游击队员与 {attacker.get('name')} 同归于尽！")
                    print(f"[游击队员] {target.get('name')} 与 {attacker.get('name')} 同归于尽")
                    attacker['health'] = 0
                    target['health'] = 0

            # 收缴效果
            if target['health'] <= 0:
                if 'effect' in attacker and '收缴' in attacker['effect']:
                    self._handle_confiscate(attacker, target, cleaned)
                enemy_board[:] = [c for c in enemy_board if c['health'] > 0]
                
            if attacker['health'] <= 0:
                attacker_board[:] = [c for c in attacker_board if c['health'] > 0]

            # ===== 奋战逻辑（攻击随从）=====
            if attacker.get('name') == '青少年爆发' or ('effect' in attacker and '奋战' in attacker['effect']):
                if 'attacks_this_turn' not in attacker:
                    attacker['attacks_this_turn'] = 0
                attacker['attacks_this_turn'] += 1
                
                if attacker['attacks_this_turn'] >= 2:
                    attacker['can_attack'] = False
                    print(f"  {attacker.get('name')} 已完成两次攻击")
                else:
                    attacker['can_attack'] = True
                    print(f"  {attacker.get('name')} 奋战第一次攻击，还可以再攻击一次")
            else:
                attacker['can_attack'] = False

            # ===== 触发散弹火炮效果（攻击随从）=====
            try:
                from new_1_spells import trigger_shotgun_effect
                trigger_shotgun_effect(self, attacker, attacker_index, target_index, 'minion')
            except Exception as e:
                print(f"[散弹火炮] 触发失败: {e}")

            # 检查游戏结束
            if (cleaned == self.player1 and self.enemy_health <= 0) or \
               (cleaned == self.player2 and self.player_health <= 0):
                self._end_game(cleaned)
            elif (cleaned == self.player1 and self.player_health <= 0) or \
                 (cleaned == self.player2 and self.enemy_health <= 0):
                winner = self.player2 if cleaned == self.player1 else self.player1
                self._end_game(winner)

            return True
            
    def _handle_confiscate(self, attacker, target, username):
        hand = self._get_player_hand(username)
        if len(hand) >= self.MAX_HAND_SIZE:
            self._set_message("手牌已满，收缴的卡牌被弃掉")
            return
        confiscated = copy.deepcopy(target)
        confiscated['attack'] = 1
        confiscated['health'] = 1
        confiscated['original_health'] = 1
        confiscated['original_attack'] = 1
        confiscated['can_attack'] = ('effect' in confiscated and '闪击' in confiscated['effect'])
        hand.append(confiscated)
        self._set_message(f"收缴到 {confiscated.get('name')}（变为1/1）")

    def end_turn(self, username):
        cleaned = self._clean_username(username)
        if self.game_over:
            return False
        if not self._is_current_player(cleaned):
            self._set_message("现在不是你的回合")
            return False

        self.pending_spell = None

        # 切换当前玩家
        if self.current_player == self.player1:
            self.current_player = self.player2
        else:
            self.current_player = self.player1

        self._start_turn()
        
        # 检查新回合是否是AI的回合
        self.trigger_ai_turn()
        
        return True

    def _start_turn(self):
        """开始新回合：只增加当前回合玩家的指挥槽（上限24）"""
        self.round_count += 1
        
        print(f"\n========== 开始新回合 ==========")
        print(f"当前玩家: {self.current_player}")
        print(f"延迟抽牌状态: {self.delayed_draw}")
        
        # ===== 处理消耗战返场 =====
        if hasattr(self, 'removed_units') and self.removed_units:
            returned_units = []
            remaining_units = []
            
            for unit in self.removed_units:
                # 检查是否到了返场时间（下个其所有者回合）
                owner = unit.get('original_owner')
                if (owner == 'player' and self.current_player == self.player1) or \
                   (owner == 'enemy' and self.current_player == self.player2):
                    # 返场
                    returned_units.append(unit)
                else:
                    remaining_units.append(unit)
            
            # 返场单位加入战场
            for unit in returned_units:
                owner = unit.get('original_owner')
                if owner == 'player':
                    if len(self.player_board) < 4:
                        # 尽量放回原位，如果被占就放最后
                        original_index = unit.get('original_index', 0)
                        if original_index <= len(self.player_board):
                            self.player_board.insert(original_index, unit)
                        else:
                            self.player_board.append(unit)
                        print(f"  {unit.get('name')} 返场到玩家战场")
                        
                        # ===== 修复：使用导入的全局 socketio =====
                        try:
                            from flask_socketio import SocketIO
                            from app import socketio as global_socketio
                            global_socketio.emit('return_animation', {
                                'owner': 'player',
                                'card': {
                                    'name': unit.get('name'),
                                    'cost': unit.get('cost', 0),
                                    'attack': unit.get('attack', 0),
                                    'health': unit.get('health', 1),
                                    'image': unit.get('image', ''),
                                    'effect': unit.get('effect', [])
                                },
                                'position': original_index
                            }, room=self.game_id)
                        except Exception as e:
                            print(f"发送返场动画失败: {e}")
                    else:
                        print(f"  玩家战场已满，{unit.get('name')} 无法返场")
                else:
                    if len(self.enemy_board) < 4:
                        original_index = unit.get('original_index', 0)
                        if original_index <= len(self.enemy_board):
                            self.enemy_board.insert(original_index, unit)
                        else:
                            self.enemy_board.append(unit)
                        print(f"  {unit.get('name')} 返场到敌方战场")
                        
                        # ===== 修复：使用导入的全局 socketio =====
                        try:
                            from flask_socketio import SocketIO
                            from app import socketio as global_socketio
                            global_socketio.emit('return_animation', {
                                'owner': 'enemy',
                                'card': {
                                    'name': unit.get('name'),
                                    'cost': unit.get('cost', 0),
                                    'attack': unit.get('attack', 0),
                                    'health': unit.get('health', 1),
                                    'image': unit.get('image', ''),
                                    'effect': unit.get('effect', [])
                                },
                                'position': original_index
                            }, room=self.game_id)
                        except Exception as e:
                            print(f"发送返场动画失败: {e}")
                    else:
                        print(f"  敌方战场已满，{unit.get('name')} 无法返场")
            
            self.removed_units = remaining_units
            
            if returned_units:
                self._set_message(f"消耗战：{len(returned_units)}个单位返场")
        
        # ===== 只增加当前回合玩家的指挥槽（上限24）=====
        if self.current_player == self.player1:
            # 玩家1的回合
            if self.player_max_commander_slot < 12:
                self.player_max_commander_slot += 1
            self.player_commander_slot = self.player_max_commander_slot
            
            # 重置攻击状态
            for card in self.player_board:
                card['can_attack'] = True
            
            # ===== 检查是否有延迟抽牌（战争债券效果）=====
            if self.delayed_draw.get('player', 0) > 0:
                extra_draws = self.delayed_draw['player']
                print(f"[_start_turn] ✓ 检测到玩家延迟抽牌: {extra_draws} 张")
                self.draw_card(extra_draws, is_player=True)
                self.delayed_draw['player'] = 0
                self._set_message(f"战争债券效果触发，额外抽 {extra_draws} 张牌")
            
            # 抽牌
            self.draw_card(1, is_player=True)
            
            self._set_message(f"回合开始，你的费用 {self.player_commander_slot}/{self.player_max_commander_slot}")
            print(f"玩家回合开始，费用: {self.player_commander_slot}/{self.player_max_commander_slot}")
            
        else:
            # 玩家2的回合
            if self.enemy_max_commander_slot < 12:
                self.enemy_max_commander_slot += 1
            self.enemy_commander_slot = self.enemy_max_commander_slot
            
            # 重置攻击状态
            for card in self.enemy_board:
                card['can_attack'] = True
            
            # ===== 检查是否有延迟抽牌（战争债券效果）=====
            if self.delayed_draw.get('enemy', 0) > 0:
                extra_draws = self.delayed_draw['enemy']
                print(f"[_start_turn] ✓ 检测到敌方延迟抽牌: {extra_draws} 张")
                self.draw_card(extra_draws, is_player=False)
                self.delayed_draw['enemy'] = 0
                self._set_message(f"敌方战争债券效果触发，额外抽 {extra_draws} 张牌")
            
            # 抽牌
            self.draw_card(1, is_player=False)
            
            self._set_message(f"回合开始，敌方费用 {self.enemy_commander_slot}/{self.enemy_max_commander_slot}")
            print(f"敌方回合开始，费用: {self.enemy_commander_slot}/{self.enemy_max_commander_slot}")
        
        # ===== 清除移除动画记录 =====
        if hasattr(self, 'removal_animations'):
            # 只保留2秒内的动画（用于前端）
            current_time = time.time()
            self.removal_animations = [a for a in self.removal_animations 
                                      if current_time - a.get('timestamp', 0) < 2.0]
        
        print("========== 回合开始完成 ==========\n")

    def surrender(self, username):
        cleaned = self._clean_username(username)
        if self.game_over:
            return False
        winner = self.player2 if cleaned == self.player1 else self.player1
        self._end_game(winner)
        self._set_message(f"{username} 投降，{winner} 获胜")
        return True

    def _end_game(self, winner):
        self.game_over = True
        self.winner = winner
        def cleanup():
            time.sleep(5)
            if self.game_id in games:
                del games[self.game_id]
                print(f"[Game] 游戏 {self.game_id} 已从内存删除")
        thread = threading.Thread(target=cleanup)
        thread.daemon = True
        thread.start()
    
    def get_state_for(self, username):
        """获取指定玩家的游戏状态视图"""
        cleaned = self._clean_username(username)
        is_player1 = (cleaned == self.player1)
        print(f"[get_state_for] 请求者='{cleaned}', is_player1={is_player1}, player1='{self.player1}', player2='{self.player2}'")

        # ===== 根据玩家返回对应的指挥槽 =====
        state = {
            'player_hand': copy.deepcopy(self.player_hand if is_player1 else self.enemy_hand),
            'player_board': copy.deepcopy(self.player_board if is_player1 else self.enemy_board),
            'enemy_hand_count': len(self.enemy_hand if is_player1 else self.player_hand),
            'enemy_board': copy.deepcopy(self.enemy_board if is_player1 else self.player_board),
            'player_health': self.player_health if is_player1 else self.enemy_health,
            'enemy_health': self.enemy_health if is_player1 else self.player_health,
            'current_player': self.current_player,
            'game_over': self.game_over,
            'winner': self.winner,
            'commander_slot': self.player_commander_slot if is_player1 else self.enemy_commander_slot,
            'max_commander_slot': self.player_max_commander_slot if is_player1 else self.enemy_max_commander_slot,
            'enemy_commander_slot': self.enemy_commander_slot if is_player1 else self.player_commander_slot,
            'enemy_max_commander_slot': self.enemy_max_commander_slot if is_player1 else self.player_max_commander_slot,
            'round_count': self.round_count,
            'player_deck_count': len(self.player_deck if is_player1 else self.enemy_deck),
            'enemy_deck_count': len(self.enemy_deck if is_player1 else self.player_deck),
            'message': self.message,
            'pending_spell': self.pending_spell is not None,
            
            # ===== 动画相关字段 =====
            'enemy_spell_used': None,        # 敌方使用的法术
            'enemy_minion_deployed': None,    # 敌方部署的随从
            'enemy_sound': None,               # 敌方音效
            'my_sound': None,                  # 己方言效
            'special_action': None             # 特殊动作（如发现）
        }

        # ===== 处理法术动画 =====
        if self.spell_for_opponent:
            if (self.spell_for_opponent.get('caster') == 'player' and not is_player1) or \
               (self.spell_for_opponent.get('caster') == 'enemy' and is_player1):
                state['enemy_spell_used'] = copy.deepcopy(self.spell_for_opponent)
                self.spell_for_opponent = None

        # ===== 处理随从部署动画 =====
        if self.minion_deployed:
            deployer = self.minion_deployed.get('deployer')
            
            # 如果是敌方部署的，显示给己方
            if (deployer == 'player' and not is_player1) or (deployer == 'enemy' and is_player1):
                # 这是敌方部署的随从，应该显示给当前玩家
                if not self.deploy_sent_to_opponent:
                    state['enemy_minion_deployed'] = copy.deepcopy(self.minion_deployed)
                    self.deploy_sent_to_opponent = True
                    print(f"[get_state_for] 发送敌方部署信息: {self.minion_deployed.get('name')}")
            
            # 如果是己方部署的，不给己方看（己方直接看到随从上场）
            # 当双方都收到后，清除部署信息
            if self.deploy_sent_to_owner and self.deploy_sent_to_opponent:
                self.minion_deployed = None
                self.deploy_sent_to_owner = False
                self.deploy_sent_to_opponent = False
                print(f"[get_state_for] 部署信息已发送完毕，清除")

        # ===== 处理音效 =====
        if self.sound_for_opponent:
            is_caster_self = (self.sound_for_opponent.get('caster') == 'player' and is_player1) or \
                             (self.sound_for_opponent.get('caster') == 'enemy' and not is_player1)
            is_opponent = (self.sound_for_opponent.get('caster') == 'player' and not is_player1) or \
                          (self.sound_for_opponent.get('caster') == 'enemy' and is_player1)
            sound_id = self.sound_for_opponent.get('id', '')
            
            if is_caster_self and not self.sound_sent_to_caster:
                state['my_sound'] = {'path': self.sound_for_opponent['path'], 'id': sound_id}
                self.sound_sent_to_caster = True
            
            if is_opponent and not self.sound_sent_to_opponent:
                state['enemy_sound'] = {'path': self.sound_for_opponent['path'], 'id': sound_id}
                self.sound_sent_to_opponent = True
            
            if self.sound_sent_to_caster and self.sound_sent_to_opponent:
                self.sound_for_opponent = None
        
        # 检查是否有特殊动作（如发现）
        if hasattr(self, 'special_actions') and cleaned in self.special_actions:
            action = self.special_actions[cleaned]
            if action.get('active', False):
                state['special_action'] = action
                print(f"[get_state_for] 返回special_action for {cleaned}: {action}")
        
        self.message = ""
        return state

# ========== 路由 ==========

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    game_id = session.get('game_id')
    if not game_id or game_id not in games:
        return redirect(url_for('main'))
    return render_template('index.html', game_id=game_id)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        success, msg = auth.login(username, password)
        if success:
            session['user'] = username
            return redirect(url_for('main'))
        else:
            return render_template('login.html', error=msg)
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        success, msg = auth.register(username, password)
        if success:
            starter_cards.give_starter_cards(username)
            session['user'] = username
            return redirect(url_for('main'))
        else:
            return render_template('register.html', error=msg)
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('game_id', None)
    return redirect(url_for('login'))

@app.route('/main')
def main():
    if 'user' not in session:
        return redirect(url_for('login'))
    users = auth.load_users()
    user = users.get(session['user'], {})
    decks = user.get('decks', [])
    gold = user.get('gold', 0)          # 每次从数据库读取最新金币
    return render_template('main.html', 
                           username=session['user'], 
                           user_decks=decks,
                           gold=gold)

@app.route('/deck')
def deck():
    if 'user' not in session:
        return redirect(url_for('login'))
    users = auth.load_users()
    user = users.get(session['user'], {})
    cards = user.get('cards', {})
    decks = user.get('decks', [])
    # 只传递可见卡牌给模板
    visible_cards_map = filter_visible_cards(CARDS_MAP)
    return render_template('deck.html', 
                           cards=cards, 
                           card_details=visible_cards_map,   # 修改：使用过滤后的可见卡
                           deck_size=DECK_SIZE,
                           decks=decks)

@app.route('/save_deck', methods=['POST'])
def save_deck():
    if 'user' not in session:
        return jsonify({'error': '未登录'}), 401

    data = request.json
    deck_name = data.get('name')
    deck_cards = data.get('cards', [])

    # 基础验证
    if not deck_name:
        return jsonify({'error': '卡组名称不能为空'}), 400
    if len(deck_cards) > DECK_SIZE:
        return jsonify({'error': f'卡组不能超过 {DECK_SIZE} 张'}), 400

    # 统计每张卡的出现次数
    counts = {}
    for card_name in deck_cards:
        if card_name not in CARDS_MAP:
            return jsonify({'error': f'卡牌 {card_name} 不存在'}), 400
        # 新增：检查卡牌是否隐藏
        if CARDS_MAP[card_name].get('hidden', False):
            return jsonify({'error': f'卡牌 {card_name} 已被隐藏，无法使用'}), 400
        counts[card_name] = counts.get(card_name, 0) + 1

    # 检查每张卡的数量是否超过品质限制
    for card_name, count in counts.items():
        quality = CARDS_MAP[card_name].get('quality', '普通')
        limit = {'普通': 4, '限定': 3, '特殊': 2, '精英': 1}.get(quality, 4)
        if count > limit:
            return jsonify({'error': f'{card_name} 最多携带 {limit} 张'}), 400

    # 检查用户是否拥有这些卡牌（但不扣除）
    users = auth.load_users()
    user = users[session['user']]
    for card_name, count in counts.items():
        if user['cards'].get(card_name, 0) < count:
            return jsonify({'error': f'你没有足够的 {card_name}'}), 400

    # 保存卡组（直接替换或添加，不修改卡牌库存）
    found = False
    for i, deck in enumerate(user['decks']):
        if deck['name'] == deck_name:
            user['decks'][i]['cards'] = deck_cards
            found = True
            break
    if not found:
        user['decks'].append({'name': deck_name, 'cards': deck_cards})

    auth.save_users(users)
    return jsonify({'success': True, 'updated_cards': user['cards']})

@app.route('/get_deck/<deck_name>')
def get_deck(deck_name):
    if 'user' not in session:
        return jsonify({'error': '未登录'}), 401
    users = auth.load_users()
    user = users.get(session['user'], {})
    for deck in user.get('decks', []):
        if deck['name'] == deck_name:
            # 过滤掉隐藏卡（确保返回的卡组不含隐藏卡）
            filtered_cards = [c for c in deck['cards'] if c in CARDS_MAP and not CARDS_MAP[c].get('hidden', False)]
            return jsonify({'success': True, 'cards': filtered_cards})
    return jsonify({'error': '卡组不存在'}), 404

@app.route('/delete_deck', methods=['POST'])
def delete_deck():
    if 'user' not in session:
        return jsonify({'error': '未登录'}), 401
    data = request.json
    deck_name = data.get('deck_name')
    users = auth.load_users()
    user = users.get(session['user'], {})
    user['decks'] = [d for d in user.get('decks', []) if d['name'] != deck_name]
    auth.save_users(users)
    return jsonify({'success': True})

@app.route('/shop')
def shop_page():
    if 'user' not in session:
        return redirect(url_for('login'))
    free_card_name = shop.refresh_shop(session['user'])
    free_card = CARDS_MAP.get(free_card_name) if free_card_name else None
    users = auth.load_users()
    user = users.get(session['user'], {})
    last_refresh = user.get('shop', {}).get('last_refresh', 0)
    gold = user.get('gold', 0)   # 新增
    return render_template('shop.html', free_card=free_card, last_refresh=last_refresh, gold=gold)
    
    
@app.route('/purchase_random_pack', methods=['POST'])
def purchase_random_pack():
    if 'user' not in session:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    username = session['user']
    success, message, reward = shop.purchase_random_pack(username)
    if success:
        return jsonify({'success': True, 'message': message, 'reward': reward})
    else:
        return jsonify({'success': False, 'message': message})
        
        

@app.route('/claim_free_card', methods=['POST'])
def claim_free_card():
    if 'user' not in session:
        return jsonify({'error': '未登录'}), 401
    success = shop.claim_free_card(session['user'])
    return jsonify({'success': success})

# ========== WebSocket 事件处理 ==========
@socketio.on('authenticate')
def handle_authenticate(data):
    username = data.get('username')
    if username and username == session.get('user'):
        join_room(username)
        pending = []
        with challenges_lock:
            for cid, chal in challenges.items():
                if chal['opponent'] == username and chal['status'] == 'pending':
                    pending.append({
                        'challenge_id': cid,
                        'challenger': chal['challenger']
                    })
        if pending:
            emit('initial_invites', pending)

@socketio.on('invite')
def handle_invite(data):
    username = session.get('user')
    if not username:
        emit('error', {'msg': '未登录'})
        return

    opponent = data.get('opponent')
    deck_name = data.get('deck_name')
    
    if not opponent or not deck_name:
        emit('error', {'msg': '参数不完整'})
        return

    # ===== 检查是否挑战AI =====
    if opponent == "AI":
        print(f"🤖 玩家 {username} 挑战AI")
        
        # 获取玩家卡组
        users = auth.load_users()
        user = users.get(username, {})
        player_deck = None
        for d in user.get('decks', []):
            if d['name'] == deck_name:
                player_deck = d['cards']
                break
                
        if not player_deck:
            emit('error', {'msg': '卡组不存在'})
            return
        
        # 导入AI相关模块
        from ai_decks import ALL_AI_DECKS
        import ai_player
        import random
        
        # 获取AI难度，默认为普通AI
        ai_difficulty = data.get('ai_difficulty', '普通AI')
        if ai_difficulty not in ALL_AI_DECKS:
            ai_difficulty = '普通AI'
            
        ai_deck = ALL_AI_DECKS[ai_difficulty]["cards"]
        
        # 随机决定谁先手
        if random.choice([True, False]):
            player1 = username
            player2 = "AI"
            deck1 = player_deck
            deck2 = ai_deck
            ai_side = 'enemy'  # AI是敌方
        else:
            player1 = "AI"
            player2 = username
            deck1 = ai_deck
            deck2 = player_deck
            ai_side = 'player'  # AI是玩家方
        
        game_id = f"ai_game_{username}_{int(time.time())}"
        
        print(f"[AI对战] 创建游戏: {game_id}")
        print(f"[AI对战] 玩家: {username}, AI难度: {ai_difficulty}, AI阵营: {ai_side}")
        
        # 创建游戏实例
        game = Game(game_id, player1, player2, deck1, deck2, CARDS_MAP, spells)
        games[game_id] = game
        
        # 创建AI玩家
        ai = ai_player.AIPlayer(ai_difficulty)
        ai.set_game(game, ai_side)
        
        # 将AI设置到游戏中
        game.set_ai(ai, ai_side)
        
        # 存储AI信息（使用app实例存储）
        if not hasattr(app, 'ai_games'):
            app.ai_games = {}
        app.ai_games[game_id] = {
            'ai': ai,
            'player_name': username,
            'ai_difficulty': ai_difficulty,
            'ai_side': ai_side,
            'game': game
        }
        
        # 立即通知玩家游戏创建成功
        emit('ai_game_created', {
            'game_id': game_id,
            'ai_difficulty': ai_difficulty,
            'message': f'AI对战创建成功（难度：{ai_difficulty}）',
            'success': True
        })
        
        # 如果是AI先手，立即触发AI回合
        if player1 == "AI":
            print(f"[AI对战] AI先手，立即触发AI回合")
            # 延迟一点触发，让前端有时间加载
            def ai_first_move():
                import time
                time.sleep(2.0)  # 给玩家一点时间加载页面
                with app.app_context():
                    try:
                        # 发送AI思考提示
                        socketio.emit('ai_thinking', {
                            'game_id': game_id,
                            'message': 'AI正在思考...'
                        }, room=username)
                        
                        # 获取游戏实例
                        game = games.get(game_id)
                        if game:
                            print(f"[AI对战] AI开始思考...")
                            # 直接触发AI回合
                            game.trigger_ai_turn()
                    except Exception as e:
                        print(f"[AI对战] 错误: {e}")
                        socketio.emit('ai_error', {
                            'game_id': game_id,
                            'message': f'AI出错: {str(e)}'
                        }, room=username)
            
            thread = threading.Thread(target=ai_first_move)
            thread.daemon = True
            thread.start()
        else:
            # 如果是玩家先手，也要确保AI会在自己的回合触发
            print(f"[AI对战] 玩家先手，等待玩家结束回合")
        
        return
    
    # ===== 原有的玩家对战逻辑 =====
    users = auth.load_users()
    if opponent not in users:
        emit('error', {'msg': '对手不存在'})
        return
    if opponent == username:
        emit('error', {'msg': '不能挑战自己'})
        return

    user = users.get(username, {})
    challenger_deck = None
    for d in user.get('decks', []):
        if d['name'] == deck_name:
            challenger_deck = d['cards']
            break
    if not challenger_deck:
        emit('error', {'msg': '卡组不存在'})
        return

    opponent_user = users.get(opponent, {})
    if not opponent_user.get('decks'):
        emit('error', {'msg': '对手还没有卡组'})
        return

    challenge_id = str(uuid.uuid4())[:8]
    with challenges_lock:
        for cid, chal in list(challenges.items()):
            if chal['challenger'] == username and chal['opponent'] == opponent and chal['status'] == 'pending':
                del challenges[cid]
        challenges[challenge_id] = {
            'challenger': username,
            'opponent': opponent,
            'challenger_deck': challenger_deck,
            'status': 'pending',
            'game_id': None,
            'created_at': time.time()
        }

    socketio.emit('new_invite', {
        'challenge_id': challenge_id,
        'challenger': username,
        'deck_name': deck_name
    }, room=opponent)

    emit('invite_sent', {'challenge_id': challenge_id, 'success': True})

@socketio.on('accept_invite')
def handle_accept_invite(data):
    username = session.get('user')
    if not username:
        emit('error', {'msg': '未登录'})
        return

    challenge_id = data.get('challenge_id')
    deck_name = data.get('deck_name')
    if not challenge_id or not deck_name:
        emit('error', {'msg': '参数不完整'})
        return

    with challenges_lock:
        challenge = challenges.get(challenge_id)
        if not challenge:
            emit('error', {'msg': '挑战不存在'})
            return
        if challenge['opponent'] != username:
            emit('error', {'msg': '无权限'})
            return
        if challenge['status'] != 'pending':
            emit('error', {'msg': '挑战已失效'})
            return

        users = auth.load_users()
        user = users.get(username, {})
        opponent_deck = None
        for d in user.get('decks', []):
            if d['name'] == deck_name:
                opponent_deck = d['cards']
                break
        if not opponent_deck:
            emit('error', {'msg': '卡组不存在'})
            return

        game_id = f"game_{challenge_id}_{int(time.time())}"
        if random.choice([True, False]):
            player1 = challenge['challenger']
            player2 = username
            deck1 = challenge['challenger_deck']
            deck2 = opponent_deck
        else:
            player1 = username
            player2 = challenge['challenger']
            deck1 = opponent_deck
            deck2 = challenge['challenger_deck']

        game = Game(game_id, player1, player2, deck1, deck2, CARDS_MAP, spells)
        games[game_id] = game
        challenge['status'] = 'accepted'
        challenge['game_id'] = game_id

        socketio.emit('invite_accepted', {
            'challenge_id': challenge_id,
            'game_id': game_id
        }, room=challenge['challenger'])

        emit('invite_accepted', {'game_id': game_id})

@socketio.on('reject_invite')
def handle_reject_invite(data):
    username = session.get('user')
    if not username:
        emit('error', {'msg': '未登录'})
        return
    challenge_id = data.get('challenge_id')
    with challenges_lock:
        challenge = challenges.get(challenge_id)
        if not challenge or challenge['opponent'] != username or challenge['status'] != 'pending':
            emit('error', {'msg': '无效的挑战'})
            return
        challenge['status'] = 'rejected'
        socketio.emit('invite_rejected', {'challenge_id': challenge_id}, room=challenge['challenger'])
        emit('invite_rejected', {'challenge_id': challenge_id})

@socketio.on('cancel_invite')
def handle_cancel_invite(data):
    username = session.get('user')
    if not username:
        emit('error', {'msg': '未登录'})
        return
    challenge_id = data.get('challenge_id')
    with challenges_lock:
        challenge = challenges.get(challenge_id)
        if not challenge or challenge['challenger'] != username or challenge['status'] != 'pending':
            emit('error', {'msg': '无效的挑战'})
            return
        challenge['status'] = 'cancelled'
        socketio.emit('invite_cancelled', {'challenge_id': challenge_id}, room=challenge['opponent'])
        emit('invite_cancelled', {'challenge_id': challenge_id})

# ========== 游戏操作 ==========
@app.route('/game_state/<game_id>')
def game_state(game_id):
    if 'user' not in session:
        return jsonify({'error': '未登录'}), 401
    game = games.get(game_id)
    if not game:
        return jsonify({'error': '游戏不存在', 'game_over': True}), 404
    username = session['user']
    if username not in [game.player1, game.player2]:
        return jsonify({'error': '无权访问'}), 403
    state = game.get_state_for(username)
    game.message = ""
    return jsonify(state)

@app.route('/play_card/<game_id>', methods=['POST'])
def play_card(game_id):
    if 'user' not in session:
        return jsonify({'error': '未登录'}), 401
    game = games.get(game_id)
    if not game:
        return jsonify({'error': '游戏不存在'}), 404
    data = request.json
    success, need_target = game.play_card(session['user'], data['card_index'])
    
    response_data = {
        'success': success,
        'need_target': need_target,
        'message': game.message
    }
    print(f"play_card 响应: {response_data}")
    
    return jsonify(response_data)

@app.route('/play_spell_target/<game_id>', methods=['POST'])
def play_spell_target(game_id):
    if 'user' not in session:
        return jsonify({'error': '未登录'}), 401
    game = games.get(game_id)
    if not game:
        return jsonify({'error': '游戏不存在'}), 404
    data = request.json
    success = game.play_spell_with_target(session['user'], data.get('target_index'))
    return jsonify({'success': success})

@app.route('/attack/<game_id>', methods=['POST'])
def attack(game_id):
    if 'user' not in session:
        return jsonify({'error': '未登录'}), 401
    game = games.get(game_id)
    if not game:
        return jsonify({'error': '游戏不存在'}), 404
    data = request.json
    result = game.attack(session['user'], data['attacker_index'], data.get('target_index'))
    
    # 广播攻击动画给房间内的所有玩家
    if result:
        socketio.emit('attack_animation', {
            'attacker_index': data['attacker_index'],
            'target_index': data.get('target_index'),
            'attacker_player': session['user']
        }, room=game_id)
    
    return jsonify({'result': result})

@app.route('/end_turn/<game_id>', methods=['POST'])
def end_turn(game_id):
    if 'user' not in session:
        return jsonify({'error': '未登录'}), 401
    game = games.get(game_id)
    if not game:
        return jsonify({'error': '游戏不存在'}), 404
    success = game.end_turn(session['user'])
    return jsonify({'success': success})

@app.route('/set_game_session/<game_id>', methods=['POST'])
def set_game_session(game_id):
    if 'user' not in session:
        return jsonify({'error': '未登录'}), 401
    game = games.get(game_id)
    if not game:
        return jsonify({'error': '游戏不存在'}), 404
    if session['user'] not in [game.player1, game.player2]:
        return jsonify({'error': '无权访问此游戏'}), 403
    session['game_id'] = game_id
    return jsonify({'success': True})

@app.route('/surrender/<game_id>', methods=['POST'])
def surrender(game_id):
    if 'user' not in session:
        return jsonify({'error': '未登录'}), 401
    game = games.get(game_id)
    if not game:
        return jsonify({'error': '游戏不存在'}), 404
    success = game.surrender(session['user'])
    return jsonify({'success': success, 'winner': game.winner})

@app.route('/current_user', methods=['GET'])
def current_user():
    if 'user' in session:
        return jsonify({'username': session['user']})
    return jsonify({'username': None}), 401

# ... 现有代码 ...

@app.route('/redeem', methods=['POST'])
def redeem_code():
    """兑换码领取接口"""
    if 'user' not in session:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    data = request.json
    code = data.get('code', '').strip()
    if not code:
        return jsonify({'success': False, 'message': '兑换码不能为空'})

    username = session['user']

    # 准备可用卡牌列表：排除精英和隐藏卡
    available_cards = [
        name for name, card in CARDS_MAP.items()
        if card.get('quality') != '精英' and not card.get('hidden', False)
    ]

    success, message, reward = redeem.process_redeem(code, username, available_cards)

    if success:
        return jsonify({
            'success': True,
            'message': message,
            'reward': reward
        })
    else:
        return jsonify({'success': False, 'message': message})
        
# ========== 发现（好人寥寥）相关路由 ==========

@app.route('/discover/<token>')
def discover_page(token):
    """发现页面 - 使用一次性令牌"""
    if 'user' not in session:
        return redirect(url_for('login'))
    
    username = session['user']
    
    # 遍历所有游戏查找匹配的令牌
    game_with_token = None
    game_id = None
    
    for gid, game in games.items():
        if hasattr(game, 'discover_tokens') and token in game.discover_tokens:
            token_data = game.discover_tokens[token]
            if token_data['username'] == username and not token_data.get('used', False):
                game_with_token = game
                game_id = gid
                break
    
    if not game_with_token:
        # 令牌无效或已使用，返回错误页面
        return render_template('error.html', 
                               message='无效的发现链接或链接已过期', 
                               redirect='/main')
    
    # 传递令牌到模板，以便在确认时使用
    return render_template('discover.html', token=token)

@app.route('/discover_cards/<game_id>')
def discover_cards(game_id):
    """获取三张随机精英卡牌"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': '未登录'}), 401
    
    game = games.get(game_id)
    if not game:
        return jsonify({'success': False, 'error': '游戏不存在'}), 404
    
    if session['user'] not in [game.player1, game.player2]:
        return jsonify({'success': False, 'error': '无权访问'}), 403
    
    # 检查是否已经选择过
    discover_key = f"discover_{game_id}_{session['user']}"
    if session.get(discover_key, False):
        return jsonify({'success': False, 'error': '已经选择过卡牌'}), 400
    
    # 从CARDS_MAP中筛选精英品质且非隐藏的卡牌
    elite_cards = [
        card for card in CARDS_DATA 
        if card.get('quality') == '精英' and not card.get('hidden', False)
    ]
    
    if len(elite_cards) < 3:
        # 如果精英卡不足3张，添加一些备选
        fallback_cards = [
            card for card in CARDS_DATA 
            if card.get('quality') in ['特殊', '限定'] and not card.get('hidden', False)
        ]
        import random
        while len(elite_cards) < 3 and fallback_cards:
            card = random.choice(fallback_cards)
            if card not in elite_cards:
                elite_cards.append(card)
    
    # 随机选择3张不同的卡牌
    import random
    selected_cards = random.sample(elite_cards, min(3, len(elite_cards)))
    
    # 返回卡牌信息（不包含敏感字段）
    result_cards = []
    for card in selected_cards:
        card_info = {
            'name': card['name'],
            'quality': card.get('quality', '精英'),
            'cost': card.get('cost', 0),
            'image': card.get('image', ''),
            'description': card.get('description', ''),
            'effect': card.get('effect', [])
        }
        if 'attack' in card:
            card_info['attack'] = card['attack']
        if 'health' in card:
            card_info['health'] = card['health']
        result_cards.append(card_info)
    
    return jsonify({'success': True, 'cards': result_cards})

@app.route('/confirm_discover', methods=['POST'])
def confirm_discover():
    """确认选择的发现卡牌"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': '未登录'}), 401
    
    data = request.json
    game_id = data.get('game_id')
    card_name = data.get('card_name')
    
    if not game_id or not card_name:
        return jsonify({'success': False, 'error': '参数不完整'}), 400
    
    game = games.get(game_id)
    if not game:
        return jsonify({'success': False, 'error': '游戏不存在'}), 404
    
    username = session['user']
    if username not in [game.player1, game.player2]:
        return jsonify({'success': False, 'error': '无权访问'}), 403
    
    # 检查是否已经选择过
    discover_key = f"discover_{game_id}_{username}"
    if hasattr(game, discover_key) and getattr(game, discover_key):
        return jsonify({'success': False, 'error': '已经选择过卡牌'}), 400
    
    # 获取卡牌数据
    card_data = CARDS_MAP.get(card_name)
    if not card_data:
        return jsonify({'success': False, 'error': '卡牌不存在'}), 404
    
    # 检查品质是否为精英
    if card_data.get('quality') != '精英':
        return jsonify({'success': False, 'error': '只能选择精英卡牌'}), 400
    
    # 将卡牌加入玩家手牌
    import copy
    new_card = copy.deepcopy(card_data)
    new_card.setdefault('health', 1)
    new_card.setdefault('attack', 0)
    new_card['original_health'] = new_card.get('health', 1)
    new_card['original_attack'] = new_card.get('attack', 0)
    new_card['can_attack'] = ('effect' in new_card and '闪击' in new_card['effect'])
    
    # 确定玩家身份
    if username == game.player1:
        hand = game.player_hand
    else:
        hand = game.enemy_hand
    
    # 检查手牌是否已满
    if len(hand) >= game.MAX_HAND_SIZE:
        return jsonify({'success': False, 'error': '手牌已满，无法获得卡牌'}), 400
    
    # 加入手牌
    hand.append(new_card)
    
    # 标记已选择
    setattr(game, discover_key, True)
    
    # 清除special_actions
    if hasattr(game, 'special_actions') and username in game.special_actions:
        # 标记为失效，而不是删除
        #game.special_actions[username]['active'] = False
        print(f"[confirm_discover] 清除special_action for {username}")
    
    # 记录消息
    game._set_message(f"通过「好人寥寥」获得了 {card_name}")
    
    return jsonify({'success': True, 'message': f'获得 {card_name}'})
    
@app.route('/discover_cards_by_token/<token>')
def discover_cards_by_token(token):
    """通过令牌获取发现卡牌"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': '未登录'}), 401
    
    username = session['user']
    
    # 查找令牌
    game_with_token = None
    game_id = None
    token_data = None
    
    for gid, game in games.items():
        if hasattr(game, 'discover_tokens') and token in game.discover_tokens:
            data = game.discover_tokens[token]
            if data['username'] == username and not data.get('used', False):
                game_with_token = game
                game_id = gid
                token_data = data
                break
    
    if not game_with_token:
        return jsonify({'success': False, 'error': '无效的发现令牌'}), 404
    
    # ✅✅✅ 直接使用存储的卡牌，不重新随机！✅✅✅
    selected_cards = token_data.get('selected_cards', [])
    
    if not selected_cards:
        return jsonify({'success': False, 'error': '卡牌数据丢失'}), 404
    
    result_cards = []
    for card in selected_cards:
        card_info = {
            'name': card['name'],
            'quality': card.get('quality', '精英'),
            'cost': card.get('cost', 0),
            'image': card.get('image', ''),
            'description': card.get('description', ''),
            'effect': card.get('effect', [])
        }
        if 'attack' in card:
            card_info['attack'] = card['attack']
        if 'health' in card:
            card_info['health'] = card['health']
        result_cards.append(card_info)
    
    return jsonify({'success': True, 'cards': result_cards, 'game_id': game_id})

@app.route('/confirm_discover_by_token', methods=['POST'])
def confirm_discover_by_token():
    """通过令牌确认选择的发现卡牌"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': '未登录'}), 401
    
    data = request.json
    token = data.get('token')
    card_name = data.get('card_name')
    
    if not token or not card_name:
        return jsonify({'success': False, 'error': '参数不完整'}), 400
    
    username = session['user']
    
    # 查找令牌
    game_with_token = None
    game_id = None
    token_data = None
    
    for gid, game in games.items():
        if hasattr(game, 'discover_tokens') and token in game.discover_tokens:
            data = game.discover_tokens[token]
            if data['username'] == username and not data.get('used', False):
                game_with_token = game
                game_id = gid
                token_data = data
                break
    
    if not game_with_token:
        return jsonify({'success': False, 'error': '无效的发现令牌'}), 404
    
    game = game_with_token
    
    # 标记令牌为已使用
    game.discover_tokens[token]['used'] = True
    
    # 获取卡牌数据
    card_data = CARDS_MAP.get(card_name)
    if not card_data:
        return jsonify({'success': False, 'error': '卡牌不存在'}), 404
    
    if card_data.get('quality') != '精英':
        return jsonify({'success': False, 'error': '只能选择精英卡牌'}), 400
    
    # 将卡牌加入玩家手牌
    import copy
    new_card = copy.deepcopy(card_data)
    new_card.setdefault('health', 1)
    new_card.setdefault('attack', 0)
    new_card['original_health'] = new_card.get('health', 1)
    new_card['original_attack'] = new_card.get('attack', 0)
    new_card['can_attack'] = ('effect' in new_card and '闪击' in new_card['effect'])
    
    if username == game.player1:
        hand = game.player_hand
    else:
        hand = game.enemy_hand
    
    if len(hand) >= game.MAX_HAND_SIZE:
        return jsonify({'success': False, 'error': '手牌已满，无法获得卡牌'}), 400
    
    hand.append(new_card)
    
    # 清除special_actions
    if hasattr(game, 'special_actions') and username in game.special_actions:
        del game.special_actions[username]
    
    game._set_message(f"通过「好人寥寥」获得了 {card_name}")
    
    return jsonify({'success': True, 'message': f'获得 {card_name}'})
       

if __name__ == '__main__':
# 最后导入特殊卡牌补丁（确保 Game 类已定义）
    socketio.run(app, debug=True, host='0.0.0.0', port=5220)