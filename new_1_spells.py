# new_1_spells.py - 包含黎明终焉、前线与家乡、B25米切尔、伟大的虫族母王效果
"""
这个文件使用猴子补丁为游戏添加以下特殊卡牌效果：
- 黎明终焉：从卡组顶召唤单位复制
- 前线与家乡：卡组所有单位费用-1，特定单位+1/+1
- B25米切尔：受到攻击力增益时，额外+2（直到回合结束）
- 伟大的虫族母王：抽1张牌，对所有敌方单位造成2点伤害
使用方法：在 app.py 中导入此文件即可
"""

import copy
import random
import spells
import types
import functools
import traceback
import sys
import time
#import veteran_simple

# ========== 保存原始函数引用 ==========
_original_apply_spell_effect = spells.apply_spell_effect
_original_get_spell_target_type = spells.get_spell_target_type
_original_game_start_turn = None
_original_attack = None
_original_play_card = None
_GAME_CLASS_PATCHED = False

# ========== 辅助函数：攻击力增益处理（含B25触发） ==========
def apply_attack_bonus(game, unit, amount, source=None):
    """
    给指定单位增加攻击力，若单位是 B25米切尔 且 amount>0，则额外增加2（临时）
    所有增加都记录到 unit['temp_attack'] 中，以便回合结束时清除
    """
    try:
        if amount == 0:
            return
        if unit is None:
            print("[错误] apply_attack_bonus 收到 None unit")
            return

        # 初始化临时攻击力记录
        if 'temp_attack' not in unit:
            unit['temp_attack'] = 0

        old_attack = unit.get('attack', 0)
        unit['attack'] = old_attack + amount
        unit['temp_attack'] += amount
        print(f"[攻击增益] {unit.get('name')} 攻击力 +{amount} → {unit['attack']}")

        # B25米切尔额外触发（通过名称检测）
        if unit.get('name') == 'B25米切尔' and amount > 0:
            extra = 2
            unit['attack'] += extra
            unit['temp_attack'] += extra
            print(f"  → B25米切尔额外 +2，攻击力现在 {unit['attack']}")
    except Exception as e:
        print(f"[apply_attack_bonus 异常] {e}")
        traceback.print_exc()

def clear_temp_attack_bonuses(game):
    """清除场上所有单位的临时攻击力加成（在回合开始时调用）"""
    try:
        for board in [game.player_board, game.enemy_board]:
            for unit in board:
                if 'temp_attack' in unit and unit['temp_attack'] != 0:
                    old_attack = unit.get('attack', 0)
                    unit['attack'] = old_attack - unit['temp_attack']
                    print(f"[回合清除] {unit.get('name')} 临时攻击力 -{unit['temp_attack']} → {unit['attack']}")
                    unit['temp_attack'] = 0
    except Exception as e:
        print(f"[clear_temp_attack_bonuses 异常] {e}")
        traceback.print_exc()

# ========== 处理伟大的虫族母王攻击效果（已废弃，因为改为抽牌AOE） ==========
def handle_great_queen_attack_effect(game, attacker, cleaned):
    """已废弃：伟大的虫族母王效果已改为抽牌AOE"""
    return False

# ========== 补丁：Game.play_card（在单位上场时传递卡组效果） ==========
def patched_play_card(game, username, card_index):
    """补丁版的 play_card 方法，在单位上场时检查并传递虫族母王效果"""
    try:
        cleaned = game._clean_username(username)
        hand = game._get_player_hand(cleaned)
        board = game._get_player_board(cleaned)
        
        if hand is None or board is None:
            return False, False

        if game.game_over:
            game._set_message("游戏已结束")
            return False, False
        if not game._is_current_player(cleaned):
            game._set_message("现在不是你的回合")
            return False, False
        if card_index < 0 or card_index >= len(hand):
            game._set_message("无效的卡牌索引")
            return False, False

        card = hand[card_index]
        cost = card.get('cost', 1)
        
        current_slot = game._get_current_commander_slot(cleaned)
        if cost > current_slot:
            game._set_message("指挥槽不足")
            return False, False

        # 法术牌处理
        if game.spells.is_spell_card(card):
            target_type = game.spells.get_spell_target_type(card)
            print(f"[play_card] 法术牌: {card.get('name')}, target_type={target_type}")

            if target_type == 'none':
                game._use_commander_slot(cleaned, cost)
                hand.pop(card_index)
                caster = 'player' if cleaned == game.player1 else 'enemy'
                game.spells.apply_spell_effect(game, card, caster)
                game._set_message(f"使用技能 {card.get('name')}")

                # 记录法术
                recorded = copy.deepcopy(card)
                recorded['caster'] = caster
                game.spell_for_opponent = recorded
                
                # 记录音效
                if 'sound' in card:
                    game.sound_for_opponent = {
                        'path': card['sound'],
                        'caster': caster,
                        'card_name': card.get('name'),
                        'id': str(time.time())
                    }
                    game.sound_sent_to_caster = False
                    game.sound_sent_to_opponent = False

                return True, False
            else:
                game.pending_spell = {
                    'card': card,
                    'index': card_index,
                    'target_type': target_type,
                    'caster': username
                }
                game._set_message(f"请选择 {card.get('name')} 的目标")
                return False, True

        # 随从牌处理
        ok, msg = game._can_play_card(board)
        if not ok:
            game._set_message(msg)
            return False, False

        # 消耗指挥槽
        game._use_commander_slot(cleaned, cost)
        card = hand.pop(card_index)
        card.setdefault('health', 1)
        card.setdefault('attack', 0)
        card['original_health'] = card['health']
        card['original_attack'] = card['attack']
        card['can_attack'] = ('effect' in card and '闪击' in card['effect'])
        
        board.append(card)

        # ===== 海军牌效果（打出单位时触发）=====
        if 'effect' in card and '海军' in card.get('effect', []):
            print(f"✓ 打出海军单位: {card.get('name')}")
            trigger_navy_effects(game, 'player' if cleaned == game.player1 else 'enemy', card.get('name'))

        game._set_message(f"打出随从 {card.get('name')}")
        
        # 音效处理
        if 'sound' in card:
            game.sound_for_opponent = {
                'path': card['sound'],
                'caster': 'player' if cleaned == game.player1 else 'enemy',
                'card_name': card.get('name'),
                'type': 'minion',
                'id': str(time.time())
            }
            game.sound_sent_to_caster = False
            game.sound_sent_to_opponent = False
        
        return True, False
    except Exception as e:
        print(f"[patched_play_card 异常] {e}")
        traceback.print_exc()
        # 出错时调用原始方法
        global _original_play_card
        if _original_play_card:
            return _original_play_card(game, username, card_index)
        return False, False

# ========== 补丁：Game._start_turn ==========
def patched_game_start_turn(game):
    """在开始新回合前清除临时攻击力，然后执行原逻辑"""
    try:
        clear_temp_attack_bonuses(game)
    except Exception as e:
        print(f"[patched_game_start_turn 清除临时攻击力时出错] {e}")
    
    # 调用原始的 _start_turn
    global _original_game_start_turn
    if _original_game_start_turn is None:
        _original_game_start_turn = game.__class__._start_turn
    _original_game_start_turn(game)

# ========== 补丁：get_spell_target_type ==========
def patched_get_spell_target_type(card):
    """补丁版的获取目标类型函数"""
    if card.get('name') in ['黎明终焉', '前线与家乡', '伟大的虫族母王', '妥协', '土地女孩', '突击队突击', '重整旗鼓', '阴云密布', '好人寥寥', '竞争战法', '爽口酱汁', '鱼雷', '白色死神[羽笙]', '弱肉强食', '崛起吧!!!海军', '伟大虫族银行', '澎湃力量', '青少年爆发']:
        return 'none'
    if card.get('name') in ['国土巡逻队', '钓鱼执法', '消耗战', '以毒攻毒']:
        return 'minion'
    return _original_get_spell_target_type(card)

# ========== 伟大的虫族母王处理（改为：抽1张牌，对所有敌方单位造成2点伤害） ==========
def handle_great_queen(game, card, caster, target=None):
    """处理伟大的虫族母王卡牌效果：抽1张牌，对所有敌方单位造成2点伤害"""
    print("\n========== [伟大的虫族母王] 开始处理 ==========")
    print(f"施法者: {caster}")
    
    used_card_info = None
    if caster == 'enemy':
        used_card_info = {
            'name': card.get('name', '未知技能'),
            'image': card.get('image', ''),
            'cost': card.get('cost', 1),
            'type': 'spell',
            'effect': card.get('effect', [])
        }
        game._set_message(f"敌方使用了 {card.get('name')}")

    # 效果1：抽1张牌
    game.draw_card(1, is_player=(caster == 'player'))
    print(f"[伟大的虫族母王] 施法者抽了1张牌")
    
    # 效果2：对所有敌方单位造成2点伤害
    if caster == 'player':
        # 玩家使用，对敌方单位造成2点伤害
        damaged_count = 0
        for enemy in game.enemy_board[:]:  # 使用切片复制，避免遍历时修改
            enemy['health'] -= 2
            damaged_count += 1
            print(f"  对敌方 {enemy.get('name')} 造成2点伤害，剩余血量: {enemy['health']}")
        
        # 移除死亡的随从
        original_count = len(game.enemy_board)
        game.enemy_board = [c for c in game.enemy_board if c['health'] > 0]
        killed_count = original_count - len(game.enemy_board)
        
        game._set_message(f"伟大的虫族母王：抽1张牌，并对所有敌方单位造成2点伤害（消灭{killed_count}个）")
        print(f"[伟大的虫族母王] 对{damaged_count}个敌方单位造成2点伤害，消灭{killed_count}个")
        
    else:
        # 敌方使用，对玩家单位造成2点伤害
        damaged_count = 0
        for player_unit in game.player_board[:]:  # 使用切片复制，避免遍历时修改
            player_unit['health'] -= 2
            damaged_count += 1
            print(f"  对玩家 {player_unit.get('name')} 造成2点伤害，剩余血量: {player_unit['health']}")
        
        # 移除死亡的随从
        original_count = len(game.player_board)
        game.player_board = [c for c in game.player_board if c['health'] > 0]
        killed_count = original_count - len(game.player_board)
        
        game._set_message(f"敌方伟大的虫族母王：敌方抽1张牌，并对你所有单位造成2点伤害（消灭{killed_count}个）")
        print(f"[伟大的虫族母王] 对{damaged_count}个玩家单位造成2点伤害，消灭{killed_count}个")

    print("========== [伟大的虫族母王] 处理完成 ==========\n")

    # 触发机枪机甲
    if card.get('type') == 'spell':
        trigger_all_machinegun_mechs(game, caster)

    return used_card_info

