# ai_player.py - AI对战逻辑
import random
import time
import threading

class AIPlayer:
    """AI玩家逻辑"""
    
    def __init__(self, difficulty="普通AI"):
        self.difficulty = difficulty
        self.thinking_time = 0.8  # AI思考时间（秒）
        self.max_actions_per_turn = 20  # 每回合最大行动次数
        
    def set_game(self, game, player_side):
        """设置游戏实例和AI控制的阵营"""
        self.game = game
        self.player_side = player_side  # 'player' 或 'enemy'
        print(f"[AI] 已设置游戏，AI控制阵营: {player_side}")
        
    def take_turn(self):
        """AI执行回合操作"""
        if self.game.game_over:
            print("[AI] 游戏已结束，跳过回合")
            return False
            
        print(f"\n{'='*50}")
        print(f"[AI] ({self.difficulty}) 开始思考")
        print(f"[AI] 控制阵营: {self.player_side}")
        print(f"{'='*50}")
        
        # 获取当前回合的玩家名
        if self.player_side == 'player':
            current_player = self.game.player1
        else:
            current_player = self.game.player2
            
        print(f"[AI] 当前回合玩家: {current_player}")
        
        # 等待一小段时间，让游戏状态稳定
        time.sleep(self.thinking_time)
        
        actions_performed = 0
        max_attempts = 30  # 最大尝试次数，防止死循环
        attempts = 0
        
        # 循环执行行动，直到无法行动
        while attempts < max_attempts:
            attempts += 1
            action_taken = False
            
            # 检查游戏是否结束
            if self.game.game_over:
                print("[AI] 游戏已结束，停止行动")
                break
                
            # 检查是否还是AI的回合
            if self.game.current_player != current_player:
                print(f"[AI] 不再是AI的回合 (当前: {self.game.current_player})")
                break
            
            # 获取当前状态
            if self.player_side == 'player':
                hand = self.game.player_hand
                board = self.game.player_board
                commander_slot = self.game.player_commander_slot
                enemy_board = self.game.enemy_board
                enemy_health = self.game.enemy_health
                my_health = self.game.player_health
            else:
                hand = self.game.enemy_hand
                board = self.game.enemy_board
                commander_slot = self.game.enemy_commander_slot
                enemy_board = self.game.player_board
                enemy_health = self.game.player_health
                my_health = self.game.enemy_health
            
            print(f"[AI] 尝试 {attempts}: 手牌={len(hand)}, 指挥槽={commander_slot}, 场上={len(board)}, 敌方场上={len(enemy_board)}")
            
            # 策略1: 尝试使用法术牌
            if not action_taken:
                if self._try_play_spells():
                    action_taken = True
                    actions_performed += 1
                    print(f"[AI] 使用了法术，继续下一轮")
                    time.sleep(0.3)
                    continue
            
            # 策略2: 尝试打出随从牌
            if not action_taken and len(board) < 4:
                if self._try_play_minions():
                    action_taken = True
                    actions_performed += 1
                    print(f"[AI] 打出了随从，继续下一轮")
                    time.sleep(0.3)
                    continue
            
            # 策略3: 尝试攻击
            if not action_taken:
                if self._try_attack():
                    action_taken = True
                    actions_performed += 1
                    print(f"[AI] 进行了攻击，继续下一轮")
                    time.sleep(0.3)
                    continue
            
            # 如果没有执行任何行动，退出循环
            if not action_taken:
                print(f"[AI] 没有可执行的行动")
                break
        
        # 结束回合
        print(f"[AI] 执行了 {actions_performed} 次行动")
        
        # 再次检查是否还是AI的回合
        if self.game.current_player == current_player and not self.game.game_over:
            print(f"[AI] 结束回合")
            if self.player_side == 'player':
                self.game.end_turn(self.game.player1)
            else:
                self.game.end_turn(self.game.player2)
        else:
            print(f"[AI] 回合已结束或游戏已结束，不重复结束")
            
        print(f"[AI] 回合结束\n")
        return True
    
    def _try_play_minions(self):
        """尝试打出随从牌"""
        # 获取当前状态
        if self.player_side == 'player':
            hand = self.game.player_hand
            commander_slot = self.game.player_commander_slot
            my_board = self.game.player_board
            enemy_board = self.game.enemy_board
            player_name = self.game.player1
        else:
            hand = self.game.enemy_hand
            commander_slot = self.game.enemy_commander_slot
            my_board = self.game.enemy_board
            enemy_board = self.game.player_board
            player_name = self.game.player2
        
        # 找出所有可用的随从牌
        available_minions = []
        for i, card in enumerate(hand):
            # 检查是否是随从牌（不是法术）
            if card.get('type') != 'spell' and card.get('cost', 1) <= commander_slot:
                available_minions.append((i, card))
        
        if not available_minions:
            return False
        
        print(f"[AI] 可用随从: {len(available_minions)} 张")
        
        # 根据难度选择策略
        if self.difficulty == "简单AI":
            # 简单AI：随机打出一张
            index, card = random.choice(available_minions)
            print(f"[AI] 简单AI打出随从: {card.get('name')}")
            self.game.play_card(player_name, index)
            return True
            
        elif self.difficulty == "普通AI":
            # 普通AI：优先打高费牌
            available_minions.sort(key=lambda x: x[1].get('cost', 0), reverse=True)
            index, card = available_minions[0]
            print(f"[AI] 普通AI打出随从: {card.get('name')} (费用:{card.get('cost',0)})")
            self.game.play_card(player_name, index)
            return True
            
        elif self.difficulty == "困难AI":
            # 困难AI：根据局势选择
            # 如果有守护优先打
            for index, card in available_minions:
                if '守护' in card.get('effect', []):
                    print(f"[AI] 困难AI打出守护随从: {card.get('name')}")
                    self.game.play_card(player_name, index)
                    return True
            
            # 否则打最高费的
            available_minions.sort(key=lambda x: x[1].get('cost', 0), reverse=True)
            index, card = available_minions[0]
            print(f"[AI] 困难AI打出随从: {card.get('name')} (费用:{card.get('cost',0)})")
            self.game.play_card(player_name, index)
            return True
            
        else:  # superAI
            # superAI：智能选择随从
            # 1. 优先打第78海军旅（如果有）
            for index, card in available_minions:
                if card.get('name') == '第78海军旅':
                    print(f"[superAI] 打出核心海军: 第78海军旅")
                    self.game.play_card(player_name, index)
                    return True
            
            # 2. 其次打激光防御装置（保护）
            for index, card in available_minions:
                if card.get('name') == '激光防御装置':
                    print(f"[superAI] 打出防御: 激光防御装置")
                    self.game.play_card(player_name, index)
                    return True
            
            # 3. 然后打探察者（守护）
            for index, card in available_minions:
                if card.get('name') == '探察者':
                    print(f"[superAI] 打出守护: 探察者")
                    self.game.play_card(player_name, index)
                    return True
            
            # 4. 再打等离子机枪机甲（配合法术）
            for index, card in available_minions:
                if card.get('name') == '等离子机枪机甲':
                    print(f"[superAI] 打出机枪: 等离子机枪机甲")
                    self.game.play_card(player_name, index)
                    return True
            
            # 5. 最后打最高费的
            available_minions.sort(key=lambda x: x[1].get('cost', 0), reverse=True)
            index, card = available_minions[0]
            print(f"[superAI] 打出高费随从: {card.get('name')}")
            self.game.play_card(player_name, index)
            return True
    
    def _try_play_spells(self):
        """尝试使用法术牌"""
        # 获取当前状态
        if self.player_side == 'player':
            hand = self.game.player_hand
            commander_slot = self.game.player_commander_slot
            my_board = self.game.player_board
            enemy_board = self.game.enemy_board
            my_health = self.game.player_health
            enemy_health = self.game.enemy_health
            player_name = self.game.player1
        else:
            hand = self.game.enemy_hand
            commander_slot = self.game.enemy_commander_slot
            my_board = self.game.enemy_board
            enemy_board = self.game.player_board
            my_health = self.game.enemy_health
            enemy_health = self.game.player_health
            player_name = self.game.player2
        
        # 找出所有可用的法术牌
        available_spells = []
        for i, card in enumerate(hand):
            if card.get('type') == 'spell' and card.get('cost', 1) <= commander_slot:
                available_spells.append((i, card))
        
        if not available_spells:
            return False
        
        print(f"[AI] 可用法术: {len(available_spells)} 张")
        
        # ===== superAI 专属智能策略 =====
        if self.difficulty == "superAI":
            # 1. 好人寥寥 - 发现精英卡（自动随机选择）
            for index, card in available_spells:
                if card.get('name') == '好人寥寥':
                    print(f"[superAI] 使用好人寥寥（自动随机选择）")
                    self.game.play_card(player_name, index)
                    # 好人寥寥不需要目标，会自动触发发现并随机选一张
                    return True
            
            # 2. 优先使用崛起吧!!!海军（如果有第78海军旅在场）
            has_navy = any(card.get('name') == '第78海军旅' for card in my_board)
            if has_navy:
                for index, card in available_spells:
                    if card.get('name') == '崛起吧!!!海军':
                        print(f"[superAI] 使用崛起吧!!!海军（配合第78海军旅）")
                        self.game.play_card(player_name, index)
                        return True
            
            # 3. 白色死神 - 当对面有高攻单位时使用
            high_attack_exists = any(card.get('attack', 0) >= 4 for card in enemy_board)
            if high_attack_exists:
                for index, card in available_spells:
                    if card.get('name') == '白色死神[羽笙]':
                        print(f"[superAI] 使用白色死神（对面有高攻单位）")
                        self.game.play_card(player_name, index)
                        return True
            
            # 4. 弱肉强食 - 当对面铺场时使用
            if len(enemy_board) >= 3:
                for index, card in available_spells:
                    if card.get('name') == '弱肉强食':
                        print(f"[superAI] 使用弱肉强食（对面铺场）")
                        self.game.play_card(player_name, index)
                        return True
            
            # 5. 消耗战 - 需要敌方有单位才能用
            if enemy_board and len(enemy_board) > 0:
                # 找出对面攻击力最高的单位
                max_atk = 0
                max_atk_idx = 0
                for i, card in enumerate(enemy_board):
                    atk = card.get('attack', 0)
                    if atk > max_atk:
                        max_atk = atk
                        max_atk_idx = i
                
                for index, card in available_spells:
                    if card.get('name') == '消耗战':
                        print(f"[superAI] 使用消耗战（移除对面高攻单位）")
                        success, need_target = self.game.play_card(player_name, index)
                        if need_target and self.game.pending_spell:
                            print(f"[superAI] 选择目标: {max_atk_idx}")
                            self.game.play_spell_with_target(player_name, max_atk_idx)
                        return True
            
            # 6. 以毒攻毒 - 需要场上至少有一个单位才能用
            if len(my_board) > 0 or len(enemy_board) > 0:
                for index, card in available_spells:
                    if card.get('name') == '以毒攻毒':
                        # 如果有残血敌方单位，优先斩杀
                        for i, enemy in enumerate(enemy_board):
                            if enemy.get('health', 0) <= 2:
                                print(f"[superAI] 使用以毒攻毒斩杀残血单位")
                                success, need_target = self.game.play_card(player_name, index)
                                if need_target and self.game.pending_spell:
                                    self.game.play_spell_with_target(player_name, i)
                                return True
                        
                        # 如果有自己的残血单位，也可以自杀过牌
                        for i, my_unit in enumerate(my_board):
                            if my_unit.get('health', 0) <= 2 and len(hand) < 3:
                                print(f"[superAI] 使用以毒攻毒自杀残血单位过牌")
                                success, need_target = self.game.play_card(player_name, index)
                                if need_target and self.game.pending_spell:
                                    self.game.play_spell_with_target(player_name, i)
                                return True
                        
                        # 如果敌方有单位，也可以杀敌方单位
                        if enemy_board:
                            print(f"[superAI] 使用以毒攻毒杀敌方单位")
                            success, need_target = self.game.play_card(player_name, index)
                            if need_target and self.game.pending_spell:
                                # 选择攻击力最高的敌方单位
                                max_atk = 0
                                max_atk_idx = 0
                                for i, target in enumerate(enemy_board):
                                    atk = target.get('attack', 0)
                                    if atk > max_atk:
                                        max_atk = atk
                                        max_atk_idx = i
                                self.game.play_spell_with_target(player_name, max_atk_idx)
                            return True
            
            # 7. 钓鱼执法 - 需要敌方有单位
            if enemy_board:
                for index, card in available_spells:
                    if card.get('name') == '钓鱼执法':
                        print(f"[superAI] 使用钓鱼执法")
                        success, need_target = self.game.play_card(player_name, index)
                        if need_target and self.game.pending_spell:
                            # 选择攻击力最高的
                            max_atk = 0
                            max_atk_idx = 0
                            for i, target in enumerate(enemy_board):
                                atk = target.get('attack', 0)
                                if atk > max_atk:
                                    max_atk = atk
                                    max_atk_idx = i
                            print(f"[superAI] 选择目标: {max_atk_idx}")
                            self.game.play_spell_with_target(player_name, max_atk_idx)
                        return True
            
            # 8. 国土巡逻队 - 需要敌方有单位
            if enemy_board:
                for index, card in available_spells:
                    if card.get('name') == '国土巡逻队':
                        print(f"[superAI] 使用国土巡逻队")
                        success, need_target = self.game.play_card(player_name, index)
                        if need_target and self.game.pending_spell:
                            # 选择攻击力最高的
                            max_atk = 0
                            max_atk_idx = 0
                            for i, target in enumerate(enemy_board):
                                atk = target.get('attack', 0)
                                if atk > max_atk:
                                    max_atk = atk
                                    max_atk_idx = i
                            self.game.play_spell_with_target(player_name, max_atk_idx)
                        return True
            
            # 9. 坚固防线 - 需要友方有单位
            if my_board:
                for index, card in available_spells:
                    if card.get('name') == '坚固防线':
                        print(f"[superAI] 使用坚固防线")
                        success, need_target = self.game.play_card(player_name, index)
                        if need_target and self.game.pending_spell:
                            # 选择生命值最高的友方单位
                            max_hp = 0
                            max_hp_idx = 0
                            for i, unit in enumerate(my_board):
                                hp = unit.get('health', 0)
                                if hp > max_hp:
                                    max_hp = hp
                                    max_hp_idx = i
                            print(f"[superAI] 选择目标: {max_hp_idx}")
                            self.game.play_spell_with_target(player_name, max_hp_idx)
                        return True
            
            # 10. 伟大的虫族母王 - 不需要目标，直接清场
            if enemy_board:
                for index, card in available_spells:
                    if card.get('name') == '伟大的虫族母王':
                        print(f"[superAI] 使用伟大的虫族母王（清场+过牌）")
                        self.game.play_card(player_name, index)
                        return True
            
            # 11. 反潜巡逻 - 随机消灭，需要敌方有单位
            if enemy_board:
                for index, card in available_spells:
                    if card.get('name') == '反潜巡逻':
                        print(f"[superAI] 使用反潜巡逻")
                        self.game.play_card(player_name, index)
                        return True
            
            # 12. 战争债券/石油需要/战争需要 - 加指挥槽（不需要目标）
            priority_ramp = ['战争债券', '石油需要', '战争需要']
            for index, card in available_spells:
                if card.get('name') in priority_ramp:
                    print(f"[superAI] 使用加速法术: {card.get('name')}")
                    self.game.play_card(player_name, index)
                    return True
            
            # 13. 过牌法术（不需要目标）
            draw_spells = ['土地女孩', '妥协', '阴云密布', '仔细生产', '先锋者运输艇', '前线与家乡']
            for index, card in available_spells:
                if card.get('name') in draw_spells:
                    print(f"[superAI] 用过牌法术: {card.get('name')}")
                    self.game.play_card(player_name, index)
                    return True
            
            # 14. 抽奖法术（不需要目标）
            lottery_spells = ['竞争战法', '鱼雷', '黎明终焉', '重整旗鼓', '虫王万岁', '突击队突击']
            for index, card in available_spells:
                if card.get('name') in lottery_spells:
                    print(f"[superAI] 用抽奖法术: {card.get('name')}")
                    self.game.play_card(player_name, index)
                    return True
            
            # 15. 爽口酱汁 - 终极收缴（不需要目标）
            for index, card in available_spells:
                if card.get('name') == '爽口酱汁':
                    print(f"[superAI] 用爽口酱汁")
                    self.game.play_card(player_name, index)
                    return True
        
        # ===== 以下是原有逻辑（简单/普通/困难AI）=====
        # 优先使用抽牌和加指挥槽的法术
        priority_spells = ['战争债券', '石油需要', '战争需要', '仔细生产']
        
        for index, card in available_spells:
            if card.get('name') in priority_spells:
                print(f"[AI] 使用优先法术: {card.get('name')}")
                success, need_target = self.game.play_card(player_name, index)
                
                # 如果需要选择目标，处理目标选择
                if need_target and self.game.pending_spell:
                    self._handle_spell_target()
                return True
        
        # 处理需要选择目标的法术
        for index, card in available_spells:
            card_name = card.get('name')
            
            # 坚固防线 - 需要友方随从作为目标
            if card_name == '坚固防线':
                if my_board and len(my_board) > 0:
                    print(f"[AI] 使用坚固防线")
                    success, need_target = self.game.play_card(player_name, index)
                    
                    if need_target and self.game.pending_spell:
                        # 选择友方随从作为目标
                        target_idx = 0
                        if len(my_board) > 1:
                            # 选择生命值最高的友方随从
                            max_hp = 0
                            max_hp_idx = 0
                            for i, target_card in enumerate(my_board):
                                hp = target_card.get('health', 0)
                                if hp > max_hp:
                                    max_hp = hp
                                    max_hp_idx = i
                            target_idx = max_hp_idx
                        
                        print(f"[AI] 选择友方随从 {target_idx} 作为目标")
                        self.game.play_spell_with_target(player_name, target_idx)
                    return True
                else:
                    print(f"[AI] 有坚固防线但没有友方随从，跳过")
                    continue
            
            # 消耗战、以毒攻毒、钓鱼执法、国土巡逻队 - 需要敌方有随从
            if card_name in ['消耗战', '以毒攻毒', '钓鱼执法', '国土巡逻队']:
                if enemy_board and len(enemy_board) > 0:
                    print(f"[AI] 使用法术: {card_name}")
                    success, need_target = self.game.play_card(player_name, index)
                    
                    if need_target and self.game.pending_spell:
                        # 选择敌方随从作为目标
                        target_idx = 0
                        if len(enemy_board) > 1:
                            # 选择攻击力最高的敌方随从
                            max_atk = 0
                            max_atk_idx = 0
                            for i, target_card in enumerate(enemy_board):
                                atk = target_card.get('attack', 0)
                                if atk > max_atk:
                                    max_atk = atk
                                    max_atk_idx = i
                            target_idx = max_atk_idx
                        
                        print(f"[AI] 选择敌方随从 {target_idx} 作为目标")
                        self.game.play_spell_with_target(player_name, target_idx)
                    return True
                else:
                    print(f"[AI] 有 {card_name} 但没有敌方随从，跳过")
                    continue
        
        # 使用无目标法术
        for index, card in available_spells:
            if card.get('name') not in ['坚固防线', '消耗战', '以毒攻毒', '钓鱼执法', '国土巡逻队']:
                print(f"[AI] 使用无目标法术: {card.get('name')}")
                self.game.play_card(player_name, index)
                return True
        
        return False
    
    def _handle_spell_target(self):
        """处理法术目标选择（普通AI用）"""
        if not self.game.pending_spell:
            return
        
        spell = self.game.pending_spell['card']
        target_type = self.game.pending_spell.get('target_type', 'minion')
        
        print(f"[AI] 处理法术目标: {spell.get('name')}, 目标类型: {target_type}")
        
        if self.player_side == 'player':
            if target_type == 'minion':
                targets = self.game.enemy_board
            else:
                targets = self.game.player_board
            player_name = self.game.player1
        else:
            if target_type == 'minion':
                targets = self.game.player_board
            else:
                targets = self.game.enemy_board
            player_name = self.game.player2
        
        if targets and len(targets) > 0:
            target_idx = 0  # 默认选择第一个
            print(f"[AI] 选择目标索引: {target_idx}")
            self.game.play_spell_with_target(player_name, target_idx)
        else:
            print(f"[AI] 没有可用的目标，取消法术")
            self.game.pending_spell = None
    
    def _try_attack(self):
        """尝试攻击"""
        # 获取当前状态
        if self.player_side == 'player':
            my_board = self.game.player_board
            enemy_board = self.game.enemy_board
            enemy_health = self.game.enemy_health
            player_name = self.game.player1
        else:
            my_board = self.game.enemy_board
            enemy_board = self.game.player_board
            enemy_health = self.game.player_health
            player_name = self.game.player2
        
        # 找出所有可以攻击的随从
        attackers = []
        for i, card in enumerate(my_board):
            if card.get('can_attack', False):
                attackers.append(i)
        
        if not attackers:
            return False
        
        print(f"[AI] 可攻击的随从: {len(attackers)} 个")
        
        # 检查敌方是否有守护随从
        taunt_indices = []
        for i, card in enumerate(enemy_board):
            if '守护' in card.get('effect', []):
                taunt_indices.append(i)
        
        # 如果有守护，只能攻击守护随从
        if taunt_indices:
            attacker_idx = attackers[0]
            target_idx = taunt_indices[0]
            
            # superAI 选择最优攻击者
            if self.difficulty == "superAI" and len(attackers) > 1:
                # 选择攻击力最高的攻击者
                max_atk = 0
                max_atk_idx = attackers[0]
                for i in attackers:
                    atk = my_board[i].get('attack', 0)
                    if atk > max_atk:
                        max_atk = atk
                        max_atk_idx = i
                attacker_idx = max_atk_idx
            
            print(f"[AI] 攻击守护随从")
            self.game.attack(player_name, attacker_idx, target_idx)
            return True
        
        # 如果没有守护，可以选择攻击英雄或随从
        if enemy_board:
            # 有敌方随从，优先攻击随从
            attacker_idx = attackers[0]
            target_idx = 0
            
            # superAI 智能选择目标
            if self.difficulty == "superAI":
                # 选择攻击力最高的敌方随从
                max_atk = 0
                max_atk_idx = 0
                for i, card in enumerate(enemy_board):
                    atk = card.get('attack', 0)
                    if atk > max_atk:
                        max_atk = atk
                        max_atk_idx = i
                target_idx = max_atk_idx
                
                # 选择攻击力最高的攻击者
                if len(attackers) > 1:
                    max_atk = 0
                    max_atk_idx = attackers[0]
                    for i in attackers:
                        atk = my_board[i].get('attack', 0)
                        if atk > max_atk:
                            max_atk = atk
                            max_atk_idx = i
                    attacker_idx = max_atk_idx
            else:
                # 普通AI选择第一个
                if len(enemy_board) > 1:
                    # 选择攻击力最高的敌方随从
                    max_atk = 0
                    max_atk_idx = 0
                    for i, card in enumerate(enemy_board):
                        atk = card.get('attack', 0)
                        if atk > max_atk:
                            max_atk = atk
                            max_atk_idx = i
                    target_idx = max_atk_idx
            
            print(f"[AI] 攻击敌方随从")
            self.game.attack(player_name, attacker_idx, target_idx)
            return True
        else:
            # 没有敌方随从，直接攻击英雄
            # 检查攻击英雄是否合理（比如敌方血量低）
            if enemy_health <= 15 or len(attackers) > 0:
                attacker_idx = attackers[0]
                
                # superAI 选择最高攻击力打脸
                if self.difficulty == "superAI" and len(attackers) > 1:
                    max_atk = 0
                    max_atk_idx = attackers[0]
                    for i in attackers:
                        atk = my_board[i].get('attack', 0)
                        if atk > max_atk:
                            max_atk = atk
                            max_atk_idx = i
                    attacker_idx = max_atk_idx
                
                print(f"[AI] 攻击敌方英雄")
                self.game.attack(player_name, attacker_idx, None)
                return True
        
        return False