# ========== 黎明终焉处理 ==========
def handle_dawn_end(game, card, caster, target=None):
    """处理黎明终焉卡牌效果"""
    print("✓ 检测到特殊卡牌: 黎明终焉")
    used_card_info = None
    if caster == 'enemy':
        used_card_info = {
            'name': card.get('name', '未知技能'),
            'image': card.get('image', ''),
            'cost': card.get('cost', 1),
            'type': 'spell',
            'effect': card.get('effect', [])
        }
        game._set_message(f"敌方使用了 {card.get('name')}")

    deck = game.player_deck if caster == 'player' else game.enemy_deck
    board = game.player_board if caster == 'player' else game.enemy_board
    
    if deck:
        top_card = deck[-1]
        if 'attack' in top_card or 'health' in top_card:
            if len(board) < 4:
                new_unit = copy.deepcopy(top_card)
                new_unit.setdefault('health', 1)
                new_unit.setdefault('attack', 0)
                new_unit['original_health'] = new_unit.get('health', 1)
                new_unit['original_attack'] = new_unit.get('attack', 0)
                new_unit['can_attack'] = ('effect' in new_unit and '闪击' in new_unit['effect'])
                
                board.append(new_unit)
                game._set_message(f"黎明终焉：从卡组顶召唤了 {new_unit.get('name')} 的复制！")
            else:
                game._set_message("黎明终焉：战场已满，无法召唤！")
        else:
            game._set_message("黎明终焉：卡组顶的卡牌不是单位！")
    else:
        game._set_message("黎明终焉：卡组已空！")

    if card.get('type') == 'spell':
        trigger_all_machinegun_mechs(game, caster)
    return used_card_info

# ========== 前线与家乡处理 ==========
def handle_front_and_home(game, card, caster, target=None):
    """处理前线与家乡卡牌效果"""
    print("✓ 检测到特殊卡牌: 前线与家乡")
    used_card_info = None
    if caster == 'enemy':
        used_card_info = {
            'name': card.get('name', '未知技能'),
            'image': card.get('image', ''),
            'cost': card.get('cost', 1),
            'type': 'spell',
            'effect': card.get('effect', [])
        }
        game._set_message(f"敌方使用了 {card.get('name')}")

    deck = game.player_deck if caster == 'player' else game.enemy_deck
    modified_units = 0
    buffed_specials = 0

    for unit in deck:
        is_unit = ('attack' in unit) or ('health' in unit) or (unit.get('type') == 'unit')
        if not is_unit:
            continue
        if 'cost' in unit:
            unit['cost'] = max(0, unit['cost'] - 1)
        else:
            unit['cost'] = 0
        modified_units += 1

        if unit.get('name') in ['黄色菌毯', '虫菌生带']:
            if 'attack' in unit:
                unit['attack'] = unit.get('attack', 0) + 1
                if 'original_attack' in unit:
                    unit['original_attack'] = unit.get('original_attack', 0) + 1
            if 'health' in unit:
                unit['health'] = unit.get('health', 1) + 1
                if 'original_health' in unit:
                    unit['original_health'] = unit.get('original_health', 1) + 1
            buffed_specials += 1

    if caster == 'player':
        game._set_message(f"前线与家乡：卡组中 {modified_units} 个单位费用-1，{buffed_specials} 张特殊卡牌获得+1/+1")
    else:
        game._set_message(f"敌方使用前线与家乡，敌方卡组中 {modified_units} 个单位费用-1，{buffed_specials} 张特殊卡牌获得+1/+1")

    if card.get('type') == 'spell':
        trigger_all_machinegun_mechs(game, caster)
    return used_card_info

def patched_apply_spell_effect(game, card, caster, target=None):
    # ✅ 强制导入，确保可用
    import random
    import copy
    import traceback
    
    # 其余代码...
    # 在第一次使用game时，确保Game类已被补丁
    patch_game_class_if_needed()
    #veteran_simple.on_spell_used(game, caster)
    print(f"\n========== [完全版] 应用法术效果 ==========")
    print(f"法术名称: {card.get('name')}")
    print(f"施法者: {caster}")
    print(f"目标索引: {target}")

    effect = card.get('effect', [])
    used_card_info = None
    if caster == 'enemy':
        used_card_info = {
            'name': card.get('name', '未知技能'),
            'image': card.get('image', ''),
            'cost': card.get('cost', 1),
            'type': 'spell',
            'effect': effect
        }
        game._set_message(f"敌方使用了 {card.get('name')}")

    # ---------- 特殊卡牌优先处理 ----------
    if card.get('name') == '黎明终焉':
        return handle_dawn_end(game, card, caster, target)

    if card.get('name') == '前线与家乡':
        return handle_front_and_home(game, card, caster, target)

    if card.get('name') == '伟大的虫族母王':
        return handle_great_queen(game, card, caster, target)

    # ---------- 以下为普通法术效果（复制自 spells.py，并将攻击力增加改为 apply_attack_bonus）----------
    for eff in effect:
        print(f"处理效果: {eff}")

        # 抽牌
        if eff == '抽牌':
            game.draw_card(1, is_player=(caster == 'player'))

        # 敌方全体打2
        elif eff == '敌方全体打2':
            if caster == 'player':
                for enemy in game.enemy_board[:]:
                    enemy['health'] -= 2
                game.enemy_board = [c for c in game.enemy_board if c['health'] > 0]
                game._set_message("对敌方全体造成2点伤害")
            else:
                for enemy in game.player_board[:]:
                    enemy['health'] -= 2
                game.player_board = [c for c in game.player_board if c['health'] > 0]
                game._set_message("敌方对我方全体造成2点伤害")

        # 对目标随从打3
        elif eff == '对目标随从打3':
            if target is not None:
                if caster == 'player' and 0 <= target < len(game.enemy_board):
                    target_card = game.enemy_board[target]
                    target_card['health'] -= 3
                    game._set_message(f"对敌方 {target_card.get('name')} 造成3点伤害")
                    if target_card['health'] <= 0:
                        game.enemy_board.pop(target)
                elif caster == 'enemy' and 0 <= target < len(game.player_board):
                    target_card = game.player_board[target]
                    target_card['health'] -= 3
                    game._set_message(f"敌方对你的 {target_card.get('name')} 造成3点伤害")
                    if target_card['health'] <= 0:
                        game.player_board.pop(target)

        # 敌方英雄打2
        elif eff == '敌方英雄打2':
            if caster == 'player':
                game.enemy_health -= 2
                game._set_message("对敌方英雄造成2点伤害")
            else:
                game.player_health -= 2
                game._set_message("敌方对你英雄造成2点伤害")

        # 己方英雄回2血
        elif eff == '己方英雄回2血':
            if caster == 'player':
                game.player_health = min(30, game.player_health + 2)
                game._set_message("回复2点生命值")
            else:
                game.enemy_health = min(30, game.enemy_health + 2)
                game._set_message("敌方回复2点生命值")

        # 将两张抵抗加入敌方牌库顶 (虫王万岁)
        elif eff == '将两张抵抗加入敌方牌库顶':
            resistance_card = game.cards_map.get('抵抗')
            if resistance_card is None:
                print("错误：找不到卡牌 '抵抗'")
                continue
            if caster == 'player':
                for _ in range(2):
                    game.enemy_deck.append(copy.deepcopy(resistance_card))
                game._set_message("将两张「抵抗」加入敌方牌库顶")
            else:
                for _ in range(2):
                    game.player_deck.append(copy.deepcopy(resistance_card))
                game._set_message("敌方将两张「抵抗」加入你的牌库顶")

        # 抽一张牌，敌方随机弃一张牌
        elif eff == '抽一张牌，敌方随机弃一张牌':
            game.draw_card(1, is_player=(caster == 'player'))
            if caster == 'player':
                if game.enemy_hand:
                    discard_index = random.randint(0, len(game.enemy_hand) - 1)
                    discarded = game.enemy_hand.pop(discard_index)
                    game._set_message(f"敌方弃掉 {discarded.get('name')}")
            else:
                if game.player_hand:
                    discard_index = random.randint(0, len(game.player_hand) - 1)
                    discarded = game.player_hand.pop(discard_index)
                    game._set_message(f"你被弃掉 {discarded.get('name')}")

        # 所有随从获得+1/+1
        elif eff == '所有随从获得+1/+1':
            if caster == 'player':
                for unit in game.player_board:
                    apply_attack_bonus(game, unit, 1, source=card)
                    unit['health'] = unit.get('health', 0) + 1
                game._set_message("你的所有随从获得+1/+1")
            else:
                for unit in game.enemy_board:
                    apply_attack_bonus(game, unit, 1, source=card)
                    unit['health'] = unit.get('health', 0) + 1
                game._set_message("敌方所有随从获得+1/+1")

        # 沉默一个随从
        elif eff == '沉默一个随从':
            if target is not None:
                if caster == 'player' and 0 <= target < len(game.enemy_board):
                    target_card = game.enemy_board[target]
                    target_card['effect'] = []
                    game._set_message(f"沉默 {target_card.get('name')}")
                elif caster == 'enemy' and 0 <= target < len(game.player_board):
                    target_card = game.player_board[target]
                    target_card['effect'] = []
                    game._set_message(f"敌方沉默你的 {target_card.get('name')}")

        # 冻结一个随从
        elif eff == '冻结一个随从':
            if target is not None:
                if caster == 'player' and 0 <= target < len(game.enemy_board):
                    target_card = game.enemy_board[target]
                    target_card['can_attack'] = False
                    target_card['frozen'] = True
                    game._set_message(f"冻结 {target_card.get('name')}")
                elif caster == 'enemy' and 0 <= target < len(game.player_board):
                    target_card = game.player_board[target]
                    target_card['can_attack'] = False
                    target_card['frozen'] = True
                    game._set_message(f"敌方冻结你的 {target_card.get('name')}")

        # 造成2点伤害，抽一张牌
        elif eff == '造成2点伤害，抽一张牌':
            if target is not None:
                if caster == 'player' and 0 <= target < len(game.enemy_board):
                    target_card = game.enemy_board[target]
                    target_card['health'] -= 2
                    game._set_message(f"对 {target_card.get('name')} 造成2点伤害")
                    if target_card['health'] <= 0:
                        game.enemy_board.pop(target)
                elif caster == 'enemy' and 0 <= target < len(game.player_board):
                    target_card = game.player_board[target]
                    target_card['health'] -= 2
                    game._set_message(f"敌方对你的 {target_card.get('name')} 造成2点伤害")
                    if target_card['health'] <= 0:
                        game.player_board.pop(target)
                game.draw_card(1, is_player=(caster == 'player'))

        # 使己方卡组所有单位获得+1血量 (先锋者运输艇)
        elif eff == '使己方卡组所有单位获得+1血量':
            if caster == 'player':
                for card_in_deck in game.player_deck:
                    if 'health' in card_in_deck:
                        card_in_deck['health'] = card_in_deck.get('health', 1) + 1
                        if 'original_health' in card_in_deck:
                            card_in_deck['original_health'] = card_in_deck.get('original_health', 1) + 1
                game._set_message("你的卡组中所有随从获得+1生命值")
            else:
                for card_in_deck in game.enemy_deck:
                    if 'health' in card_in_deck:
                        card_in_deck['health'] = card_in_deck.get('health', 1) + 1
                        if 'original_health' in card_in_deck:
                            card_in_deck['original_health'] = card_in_deck.get('original_health', 1) + 1
                game._set_message("敌方卡组中所有随从获得+1生命值")

        # 默认无效果
        else:
            print(f"未知效果: {eff}")
            
    # ===== 青少年爆发 - 使攻击力最高的友方单位获得奋战、闪击，攻防翻倍 =====
    if card.get('name') == '青少年爆发':
        print("✓ 检测到特殊卡牌: 青少年爆发")

        # 确定友方战场
        if caster == 'player':
            friendly_board = game.player_board
            side_name = "玩家"
        else:
            friendly_board = game.enemy_board
            side_name = "敌方"

    # 检查是否有友方单位
        if not friendly_board:
            game._set_message("没有友方单位，无法使用")
            return used_card_info

    # 找出攻击力最高的单位
        max_attack = 0
        target_index = 0
        target_unit = None

        for i, unit in enumerate(friendly_board):
            attack = unit.get('attack', 0)
            if attack > max_attack:
                max_attack = attack
                target_index = i
                target_unit = unit

        if target_unit is None:
            game._set_message("没有有效的目标")
            return used_card_info

    # 记录原始值（用于日志）
        old_attack = target_unit.get('attack', 0)
        old_health = target_unit.get('health', 1)
    
    # 攻击力和生命值翻倍
        target_unit['attack'] = old_attack * 2
        target_unit['health'] = old_health * 2
    
    # 更新原始值（用于显示变化）
        if 'original_attack' in target_unit:
            target_unit['original_attack'] = target_unit['attack']
        if 'original_health' in target_unit:
            target_unit['original_health'] = target_unit['health']
    
        # 添加奋战效果（本回合可攻击两次）
        if 'effect' not in target_unit:
            target_unit['effect'] = []
        if not isinstance(target_unit['effect'], list):
            target_unit['effect'] = [target_unit['effect']] if target_unit['effect'] else []
    
    # 添加奋战
        if '奋战' not in target_unit['effect']:
            target_unit['effect'].append('奋战')
    
    # 添加闪击（如果还没有）
        if '闪击' not in target_unit['effect']:
            target_unit['effect'].append('闪击')
    
        # 设置本回合可攻击（闪击效果）
        target_unit['can_attack'] = True
    
    # 记录奋战次数（用于攻击两次）
        if 'attacks_this_turn' not in target_unit:
            target_unit['attacks_this_turn'] = 0
        target_unit['max_attacks_per_turn'] = 2  # 奋战 = 2次攻击
    
        game._set_message(f"青少年爆发：{target_unit.get('name')}（攻击力最高）获得奋战和闪击，攻防翻倍 ({old_attack}/{old_health} → {target_unit['attack']}/{target_unit['health']})")
        print(f"  选择攻击力最高的单位: {target_unit.get('name')} (攻击力 {old_attack})")
        print(f"  {target_unit.get('name')} 现在可以攻击2次，攻防翻倍")

    # 记录敌方使用信息
        if caster == 'enemy':
            used_card_info = {
                'name': card.get('name', '青少年爆发'),
                'image': card.get('image', ''),
                'cost': card.get('cost', 4),
                'type': 'spell',
                'effect': card.get('effect', [])
            }

        # 触发机枪机甲
        if card.get('type') == 'spell':
            trigger_all_machinegun_mechs(game, caster)        
        return used_card_info
            
    # ===== 科技行动 - 将一张科技行动洗入卡组，再将一张澎湃力量加入手牌 =====
    if card.get('name') == '科技行动':
        print("✓ 检测到特殊卡牌: 科技行动")
    
        # 获取科技行动卡牌本身
        tech_action_card = game.cards_map.get('科技行动')
        if tech_action_card is None:
            print("错误：找不到科技行动卡牌")
            return used_card_info
    
        # 获取澎湃力量卡牌
        power_card = game.cards_map.get('澎湃力量')
        if power_card is None:
            print("错误：找不到澎湃力量卡牌")
            return used_card_info
    
        # 确定友方卡组和手牌
        if caster == 'player':
            deck = game.player_deck
            hand = game.player_hand
            side_name = "玩家"
        else:
            deck = game.enemy_deck
            hand = game.enemy_hand
            side_name = "敌方"
    
        # 将一张科技行动洗入卡组（随机位置）
        import random
        copy_tech = copy.deepcopy(tech_action_card)
        insert_pos = random.randint(0, len(deck))
        deck.insert(insert_pos, copy_tech)
        print(f"  将科技行动洗入{side_name}卡组，位置: {insert_pos}")
    
        # 将一张澎湃力量加入手牌（检查手牌上限）
        copy_power = copy.deepcopy(power_card)
        if len(hand) < game.MAX_HAND_SIZE:
            hand.append(copy_power)
            game._set_message(f"科技行动：将一张科技行动洗入卡组，将一张澎湃力量加入手牌！")
            print(f"  将澎湃力量加入{side_name}手牌")
        else:
            # 手牌已满，加入牌库底
            deck.append(copy_power)
            game._set_message(f"科技行动：手牌已满，澎湃力量置入牌库底")
            print(f"  手牌已满，澎湃力量置入{side_name}牌库底")
    
        # 记录敌方使用信息
        if caster == 'enemy':
            used_card_info = {
                'name': card.get('name', '科技行动'),
                'image': card.get('image', ''),
                'cost': card.get('cost', 2),
                'type': 'spell',
                'effect': card.get('effect', [])
            }
    
        # 触发机枪机甲
        if card.get('type') == 'spell':
            trigger_all_machinegun_mechs(game, caster)  
        return used_card_info
            
    # ===== 澎湃力量 - 抽两张牌，根据增加的指挥点槽获得指挥点 =====
    if card.get('name') == '澎湃力量':
        print("✓ 检测到特殊卡牌: 澎湃力量")
    
        # 计算本场对局中增加的指挥点槽数量
        if caster == 'player':
            slot_increase = game.player_max_commander_slot - 1
            command_gain = slot_increase * 2
            game.player_commander_slot += command_gain
            game._set_message(f"使用澎湃力量：抽两张牌，获得{command_gain}个指挥点！")
        else:
            slot_increase = game.enemy_max_commander_slot - 1
            command_gain = slot_increase * 2
            game.enemy_commander_slot += command_gain
            game._set_message(f"敌方使用澎湃力量：敌方抽两张牌，获得{command_gain}个指挥点！")    
        # 抽两张牌
        game.draw_card(2, is_player=(caster == 'player'))    
        print(f"  增加的槽位数: {slot_increase}, 获得指挥点: {command_gain}")

    # ---------- 特殊卡牌效果（通过名称）----------
    # 石油需要
    if card.get('name') == '石油需要':
        print("✓ 检测到特殊卡牌: 石油需要")
        if caster == 'player':
            if game.player_max_commander_slot < 24:
                game.player_max_commander_slot += 1
            game.player_commander_slot += 1
            game._set_message("使用石油需要，指挥槽+1！")
        else:
            if game.enemy_max_commander_slot < 24:
                game.enemy_max_commander_slot += 1
            game.enemy_commander_slot += 1
            game._set_message("敌方使用石油需要，敌方指挥槽+1！")
            
    # ===== 伟大虫族银行 - 获得2个指挥点（不增加槽位）=====
    if card.get('name') == '伟大虫族银行':
        print("✓ 检测到特殊卡牌: 伟大虫族银行")
        if caster == 'player':
            game.player_commander_slot += 2
            game._set_message("使用伟大虫族银行，指挥点+2！")
        else:
            game.enemy_commander_slot += 2
            game._set_message("敌方使用伟大虫族银行，敌方指挥点+2！")

    # 战争需要
    if card.get('name') == '战争需要':
        print("✓ 检测到特殊卡牌: 战争需要")
        if caster == 'player':
            for _ in range(2):
                if game.player_max_commander_slot < 24:
                    game.player_max_commander_slot += 1
            game.player_commander_slot += 2
            game._set_message("使用战争需要，指挥槽+2！")
        else:
            for _ in range(2):
                if game.enemy_max_commander_slot < 24:
                    game.enemy_max_commander_slot += 1
            game.enemy_commander_slot += 2
            game._set_message("敌方使用战争需要，敌方指挥槽+2！")

    # 战争债券
    if card.get('name') == '战争债券':
        print("✓ 检测到特殊卡牌: 战争债券")
        if caster == 'player':
            for _ in range(2):
                if game.player_max_commander_slot < 24:
                    game.player_max_commander_slot += 1
            game.player_commander_slot += 2
            if not hasattr(game, 'delayed_draw'):
                game.delayed_draw = {}
            game.delayed_draw['player'] = game.delayed_draw.get('player', 0) + 1
            game._set_message("使用战争债券，指挥槽+2！下个友方回合开始时额外抽一张牌")
        else:
            for _ in range(2):
                if game.enemy_max_commander_slot < 24:
                    game.enemy_max_commander_slot += 1
            game.enemy_commander_slot += 2
            if not hasattr(game, 'delayed_draw'):
                game.delayed_draw = {}
            game.delayed_draw['enemy'] = game.delayed_draw.get('enemy', 0) + 1
            game._set_message("敌方使用战争债券，敌方指挥槽+2！敌方下个回合开始时额外抽一张牌")

    # 反潜巡逻
    if card.get('name') == '反潜巡逻':
        print("✓ 检测到特殊卡牌: 反潜巡逻")
        if caster == 'player':
            for _ in range(2):
                if game.player_max_commander_slot < 24:
                    game.player_max_commander_slot += 1
            game.player_commander_slot += 2
            if game.enemy_board:
                target_idx = random.randint(0, len(game.enemy_board) - 1)
                target_card = game.enemy_board[target_idx]
                target_card['health'] -= 1000
                if target_card['health'] <= 0:
                    game.enemy_board.pop(target_idx)
                game._set_message(f"使用反潜巡逻，随机消灭敌方 {target_card.get('name')}！")
            else:
                game._set_message("使用反潜巡逻，但敌方场上没有随从")
        else:
            for _ in range(2):
                if game.enemy_max_commander_slot < 24:
                    game.enemy_max_commander_slot += 1
            game.enemy_commander_slot += 2
            if game.player_board:
                target_idx = random.randint(0, len(game.player_board) - 1)
                target_card = game.player_board[target_idx]
                target_card['health'] -= 1000
                if target_card['health'] <= 0:
                    game.player_board.pop(target_idx)
                game._set_message(f"敌方使用反潜巡逻，随机消灭你的 {target_card.get('name')}！")
            else:
                game._set_message("敌方使用反潜巡逻，但你场上没有随从")

    # 仔细生产
    if card.get('name') == '仔细生产':
        print("✓ 检测到特殊卡牌: 仔细生产")
        deck = game.player_deck if caster == 'player' else game.enemy_deck
        for unit in deck:
            if 'attack' in unit:
                unit['attack'] += 1
                if 'original_attack' in unit:
                    unit['original_attack'] += 1
        game._set_message("使用仔细生产，卡组中所有单位获得+1攻击力")
        
    # ---------- 阴云密布：双方抽一张牌，双方英雄恢复3点生命值 ----------
    if card.get('name') == '阴云密布':
        print("✓ 检测到特殊卡牌: 阴云密布")
        # 双方各抽一张牌（注意抽牌方参数）
        if caster == 'player':
            game.draw_card(1, is_player=True)   # 玩家抽1张
            game.draw_card(1, is_player=False)  # 敌方抽1张
        else:
            game.draw_card(1, is_player=False)  # 敌方抽1张
            game.draw_card(1, is_player=True)   # 玩家抽1张

        # 双方英雄增加3点生命值，上限99
        game.player_health = min(99, game.player_health + 3)
        game.enemy_health = min(99, game.enemy_health + 3)

        game._set_message("使用阴云密布：双方抽一张牌，双方英雄恢复3点生命值")

    # ===== 爽口酱汁 - 使友方所有随从和卡组里的随从获得“收缴” =====
    if card.get('name') == '爽口酱汁':
        print("✓ 检测到特殊卡牌: 爽口酱汁")
    
        # 确定友方阵营
        if caster == 'player':
            board = game.player_board
            deck = game.player_deck
            side_name = "玩家"
        else:
            board = game.enemy_board
            deck = game.enemy_deck
            side_name = "敌方"
    
        # 给场上所有随从添加“收缴”
        for unit in board:
            if unit is None:
                continue
            # 确保 effect 字段存在
            if 'effect' not in unit:
                unit['effect'] = []
            if '收缴' not in unit['effect']:
                unit['effect'].append('收缴')
                print(f"  场上 {unit.get('name')} 获得收缴")    
        # 给牌库中所有随从添加“收缴”
        added_count = 0
        for card_in_deck in deck:
            # 判断是否为随从（拥有 attack 或 health，或 type 为 unit）
            is_unit = ('attack' in card_in_deck) or ('health' in card_in_deck) or (card_in_deck.get('type') == 'unit')
            if not is_unit:
                continue
            if 'effect' not in card_in_deck:
                card_in_deck['effect'] = []
            if '收缴' not in card_in_deck['effect']:
                card_in_deck['effect'].append('收缴')
                added_count += 1
                print(f"  牌库 {card_in_deck.get('name')} 获得收缴")  
        game._set_message(f"{side_name} 使用爽口酱汁：所有随从获得收缴（场上 {len(board)} 个，牌库 {added_count} 张）")    
        # 如果希望敌方使用时也显示名称（用于前端动画），可以构造 used_card_info
        if caster == 'enemy':
            used_card_info = {
                'name': card.get('name', '爽口酱汁'),
                'image': card.get('image', ''),
                'cost': card.get('cost', 14),
                'type': 'spell',
                'effect': card.get('effect', [])
            }
        return used_card_info
        
    if card.get('name') == '鱼雷':
        print("✓ 检测到特殊卡牌: 鱼雷")
        if caster == 'player':
            enemy_deck = game.enemy_deck
            hand = game.player_hand
            friendly_health = game.player_health
        else:
            enemy_deck = game.player_deck
            hand = game.enemy_hand
            friendly_health = game.enemy_health

        spells_in_enemy_deck = [c for c in enemy_deck if c.get('type') == 'spell']
        if not spells_in_enemy_deck:
            game._set_message("敌方卡组中没有指令，鱼雷没有效果")
            return used_card_info

        import random
        chosen_spell = random.choice(spells_in_enemy_deck)
        spell_cost = chosen_spell.get('cost', 0)
        spell_name = chosen_spell.get('name', '未知指令')

        # 增加友方英雄生命值
        if caster == 'player':
            game.player_health = min(99, game.player_health + spell_cost)
        else:
            game.enemy_health = min(99, game.enemy_health + spell_cost)

        # 将复制牌加入手牌（检查手牌上限）
        if len(hand) < game.MAX_HAND_SIZE:
            import copy
            new_card = copy.deepcopy(chosen_spell)
            # 如果是法术牌，可能需要初始化一些字段（但法术牌没有 attack/health）
            hand.append(new_card)
            game._set_message(f"鱼雷复制了敌方卡组中的「{spell_name}」，恢复 {spell_cost} 点生命值，并将该牌加入手牌")
            print(f"复制指令: {spell_name}，已加入手牌")
        else:
            game._set_message(f"鱼雷复制了敌方卡组中的「{spell_name}」，恢复 {spell_cost} 点生命值，但手牌已满，复制牌被销毁")

        return used_card_info
        