# AI游戏管理
ai_games = {}
ai_games_lock = threading.Lock()

def create_ai_game(player_name, ai_difficulty="普通AI", player_deck=None):
    """创建AI对战游戏"""
    from ai_decks import ALL_AI_DECKS
    from app import Game, CARDS_MAP, spells
    
    # 获取AI卡组
    ai_deck_info = ALL_AI_DECKS.get(ai_difficulty, ALL_AI_DECKS["普通AI"])
    ai_deck = ai_deck_info["cards"]
    
    # 随机决定谁先手
    import random
    if random.choice([True, False]):
        player1 = player_name
        player2 = "AI"
        deck1 = player_deck
        deck2 = ai_deck
        ai_side = 'enemy'
    else:
        player1 = "AI"
        player2 = player_name
        deck1 = ai_deck
        deck2 = player_deck
        ai_side = 'player'
    
    game_id = f"ai_game_{player_name}_{int(time.time())}"
    
    # 创建游戏实例
    game = Game(game_id, player1, player2, deck1, deck2, CARDS_MAP, spells)
    
    # 创建AI玩家
    ai_player = AIPlayer(ai_difficulty)
    ai_player.set_game(game, ai_side)
    
    with ai_games_lock:
        ai_games[game_id] = {
            'game': game,
            'ai_player': ai_player,
            'player_name': player_name,
            'ai_difficulty': ai_difficulty,
            'ai_side': ai_side,
            'created_at': time.time()
        }
    
    print(f"[AI] 游戏创建成功: {game_id}")
    print(f"[AI] 玩家: {player_name}, AI难度: {ai_difficulty}, AI阵营: {ai_side}")
    
    return game_id, game, ai_player