# 在 new_1_spells.py 的 patched_apply_spell_effect 函数中，在 "好人寥寥" 处理之后添加：

    # ===== 白色死神 - 使所有敌方单位变为1/1，召唤游击队员 =====
    if card.get('name') == '白色死神[羽笙]':
        print("✓ 检测到特殊卡牌: 白色死神")
        
        # 效果1：使所有敌方单位变为1/1
        if caster == 'player':
            # 玩家使用，敌方单位变为1/1
            transformed_count = 0
            for enemy in game.enemy_board:
                old_name = enemy.get('name', '未知')
                enemy['attack'] = 1
                enemy['health'] = 1
                enemy['original_attack'] = 1
                enemy['original_health'] = 1
                # 清除临时攻击力加成
                if 'temp_attack' in enemy:
                    del enemy['temp_attack']
                transformed_count += 1
                print(f"  敌方 {old_name} 变为 1/1")
            
            # 效果2：召唤游击队员到友方战场
            if len(game.player_board) < 4:  # 战场上限4个
                guerrilla = game.cards_map.get('游击队员')
                if guerrilla:
                    new_unit = copy.deepcopy(guerrilla)
                    new_unit['original_attack'] = new_unit.get('attack', 1)
                    new_unit['original_health'] = new_unit.get('health', 1)
                    new_unit['can_attack'] = True  # 闪击
                    game.player_board.append(new_unit)
                    game._set_message(f"白色死神：使所有敌方单位变为1/1，并召唤游击队员！")
                    print(f"  召唤游击队员到玩家战场")
                else:
                    game._set_message("白色死神：找不到游击队员卡牌")
                    print("错误：找不到游击队员")
            else:
                game._set_message("白色死神：战场已满，无法召唤游击队员")
                print("玩家战场已满，无法召唤游击队员")
                
        else:  # caster == 'enemy'
            # 敌方使用，玩家单位变为1/1
            transformed_count = 0
            for player_unit in game.player_board:
                old_name = player_unit.get('name', '未知')
                player_unit['attack'] = 1
                player_unit['health'] = 1
                player_unit['original_attack'] = 1
                player_unit['original_health'] = 1
                if 'temp_attack' in player_unit:
                    del player_unit['temp_attack']
                transformed_count += 1
                print(f"  玩家 {old_name} 变为 1/1")
            
            # 召唤游击队员到敌方战场
            if len(game.enemy_board) < 4:
                guerrilla = game.cards_map.get('游击队员')
                if guerrilla:
                    new_unit = copy.deepcopy(guerrilla)
                    new_unit['original_attack'] = new_unit.get('attack', 1)
                    new_unit['original_health'] = new_unit.get('health', 1)
                    new_unit['can_attack'] = True
                    game.enemy_board.append(new_unit)
                    game._set_message(f"敌方白色死神：使你的所有单位变为1/1，并召唤游击队员！")
                    print(f"  召唤游击队员到敌方战场")
                else:
                    game._set_message("敌方白色死神：找不到游击队员卡牌")
            else:
                game._set_message("敌方白色死神：战场已满，无法召唤游击队员")
                print("敌方战场已满，无法召唤游击队员")
        
        # 如果是敌方使用，记录使用信息
        if caster == 'enemy':
            used_card_info = {
                'name': card.get('name', '白色死神'),
                'image': card.get('image', ''),
                'cost': card.get('cost', 5),
                'type': 'spell',
                'effect': card.get('effect', [])
            }
        
        # 触发机枪机甲效果
        if card.get('type') == 'spell':
            trigger_all_machinegun_mechs(game, caster)
            
        return used_card_info
        
# 在 new_1_spells.py 的 patched_apply_spell_effect 函数中添加：

    # ===== 弱肉强食 - 消灭所有最低攻单位，优先收缴游击队员 =====
    if card.get('name') == '弱肉强食':
        print("✓ 检测到特殊卡牌: 弱肉强食")
        
        # 收集所有单位
        all_units = []
        for idx, unit in enumerate(game.player_board):
            all_units.append({
                'unit': unit,
                'board': 'player',
                'index': idx,
                'name': unit.get('name', ''),
                'attack': unit.get('attack', 0)
            })
        for idx, unit in enumerate(game.enemy_board):
            all_units.append({
                'unit': unit,
                'board': 'enemy',
                'index': idx,
                'name': unit.get('name', ''),
                'attack': unit.get('attack', 0)
            })
        
        if not all_units:
            game._set_message("弱肉强食：战场上没有单位")
            return used_card_info
        
        # 找出最低攻击力
        min_attack = min(u['attack'] for u in all_units)
        print(f"最低攻击力: {min_attack}")
        
        # 筛选出所有最低攻单位
        min_attack_units = [u for u in all_units if u['attack'] == min_attack]
        
        # 分离游击队员和其他单位
        guerrilla_units = [u for u in min_attack_units if u['name'] == '游击队员']
        other_units = [u for u in min_attack_units if u['name'] != '游击队员']
        
        # 处理顺序：先处理游击队员，再处理其他
        victims = guerrilla_units + other_units
        
        # 确定施法者的手牌和牌库
        if caster == 'player':
            hand = game.player_hand
            deck = game.player_deck
            opponent_hand = game.enemy_hand
            side_name = "玩家"
        else:
            hand = game.enemy_hand
            deck = game.enemy_deck
            opponent_hand = game.player_hand
            side_name = "敌方"
        
        confiscated_count = 0
        sent_to_deck_count = 0
        
        for victim in victims:
            # 从战场上移除
            if victim['board'] == 'player':
                removed_unit = game.player_board.pop(victim['index'])
                # 调整后续索引
                for later in victims:
                    if later['board'] == 'player' and later['index'] > victim['index']:
                        later['index'] -= 1
            else:
                removed_unit = game.enemy_board.pop(victim['index'])
                for later in victims:
                    if later['board'] == 'enemy' and later['index'] > victim['index']:
                        later['index'] -= 1
            
            # 准备收缴的卡牌（变1/1）
            confiscated = copy.deepcopy(removed_unit)
            confiscated['attack'] = 1
            confiscated['health'] = 1
            confiscated['original_attack'] = 1
            confiscated['original_health'] = 1
            confiscated['can_attack'] = ('effect' in confiscated and '闪击' in confiscated['effect'])
            
            # 优先给施法者
            if len(hand) < game.MAX_HAND_SIZE:
                hand.append(confiscated)
                confiscated_count += 1
                print(f"  收缴 {victim['name']} 到 {side_name} 手牌")
            else:
                # 手牌已满，塞入牌库底
                deck.insert(0, confiscated)  # 牌库底（索引0）
                sent_to_deck_count += 1
                print(f"  手牌已满，{victim['name']} 置入 {side_name} 牌库底")
        
        # 设置消息
        if confiscated_count > 0 and sent_to_deck_count > 0:
            game._set_message(f"弱肉强食：消灭{len(victims)}个最低攻单位，收缴{confiscated_count}张，{sent_to_deck_count}张置入牌库底")
        elif confiscated_count > 0:
            game._set_message(f"弱肉强食：消灭{len(victims)}个最低攻单位，全部收缴")
        elif sent_to_deck_count > 0:
            game._set_message(f"弱肉强食：消灭{len(victims)}个最低攻单位，手牌已满，全部置入牌库底")
        else:
            game._set_message("弱肉强食：没有单位被消灭")
        
        # 记录敌方使用信息
        if caster == 'enemy':
            used_card_info = {
                'name': card.get('name', '弱肉强食'),
                'image': card.get('image', ''),
                'cost': card.get('cost', 5),
                'type': 'spell',
                'effect': card.get('effect', [])
            }
        
        # 触发机枪机甲
        if card.get('type') == 'spell':
            trigger_all_machinegun_mechs(game, caster)
        
        return used_card_info
        
# 在 new_1_spells.py 的 patched_apply_spell_effect 函数中添加：

    # ===== 钓鱼执法 - 打2伤，送游击队员（带收缴）=====
    if card.get('name') == '钓鱼执法':
        print("✓ 检测到特殊卡牌: 钓鱼执法")
        
        if target is None:
            game._set_message("需要选择目标")
            return used_card_info
        
        # 效果1：造成2点伤害
        if caster == 'player':
            if 0 <= target < len(game.enemy_board):
                target_card = game.enemy_board[target]
                target_card['health'] -= 2
                game._set_message(f"对敌方 {target_card.get('name')} 造成2点伤害")
                if target_card['health'] <= 0:
                    game.enemy_board.pop(target)
            else:
                game._set_message("目标无效")
                return used_card_info
        else:
            if 0 <= target < len(game.player_board):
                target_card = game.player_board[target]
                target_card['health'] -= 2
                game._set_message(f"敌方对你的 {target_card.get('name')} 造成2点伤害")
                if target_card['health'] <= 0:
                    game.player_board.pop(target)
            else:
                game._set_message("目标无效")
                return used_card_info
        
        # 效果2：将一个游击队员加入手牌（带收缴，不带闪击）
        guerrilla_card = game.cards_map.get('游击队员')
        if guerrilla_card is None:
            print("错误：找不到游击队员")
            return used_card_info
        
        # 确定目标手牌
        if caster == 'player':
            hand = game.player_hand
            side_name = "玩家"
        else:
            hand = game.enemy_hand
            side_name = "敌方"
        
        # 创建游击队员（不带闪击，带收缴）
        new_guerrilla = copy.deepcopy(guerrilla_card)
        new_guerrilla['attack'] = 1
        new_guerrilla['health'] = 1
        new_guerrilla['original_attack'] = 1
        new_guerrilla['original_health'] = 1
        
        # 移除闪击（如果有）
        if 'effect' not in new_guerrilla:
            new_guerrilla['effect'] = []
        else:
            # 确保effect是列表
            if not isinstance(new_guerrilla['effect'], list):
                new_guerrilla['effect'] = []
        
        # 移除闪击
        if '闪击' in new_guerrilla['effect']:
            new_guerrilla['effect'].remove('闪击')
        
        # 添加收缴
        if '收缴' not in new_guerrilla['effect']:
            new_guerrilla['effect'].append('收缴')
        
        # 更新描述
        new_guerrilla['description'] = "收缴。消灭受到本单位对战伤害的单位。"
        
        # 加入手牌（检查手牌上限）
        if len(hand) < game.MAX_HAND_SIZE:
            hand.append(new_guerrilla)
            game._set_message(f"钓鱼执法：造成2点伤害，将一个带收缴的游击队员加入{side_name}手牌")
            print(f"  带收缴的游击队员加入{side_name}手牌")
        else:
            game._set_message(f"钓鱼执法：造成2点伤害，但手牌已满，游击队员被弃掉")
            print(f"  手牌已满，游击队员被弃掉")
        
        # 记录敌方使用信息
        if caster == 'enemy':
            used_card_info = {
                'name': card.get('name', '钓鱼执法'),
                'image': card.get('image', ''),
                'cost': card.get('cost', 3),
                'type': 'spell',
                'effect': card.get('effect', [])
            }
        
        # 触发机枪机甲
        if card.get('type') == 'spell':
            trigger_all_machinegun_mechs(game, caster)
        
        return used_card_info
        
    # ===== 消耗战 - 移除单位，下下回合返场并变为2/2 =====
    if card.get('name') == '消耗战':
        print("✓ 检测到特殊卡牌: 消耗战")
    
        if target is None:
            game._set_message("需要选择目标")
            return used_card_info
    
        # 确定目标和所有者
        if caster == 'player':
            # 玩家使用，目标是敌方随从
            if 0 <= target < len(game.enemy_board):
                target_unit = game.enemy_board[target]
                owner = 'enemy'
                board = game.enemy_board
                index = target
            else:
                game._set_message("目标无效")
                return used_card_info
        else:
            # 敌方使用，目标是玩家随从
            if 0 <= target < len(game.player_board):
                target_unit = game.player_board[target]
                owner = 'player'
                board = game.player_board
                index = target
            else:
                game._set_message("目标无效")
                return used_card_info
    
        # 记录被移除的单位信息
        removed_unit = copy.deepcopy(target_unit)
        removed_unit['original_owner'] = owner
        removed_unit['original_index'] = index
        removed_unit['removed_at'] = time.time()
        removed_unit['removed_round'] = game.round_count
        
        # ===== 阴间增强：不管原来多大，返场后强制变成2/2 =====
        # 保存原始值（备用）
        removed_unit['original_attack_before'] = removed_unit.get('attack', 1)
        removed_unit['original_health_before'] = removed_unit.get('health', 1)
        
        # 直接设置为2/2（这样返场时就是2/2）
        removed_unit['attack'] = 2
        removed_unit['health'] = 2
        removed_unit['original_attack'] = 2
        removed_unit['original_health'] = 2
        
        # 清除临时攻击力加成
        if 'temp_attack' in removed_unit:
            del removed_unit['temp_attack']
    
        # 从战场上移除
        board.pop(index)
    
        # 存储到游戏对象的移除队列
        if not hasattr(game, 'removed_units'):
            game.removed_units = []
    
        game.removed_units.append(removed_unit)
    
        # 记录移除动画信息
        if not hasattr(game, 'removal_animations'):
            game.removal_animations = []
    
        game.removal_animations.append({
            'unit': target_unit.get('name', '未知'),
            'owner': owner,
            'index': index,
            'timestamp': time.time()
        })
    
        game._set_message(f"消耗战：移除了 {target_unit.get('name')}，下下回合返场并变为2/2")
    
        # 记录敌方使用信息
        if caster == 'enemy':
            used_card_info = {
                'name': card.get('name', '消耗战'),
                'image': card.get('image', ''),
                'cost': card.get('cost', 3),
                'type': 'spell',
                'effect': card.get('effect', [])
            }
        return used_card_info
        
    # ===== 以毒攻毒 - 消灭一个单位，其控制者抽两张牌 =====
    if card.get('name') == '以毒攻毒':
        print("✓ 检测到特殊卡牌: 以毒攻毒")

        if target is None:
            game._set_message("需要选择目标")
            return used_card_info

        # 确定目标
        if caster == 'player':
            # 玩家使用，目标可以是敌方或友方单位
            if 0 <= target < len(game.enemy_board):
                # 目标是敌方单位
                target_unit = game.enemy_board[target]
                owner = 'enemy'
                board = game.enemy_board
                index = target
                controller = 'enemy'  # 控制者是敌方
            elif 0 <= target < len(game.player_board):
                # 目标是己方单位
                target_unit = game.player_board[target]
                owner = 'player'
                board = game.player_board
                index = target
                controller = 'player'  # 控制者是玩家
            else:
                game._set_message("目标无效")
                return used_card_info
        else:
            # 敌方使用，目标可以是玩家或敌方单位
            if 0 <= target < len(game.player_board):
                # 目标是玩家单位
                target_unit = game.player_board[target]
                owner = 'player'
                board = game.player_board
                index = target
                controller = 'player'  # 控制者是玩家
            elif 0 <= target < len(game.enemy_board):
                # 目标是己方（敌方）单位
                target_unit = game.enemy_board[target]
                owner = 'enemy'
                board = game.enemy_board
                index = target
                controller = 'enemy'  # 控制者是敌方
            else:
                game._set_message("目标无效")
                return used_card_info

        # 记录单位名称用于消息
        unit_name = target_unit.get('name', '未知单位')

        # 从战场上移除（消灭）
        board.pop(index)

        # 让控制者抽两张牌
        if controller == 'player':
            game.draw_card(2, is_player=True)
            game._set_message(f"以毒攻毒：消灭了 {unit_name}，其控制者抽两张牌")
            print(f"  玩家消灭了自己的 {unit_name}，抽两张牌")
        else:
            game.draw_card(2, is_player=False)
            game._set_message(f"以毒攻毒：消灭了 {unit_name}，敌方抽两张牌")
            print(f"  玩家消灭了敌方的 {unit_name}，敌方抽两张牌")

        # 记录敌方使用信息
        if caster == 'enemy':
            used_card_info = {
                'name': card.get('name', '以毒攻毒'),
                'image': card.get('image', ''),
                'cost': card.get('cost', 3),
                'type': 'spell',
                'effect': card.get('effect', [])
            }

        # 触发机枪机甲
        if card.get('type') == 'spell':
            trigger_all_machinegun_mechs(game, caster)
        return used_card_info
        
    # ===== 崛起吧!!!海军 - 使卡组里的所有指令牌算作海军 =====
    if card.get('name') == '崛起吧!!!海军':
        print("✓ 检测到特殊卡牌: 崛起吧!!!海军")

        # 确定友方卡组
        if caster == 'player':
            deck = game.player_deck
            side_name = "玩家"
        else:
            deck = game.enemy_deck
            side_name = "敌方"

        # 给卡组中所有指令牌添加"海军"效果
# 给卡组中所有指令牌添加"海军"效果
        modified_count = 0
        for deck_card in deck:
            is_spell = (deck_card.get('type') == 'spell') or ('attack' not in deck_card and 'health' not in deck_card)
            if is_spell:
                if 'effect' not in deck_card:
                    deck_card['effect'] = []
                if not isinstance(deck_card['effect'], list):
                    deck_card['effect'] = [deck_card['effect']] if deck_card['effect'] else []
                if '海军' not in deck_card['effect']:
                    deck_card['effect'].append('海军')
                    modified_count += 1
                    print(f"  指令牌 {deck_card.get('name')} 获得海军效果")

        if not hasattr(game, 'navy_rising_active'):
            game.navy_rising_active = {}
        game.navy_rising_active[caster] = True

        game._set_message(f"{side_name} 使用崛起吧!!!海军：卡组中 {modified_count} 张指令牌获得海军效果！")
        print(f"  共 {modified_count} 张指令牌变为海军牌")

        # ===== 关键修复：主动触发海军效果 =====
        print(f"  ✓ 崛起吧!!!海军 自身触发海军效果")
        trigger_navy_effects(game, caster, card.get('name'))

        # 记录敌方使用信息
        if caster == 'enemy':
            used_card_info = {
                'name': card.get('name', '崛起吧!!!海军'),
                'image': card.get('image', ''),
                'cost': card.get('cost', 4),
                'type': 'spell',
                'effect': card.get('effect', [])
            }
        # 触发机枪机甲
        if card.get('type') == 'spell':
            trigger_all_machinegun_mechs(game, caster)       
        return used_card_info
        
        # ---------- 妥协：双方抽两张牌，双方英雄恢复8点生命值（上限99） ----------
    if card.get('name') == '妥协':
        print("✓ 检测到特殊卡牌: 妥协")
        # 双方各抽两张牌（注意抽牌方参数）
        if caster == 'player':
            game.draw_card(2, is_player=True)   # 玩家抽2张
            game.draw_card(2, is_player=False)  # 敌方抽2张
        else:
            game.draw_card(2, is_player=False)  # 敌方抽2张
            game.draw_card(2, is_player=True)   # 玩家抽2张

        # 双方英雄增加8点生命值，上限99
        game.player_health = min(99, game.player_health + 8)
        game.enemy_health = min(99, game.enemy_health + 8)

        game._set_message("使用妥协：双方抽两张牌，双方英雄恢复8点生命值")
        
    # ===== 竞争战法：随机将一张特殊牌加入手牌 =====
    if card.get('name') == '竞争战法':
        print("✓ 检测到特殊卡牌: 竞争战法")
        # 收集所有品质为“特殊”且非隐藏的卡牌
        special_cards = []
        for name, c in game.cards_map.items():
            if c.get('quality') == '特殊' and not c.get('hidden', False):
                special_cards.append(c)
    
        if not special_cards:
            game._set_message("没有可用的特殊牌")
        else:
            chosen = random.choice(special_cards)
            hand = game.player_hand if caster == 'player' else game.enemy_hand
            if len(hand) >= game.MAX_HAND_SIZE:
                game._set_message("手牌已满，无法获得特殊牌")
            else:
                # 深拷贝卡牌
                new_card = copy.deepcopy(chosen)
                # 如果是单位牌，初始化必要字段
                if new_card.get('type') == 'unit' or ('attack' in new_card and 'health' in new_card):
                    new_card.setdefault('health', 1)
                    new_card.setdefault('attack', 0)
                    new_card['original_health'] = new_card.get('health', 1)
                    new_card['original_attack'] = new_card.get('attack', 0)
                    new_card['can_attack'] = ('effect' in new_card and '闪击' in new_card['effect'])
                hand.append(new_card)
                game._set_message(f"获得了特殊牌：{chosen.get('name')}")
    
        # 如果是敌方使用，记录使用信息（用于前端显示）
        if caster == 'enemy':
            used_card_info = {
                'name': card.get('name', '未知技能'),
                'image': card.get('image', ''),
                'cost': card.get('cost', 1),
                'type': 'spell',
                'effect': card.get('effect', [])
            }
        # 返回 used_card_info（可能为 None 或 dict）
        return used_card_info
        
    # ---------- 重整旗鼓：随机将卡组中一个单位的2/2复制置入友方战场 ----------
    if card.get('name') == '重整旗鼓':
        print("✓ 检测到特殊卡牌: 重整旗鼓")
        if caster == 'player':
            deck = game.player_deck
            board = game.player_board
            owner = "玩家"
        else:
            deck = game.enemy_deck
            board = game.enemy_board
            owner = "敌方"

        # 筛选牌库中的单位（有 attack 和 health 字段）
        unit_cards = [c for c in deck if c.get('type') == 'unit' or ('attack' in c and 'health' in c)]
        if not unit_cards:
            game._set_message("重整旗鼓：牌库中没有单位")
            print("牌库中无单位，无法召唤")
        elif len(board) >= 4:
            game._set_message("重整旗鼓：战场已满，无法召唤")
            print("战场已满，无法召唤")
        else:
            selected = random.choice(unit_cards)
            print(f"随机选中: {selected.get('name')}")
            new_unit = copy.deepcopy(selected)
            new_unit['attack'] = 2
            new_unit['health'] = 2
            new_unit['original_attack'] = 2
            new_unit['original_health'] = 2
            if 'temp_attack' in new_unit:
                del new_unit['temp_attack']
            new_unit['can_attack'] = ('effect' in new_unit and '闪击' in new_unit['effect'])
            board.append(new_unit)
            game._set_message(f"重整旗鼓召唤了 {selected.get('name')} 的2/2复制")
            print(f"召唤成功: {selected.get('name')} (2/2)")
        
    # ---------- 土地女孩：友方抽两张牌，友方英雄恢复3点生命值 ----------
    if card.get('name') == '土地女孩':
        print("✓ 检测到特殊卡牌: 土地女孩")
        # 友方抽两张牌（根据施法者判断）
        game.draw_card(2, is_player=(caster == 'player'))
        # 友方英雄增加3点生命值，上限99
        if caster == 'player':
            game.player_health = min(99, game.player_health + 3)
        else:
            game.enemy_health = min(99, game.enemy_health + 3)
        game._set_message(f"使用土地女孩：抽两张牌，英雄恢复3点生命值")
        
    # ---------- 国土巡逻队：对一个敌方随从造成2点伤害，将一张卫戍加入手牌 ----------
    if card.get('name') == '国土巡逻队':
        print("✓ 检测到特殊卡牌: 国土巡逻队")
        if target is None:
            game._set_message("需要选择目标")
            return used_card_info

        # 造成2点伤害
        if caster == 'player':
            if 0 <= target < len(game.enemy_board):
                target_card = game.enemy_board[target]
                target_card['health'] -= 2
                game._set_message(f"对敌方 {target_card.get('name')} 造成2点伤害")
                if target_card['health'] <= 0:
                    game.enemy_board.pop(target)
            else:
                game._set_message("目标无效")
                return used_card_info
        else:  # caster == 'enemy'
            if 0 <= target < len(game.player_board):
                target_card = game.player_board[target]
                target_card['health'] -= 2
                game._set_message(f"敌方对你的 {target_card.get('name')} 造成2点伤害")
                if target_card['health'] <= 0:
                    game.player_board.pop(target)
            else:
                game._set_message("目标无效")
                return used_card_info

        # 将一张「卫戍」加入施法者手牌
        garrison_card = game.cards_map.get('卫戍')
        if garrison_card is None:
            print("错误：找不到卡牌 '卫戍'")
            return used_card_info

        hand = game.player_hand if caster == 'player' else game.enemy_hand
        if len(hand) >= game.MAX_HAND_SIZE:
            game._set_message("手牌已满，卫戍被弃掉")
        else:
            hand.append(copy.deepcopy(garrison_card))
            game._set_message("将一张卫戍加入手牌")
        
# ---------- 突击队突击：召唤两个4/4等离子机枪机甲到友方战场 ----------
    if card.get('name') == '突击队突击':
        print("✓ 检测到特殊卡牌: 突击队突击")
        # 确定目标战场（友方）
        board = game.player_board if caster == 'player' else game.enemy_board
        max_board = 4
        # 获取等离子机枪机甲原型
        prototype = game.cards_map.get('等离子机枪机甲')
        if prototype is None:
            print("错误：找不到等离子机枪机甲")
        else:
            # 计算可用空位
            empty_slots = max_board - len(board)
            if empty_slots <= 0:
                game._set_message("战场已满，无法召唤突击队")
            else:
                count = min(2, empty_slots)  # 最多召唤2个
                for i in range(count):
                    new_unit = copy.deepcopy(prototype)
                    # 设置为4/4
                    new_unit['attack'] = 2
                    new_unit['health'] = 2
                    new_unit['original_attack'] = 2
                    new_unit['original_health'] = 2
                    # 保留原有特效（等离子机枪机甲的效果是当友方使用法术时随机造成1点伤害）
                    # 确保 can_attack 根据闪击属性设置
                    new_unit['can_attack'] = ('effect' in new_unit and '闪击' in new_unit['effect'])
                    board.append(new_unit)
                if count == 2:
                    game._set_message("成功召唤两个4/4等离子机枪机甲！")
                elif count == 1:
                    game._set_message("战场只有1个空位，召唤了一个4/4等离子机枪机甲")

    # 坚固防线
    if card.get('name') == '坚固防线':
        print("✓ 检测到特殊卡牌: 坚固防线")
        if target is None:
            print("错误：目标为 None")
            return used_card_info

        if caster == 'player':
            board = game.player_board
            target_owner = "你的"
        else:
            board = game.enemy_board
            target_owner = "敌方"

        if 0 <= target < len(board):
            target_card = board[target]
            if target_card is None:
                print("错误：目标卡牌为 None")
                return used_card_info

            apply_attack_bonus(game, target_card, 1, source=card)
            target_card['health'] = target_card.get('health', 0) + 1
            game._set_message(f"{target_owner}{target_card.get('name')} 获得+1/+1")
        else:
            print(f"错误：目标索引 {target} 超出范围，战场长度 {len(board)}")
            game._set_message("坚固防线目标无效")

    # 在 patched_apply_spell_effect 函数中，找到处理"伟大的虫族母王"的部分之后
    # 添加以下代码：

# ===== 好人寥寥 - 发现一张精英牌 =====
    if card.get('name') == '好人寥寥':
        print("✓ 检测到特殊卡牌: 好人寥寥")
    
        # 获取游戏ID和当前用户名
        game_id = game.game_id
        if caster == 'player':
            username = game.player1
        else:
            username = game.player2

        print(f"触发发现: 玩家 {username} 需要选择一张精英卡牌")
        print(f"游戏ID: {game_id}")
    
        # 生成一个随机的发现令牌（一次性使用）
        import uuid
        discover_token = str(uuid.uuid4())[:8]
    
        # ===== 从CARDS_MAP中筛选精英品质且非隐藏的卡牌 =====
        elite_cards = []
        # ✅ 注意：game.cards_map 可能不是列表，需要遍历values()
        for card_name, card_data in game.cards_map.items():
            if card_data.get('quality') == '精英' and not card_data.get('hidden', False):
                elite_cards.append(card_data)
    
        # 如果精英卡不足3张，添加一些备选
        if len(elite_cards) < 3:
            fallback_cards = []
            for card_name, card_data in game.cards_map.items():
                if card_data.get('quality') in ['特殊', '限定'] and not card_data.get('hidden', False):
                    fallback_cards.append(card_data)
        
            import random
            while len(elite_cards) < 3 and fallback_cards:
                card = random.choice(fallback_cards)
                if card not in elite_cards:
                    elite_cards.append(card)
    
        # ✅ 确保有至少3张卡
        if len(elite_cards) == 0:
        # 实在没有卡，用个默认的
            print("警告：没有找到精英卡，使用默认卡牌")
            elite_cards = [{"name": "默认卡", "quality": "精英", "cost": 1}]
    
    # ===== 随机选择3张不同的卡牌 - 这里就固定下来！=====
        import random
        # ✅ 确保不会超过列表长度
        num_to_select = min(3, len(elite_cards))
        selected_cards = random.sample(elite_cards, num_to_select)
        print(f"已选定{num_to_select}张卡牌: {[c.get('name', '未知') for c in selected_cards]}")
    
        # 存储发现信息到游戏对象（包括选定的卡牌）
        if not hasattr(game, 'discover_tokens'):
            game.discover_tokens = {}
    
        # 存储令牌，关联到用户名和选定的卡牌
        game.discover_tokens[discover_token] = {
            'username': username,
            'game_id': game_id,
            'used': False,
            'timestamp': time.time(),
            'selected_cards': selected_cards  # ✅ 存储选定的卡牌！
        }
    
        # 记录要发给前端的特殊指令
        if not hasattr(game, 'special_actions'):
            game.special_actions = {}
    
        # 使用令牌生成一次性URL
        discover_url = f'/discover/{discover_token}'
    
        game.special_actions[username] = {
            'type': 'discover',
            'message': '请选择一张精英卡牌',
            'redirect_url': discover_url,
            'token': discover_token,
            'timestamp': time.time(),
            'active': True
        }
        print(f"设置special_actions for {username}, 令牌: {discover_token}")
    
        game._set_message("使用好人寥寥，请选择一张精英卡牌")
    
        # ✅ 如果是敌方使用，记录使用信息
        if caster == 'enemy':
            used_card_info = {
                'name': card.get('name', '好人寥寥'),
                'image': card.get('image', ''),
                'cost': card.get('cost', 2),
                'type': 'spell',
                'effect': card.get('effect', [])
            }
            return used_card_info
         
        # ✅ 对于玩家使用，不需要返回used_card_info，但为了函数完整性，返回None
        return None
        
    if 'effect' in card and '海军' in card.get('effect', []):
        print(f"✓ 检测到海军牌: {card.get('name')}")    
        trigger_navy_effects(game, caster, card.get('name'))

    # ---------- 触发机枪机甲 ----------
    if card.get('type') == 'spell':
        print(f"✓ 触发场上所有机枪机甲效果")
        trigger_all_machinegun_mechs(game, caster)

    print("========== 应用法术效果完成 ==========\n")
    
    # ===== 触发轻型战术机效果（友方使用指令时，每个独立触发）=====
    if card.get('type') == 'spell':  # 只有使用法术牌才触发
        try:
            print("✓ 检查轻型战术机效果")
            if caster == 'player':
                mechs = [unit for unit in game.player_board if unit.get('name') == '轻型战术机']
                deck = game.player_deck
                owner = "玩家"
            else:
                mechs = [unit for unit in game.enemy_board if unit.get('name') == '轻型战术机']
                deck = game.enemy_deck
                owner = "敌方"

            if mechs:
                patrol_card = game.cards_map.get('国土巡逻队')
                if patrol_card is None:
                    print("❌ 错误：找不到卡牌 '国土巡逻队'")
                    game._set_message("轻型战术机效果：找不到国土巡逻队卡牌")
                else:
                    for i, mech in enumerate(mechs):
                        print(f"轻型战术机 #{i+1} 触发效果：将两张国土巡逻队加入{owner}牌库底")
                        for _ in range(2):
                            try:
                                # 确保深拷贝成功
                                card_copy = copy.deepcopy(patrol_card)
                                deck.insert(0, card_copy)
                            except Exception as e:
                                print(f"  深拷贝国土巡逻队失败: {e}")
                                # 尝试手动创建简单版本
                                fallback_card = {
                                    "name": "国土巡逻队",
                                    "type": "spell",
                                    "cost": 2,
                                    "description": "对一个敌方单位造成2点伤害,将一张“卫戍”加入手牌",
                                    "image": "国土巡逻队.png",
                                    "quality": "普通",
                                    "hidden": False,
                                    "sound": "/static/sounds/法国.wav"
                                }
                                deck.insert(0, fallback_card)
                        game._set_message(f"轻型战术机 #{i+1} 将两张国土巡逻队洗入牌库底")
        except Exception as e:
            print(f"轻型战术机效果执行出错: {e}")
            traceback.print_exc()
    

# ========== 机枪机甲触发函数 ==========
def trigger_all_machinegun_mechs(game, caster):
    """触发场上所有等离子机枪机甲（每个独立随机目标）"""
    print(f"\n========== 触发所有机枪机甲效果 ==========")
    print(f"施法者: {caster}")

    try:
        if caster == 'player':
            mechs = [card for card in game.player_board if card.get('name') == '等离子机枪机甲']
            targets = ['hero'] + list(range(len(game.enemy_board)))
            for i, mech in enumerate(mechs):
                selected = random.choice(targets)
                if selected == 'hero':
                    game.enemy_health = max(0, game.enemy_health - 1)
                    game._set_message(f"等离子机枪机甲 #{i+1} 对敌方英雄造成1点伤害")
                else:
                    idx = selected
                    if idx < len(game.enemy_board):
                        target = game.enemy_board[idx]
                        target['health'] -= 1
                        game._set_message(f"等离子机枪机甲 #{i+1} 对 {target.get('name')} 造成1点伤害")
                        if target['health'] <= 0:
                            game.enemy_board.pop(idx)
                            targets = ['hero'] + list(range(len(game.enemy_board)))
        else:
            mechs = [card for card in game.enemy_board if card.get('name') == '等离子机枪机甲']
            targets = ['hero'] + list(range(len(game.player_board)))
            for i, mech in enumerate(mechs):
                selected = random.choice(targets)
                if selected == 'hero':
                    game.player_health = max(0, game.player_health - 1)
                    game._set_message(f"敌方等离子机枪机甲 #{i+1} 对你的英雄造成1点伤害")
                else:
                    idx = selected
                    if idx < len(game.player_board):
                        target = game.player_board[idx]
                        target['health'] -= 1
                        game._set_message(f"敌方等离子机枪机甲 #{i+1} 对你的 {target.get('name')} 造成1点伤害")
                        if target['health'] <= 0:
                            game.player_board.pop(idx)
                            targets = ['hero'] + list(range(len(game.player_board)))
    except Exception as e:
        print(f"[trigger_all_machinegun_mechs 异常] {e}")
        traceback.print_exc()
    print("========== 机枪机甲效果触发完成 ==========\n")

# ========== 补丁Game类 ==========
def patch_game_class_if_needed():
    """给Game类打补丁"""
    global _GAME_CLASS_PATCHED, _original_game_start_turn, _original_attack, _original_play_card
    
    if _GAME_CLASS_PATCHED:
        return
    
    try:
        import app
        GameClass = app.Game
        
        # 保存原始方法
        _original_game_start_turn = GameClass._start_turn
        _original_attack = GameClass.attack
        _original_play_card = GameClass.play_card
        
        # 替换为补丁方法
        GameClass._start_turn = patched_game_start_turn
        GameClass.attack = patched_attack_with_laser_defense
        GameClass.play_card = patched_play_card
        
        _GAME_CLASS_PATCHED = True
        print("[补丁] Game 类补丁成功！")
        print(f"[补丁] attack 方法已替换")
        print(f"[补丁] play_card 方法已替换")
    except Exception as e:
        print(f"[补丁错误] {e}")
        
      
      
# ===== 海军核心效果 =====
def trigger_navy_effects(game, caster, navy_card_name):
    """触发所有海军核心单位的效果"""
    print(f"\n========== 触发海军效果 ==========")
    print(f"施法者: {caster}, 使用海军牌: {navy_card_name}")
    
    # 确定双方战场
    if caster == 'player':
        friendly_board = game.player_board
        enemy_board = game.enemy_board
        enemy_hero = 'enemy'
    else:
        friendly_board = game.enemy_board
        enemy_board = game.player_board
        enemy_hero = 'player'
    
    # 触发第78海军旅（对敌方角色造成2点伤害）
    for unit in friendly_board:
        if unit.get('name') == '第78海军旅':
            print(f"  第78海军旅触发！")
            
            # 随机选择目标：敌方英雄或敌方随从
            targets = ['hero'] + list(range(len(enemy_board)))
            selected = random.choice(targets)
            
            if selected == 'hero':
                if enemy_hero == 'enemy':
                    game.enemy_health = max(0, game.enemy_health - 2)
                    game._set_message(f"第78海军旅对敌方英雄造成2点伤害！")
                else:
                    game.player_health = max(0, game.player_health - 2)
                    game._set_message(f"第78海军旅对你英雄造成2点伤害！")
                print(f"    对英雄造成2点伤害")
            else:
                idx = selected
                if idx < len(enemy_board):
                    target = enemy_board[idx]
                    target['health'] -= 2
                    game._set_message(f"第78海军旅对 {target.get('name')} 造成2点伤害！")
                    print(f"    对 {target.get('name')} 造成2点伤害")
                    if target['health'] <= 0:
                        enemy_board.pop(idx)
                        targets = ['hero'] + list(range(len(enemy_board)))
    
    # 触发海军总司令（对敌方英雄造成2点伤害）
    for unit in friendly_board:
        if unit.get('name') == '海军总司令':
            print(f"  海军总司令触发！")
            if enemy_hero == 'enemy':
                game.enemy_health = max(0, game.enemy_health - 2)
                game._set_message(f"海军总司令对敌方英雄造成2点伤害！")
            else:
                game.player_health = max(0, game.player_health - 2)
                game._set_message(f"海军总司令对你英雄造成2点伤害！")
            print(f"    对英雄造成2点伤害")
    
    print("========== 海军效果触发完成 ==========\n")
    
    
    
# ===== 散弹火炮效果 =====
def trigger_shotgun_effect(game, attacker, attacker_index, target_index, target_type):
    """触发散弹火炮效果：攻击时对相邻目标造成1点伤害"""
    
    # 检查攻击者是否是散弹火炮
    if attacker.get('name') != '散弹火炮':
        return
    
    print(f"\n========== 触发散弹火炮效果 ==========")
    print(f"攻击者: 散弹火炮 位置:{attacker_index}")
    
    # 确定攻击者和目标所在的战场
    if game.current_player == game.player1:
        # 当前是玩家回合，攻击者是玩家随从
        attacker_board = game.player_board
        enemy_board = game.enemy_board
        enemy_hero = 'enemy'
    else:
        # 当前是敌方回合，攻击者是敌方随从
        attacker_board = game.enemy_board
        enemy_board = game.player_board
        enemy_hero = 'player'
    
    # 如果目标是英雄，不触发相邻伤害（因为没有相邻概念）
    if target_type == 'hero' or target_index is None:
        print("  目标是英雄，不触发相邻伤害")
        return
    
    # 找到目标在敌方战场上的相邻单位
    adjacent_indices = []
    if target_index > 0:
        adjacent_indices.append(target_index - 1)  # 左边
    if target_index < len(enemy_board) - 1:
        adjacent_indices.append(target_index + 1)  # 右边
    
    if not adjacent_indices:
        print("  目标没有相邻单位")
        return
    
    print(f"  相邻目标索引: {adjacent_indices}")
    
    # 对相邻单位造成1点伤害
    for adj_idx in adjacent_indices:
        if adj_idx < len(enemy_board):
            target = enemy_board[adj_idx]
            old_health = target.get('health', 0)
            target['health'] -= 1
            print(f"    对相邻 {target.get('name')} 造成1点伤害 ({old_health} → {target['health']})")
            
            # 如果死亡，移除
            if target['health'] <= 0:
                print(f"      {target.get('name')} 死亡")
                enemy_board.pop(adj_idx)
                # 调整后续索引（因为删除了一个元素）
                for i in range(len(adjacent_indices)):
                    if adjacent_indices[i] > adj_idx:
                        adjacent_indices[i] -= 1
    
    # 设置游戏消息
    game._set_message(f"散弹火炮对相邻单位造成1点伤害！")
    print("========== 散弹火炮效果触发完成 ==========\n")
        
        

# ========== 应用补丁 ==========
def patch_spells():
    """应用所有补丁"""
    print("[补丁] 正在应用特殊卡牌效果补丁...")

    global _original_apply_spell_effect, _original_get_spell_target_type

    _original_apply_spell_effect = spells.apply_spell_effect
    _original_get_spell_target_type = spells.get_spell_target_type

    spells.apply_spell_effect = patched_apply_spell_effect
    spells.get_spell_target_type = patched_get_spell_target_type

    print("[补丁] spells 模块补丁成功！")
    print("[补丁] 可用的特殊卡牌: 黎明终焉, 前线与家乡, 伟大的虫族母王, B25米切尔")
    

# 应用补丁
patch_spells()

# 导出接口
is_spell_card = spells.is_spell_card
get_spell_target_type = spells.get_spell_target_type
apply_spell_effect = spells.apply_spell_effect
apply_draw_effect = spells.apply_draw_effect