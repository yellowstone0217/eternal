# spells.py
import random
import copy

def is_spell_card(card):
    """判断是否为技能牌"""
    return card.get('type') == 'spell'

def get_spell_target_type(card):
    """
    获取技能牌的目标类型：
    - 'none': 无指向，直接生效
    - 'minion': 指向随从
    - 'hero': 指向英雄
    """
    # 石油需要 - 无指向
    if card.get('name') == '石油需要':
        return 'none'
    
    # 战争需要 - 无指向
    if card.get('name') == '战争需要':
        return 'none'
    
    # 战争债券 - 无指向
    if card.get('name') == '战争债券':
        return 'none'
    
    # 反潜巡逻 - 无指向（随机消灭）
    if card.get('name') == '反潜巡逻':
        return 'none'
    
    # 仔细生产 - 无指向
    if card.get('name') == '仔细生产':
        return 'none'
    
    # 坚固防线 - 指向随从（+1/+1）
    if card.get('name') == '坚固防线':
        return 'minion'
    
    effect = card.get('effect', [])
    # 根据效果名称判断
    if '对目标随从打3' in effect:
        return 'minion'
    if '对敌方英雄打2' in effect:
        return 'hero'
    if '对己方英雄回2血' in effect:
        return 'hero'
    if '造成2点伤害，抽一张牌' in effect:
        return 'minion'
    if '沉默一个随从' in effect:
        return 'minion'
    if '冻结一个随从' in effect:
        return 'minion'
    if '使己方卡组所有单位获得+1血量' in effect:
        return 'none'
    # 默认无指向
    return 'none'

def apply_spell_effect(game, card, caster, target=None):
    """
    应用技能效果
    :param game: Game实例
    :param card: 技能牌数据
    :param caster: 'player' 或 'enemy'
    :param target: 目标索引（对于指向型）
    :return: 返回使用的卡牌信息，用于前端显示（敌方使用时）
    """
    print(f"\n========== 应用法术效果 ==========")
    print(f"法术名称: {card.get('name')}")
    print(f"施法者: {caster}")
    print(f"目标索引: {target}")
    print(f"卡牌类型: {card.get('type')}")
    
    effect = card.get('effect', [])
    if effect:
        print(f"法术效果: {effect}")
    else:
        print("法术牌没有立即生效的效果（可能是抽到时触发）")
    
    # 获取施法者名称
    caster_name = game.player1 if caster == 'player' else game.player2
    
    # 只在敌方使用卡牌时记录卡牌信息
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

    # ===== 第一步：如果有效果，处理法术本身的效果 =====
    if effect:
        print("开始处理法术效果...")
        for eff in effect:
            print(f"处理效果: {eff}")
            
            # 抽牌效果
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
                        import random
                        discard_index = random.randint(0, len(game.enemy_hand) - 1)
                        discarded = game.enemy_hand.pop(discard_index)
                        game._set_message(f"敌方弃掉 {discarded.get('name')}")
                else:
                    if game.player_hand:
                        import random
                        discard_index = random.randint(0, len(game.player_hand) - 1)
                        discarded = game.player_hand.pop(discard_index)
                        game._set_message(f"你被弃掉 {discarded.get('name')}")
                        
            # 所有随从获得+1/+1
            elif eff == '所有随从获得+1/+1':
                if caster == 'player':
                    for card in game.player_board:
                        card['attack'] = card.get('attack', 0) + 1
                        card['health'] = card.get('health', 0) + 1
                    game._set_message("你的所有随从获得+1/+1")
                else:
                    for card in game.enemy_board:
                        card['attack'] = card.get('attack', 0) + 1
                        card['health'] = card.get('health', 0) + 1
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
                        
            # 发现一张牌
            elif eff == '发现一张牌':
                game._set_message("触发发现效果")
                
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
    
    # ===== 第二步：特殊卡牌效果 - 通过名称判定 =====
    
    # ===== 石油需要 - 获得1个指挥点槽 =====
    if card.get('name') == '石油需要':
        print("✓ 检测到特殊卡牌: 石油需要")
        if caster == 'player':
            # 增加玩家当前回合的指挥槽
            if game.player_max_commander_slot < 24:
                game.player_max_commander_slot += 1
                print(f"玩家最大指挥槽增加至 {game.player_max_commander_slot}")
            game.player_commander_slot += 1
            game._set_message("使用石油需要，指挥槽+1！")
            print(f"玩家指挥槽增加，当前: {game.player_commander_slot}/{game.player_max_commander_slot}")
        else:
            # 敌方使用，增加敌方的指挥槽
            if game.enemy_max_commander_slot < 24:
                game.enemy_max_commander_slot += 1
                print(f"敌方最大指挥槽增加至 {game.enemy_max_commander_slot}")
            game.enemy_commander_slot += 1
            game._set_message("敌方使用石油需要，敌方指挥槽+1！")
            print(f"敌方指挥槽增加，当前: {game.enemy_commander_slot}/{game.enemy_max_commander_slot}")
    
    # ===== 战争需要 - 获得2个指挥点槽 =====
    if card.get('name') == '战争需要':
        print("✓ 检测到特殊卡牌: 战争需要")
        if caster == 'player':
            # 增加玩家当前回合的指挥槽
            max_increase = 0
            for _ in range(2):
                if game.player_max_commander_slot < 24:
                    game.player_max_commander_slot += 1
                    max_increase += 1
            game.player_commander_slot += 2
            game._set_message("使用战争需要，指挥槽+2！")
            print(f"玩家指挥槽增加，当前: {game.player_commander_slot}/{game.player_max_commander_slot} (最大增加: {max_increase})")
        else:
            # 敌方使用，增加敌方的指挥槽
            max_increase = 0
            for _ in range(2):
                if game.enemy_max_commander_slot < 24:
                    game.enemy_max_commander_slot += 1
                    max_increase += 1
            game.enemy_commander_slot += 2
            game._set_message("敌方使用战争需要，敌方指挥槽+2！")
            print(f"敌方指挥槽增加，当前: {game.enemy_commander_slot}/{game.enemy_max_commander_slot} (最大增加: {max_increase})")
    
    # ===== 战争债券 - 获得2个指挥点槽，下个友方回合开始时额外抽一张牌 =====
    if card.get('name') == '战争债券':
        print("✓ 检测到特殊卡牌: 战争债券")
        if caster == 'player':
            # 增加玩家当前回合的指挥槽
            max_increase = 0
            for _ in range(2):
                if game.player_max_commander_slot < 24:
                    game.player_max_commander_slot += 1
                    max_increase += 1
            game.player_commander_slot += 2
            
            # 设置延迟抽牌标记 - 使用字典直接赋值，确保存在
            if not hasattr(game, 'delayed_draw'):
                game.delayed_draw = {}
                print("[战争债券] 初始化 delayed_draw 字典")
            
            # 确保player键存在
            if 'player' not in game.delayed_draw:
                game.delayed_draw['player'] = 0
                print("[战争债券] 初始化 player 键")
            
            # 增加延迟抽牌计数
            game.delayed_draw['player'] += 1
            print(f"✓ 战争债券延迟抽牌已设置: player={game.delayed_draw['player']}")
            print(f"✓ game.delayed_draw 内容: {game.delayed_draw}")
            
            game._set_message("使用战争债券，指挥槽+2！下个友方回合开始时额外抽一张牌")
            print(f"玩家指挥槽增加，当前: {game.player_commander_slot}/{game.player_max_commander_slot} (最大增加: {max_increase})")
        else:
            # 敌方使用，增加敌方的指挥槽
            max_increase = 0
            for _ in range(2):
                if game.enemy_max_commander_slot < 24:
                    game.enemy_max_commander_slot += 1
                    max_increase += 1
            game.enemy_commander_slot += 2
            
            # 设置延迟抽牌标记 - 使用字典直接赋值，确保存在
            if not hasattr(game, 'delayed_draw'):
                game.delayed_draw = {}
                print("[战争债券] 初始化 delayed_draw 字典")
            
            # 确保enemy键存在
            if 'enemy' not in game.delayed_draw:
                game.delayed_draw['enemy'] = 0
                print("[战争债券] 初始化 enemy 键")
            
            # 增加延迟抽牌计数
            game.delayed_draw['enemy'] += 1
            print(f"✓ 敌方战争债券延迟抽牌已设置: enemy={game.delayed_draw['enemy']}")
            print(f"✓ game.delayed_draw 内容: {game.delayed_draw}")
            
            game._set_message("敌方使用战争债券，敌方指挥槽+2！敌方下个回合开始时额外抽一张牌")
            print(f"敌方指挥槽增加，当前: {game.enemy_commander_slot}/{game.enemy_max_commander_slot} (最大增加: {max_increase})")
    
    # ===== 反潜巡逻 - 获得2个指挥点槽，随机消灭一个敌方单位（造成1000点伤害） =====
    if card.get('name') == '反潜巡逻':
        print("✓ 检测到特殊卡牌: 反潜巡逻")
        if caster == 'player':
            # 增加玩家当前回合的指挥槽
            max_increase = 0
            for _ in range(2):
                if game.player_max_commander_slot < 24:
                    game.player_max_commander_slot += 1
                    max_increase += 1
            game.player_commander_slot += 2
            
            # 随机消灭一个敌方单位（造成1000点伤害）- 只消灭一个，不是所有
            if game.enemy_board and len(game.enemy_board) > 0:
                import random
                # 复制当前敌方随从列表，避免在迭代中修改
                enemy_board_copy = game.enemy_board[:]
                target_index = random.randint(0, len(enemy_board_copy) - 1)
                target_card = enemy_board_copy[target_index]
                target_name = target_card.get('name', '未知随从')
                
                # 找到这个目标在原始列表中的索引
                original_index = -1
                for i, card in enumerate(game.enemy_board):
                    if card.get('name') == target_name and card.get('health') == target_card.get('health'):
                        original_index = i
                        break
                
                if original_index >= 0:
                    # 造成1000点伤害（相当于消灭）
                    game.enemy_board[original_index]['health'] -= 1000
                    print(f"对敌方随从 {target_name} 造成1000点伤害")
                    
                    # 移除死亡的随从
                    if game.enemy_board[original_index]['health'] <= 0:
                        game.enemy_board.pop(original_index)
                        game._set_message(f"使用反潜巡逻，随机消灭敌方 {target_name}！")
                    else:
                        game._set_message(f"使用反潜巡逻，对敌方 {target_name} 造成1000点伤害")
                else:
                    game._set_message("使用反潜巡逻，但无法找到目标")
            else:
                game._set_message("使用反潜巡逻，但敌方场上没有随从")
            
            print(f"玩家指挥槽增加，当前: {game.player_commander_slot}/{game.player_max_commander_slot} (最大增加: {max_increase})")
        else:
            # 敌方使用，增加敌方的指挥槽
            max_increase = 0
            for _ in range(2):
                if game.enemy_max_commander_slot < 24:
                    game.enemy_max_commander_slot += 1
                    max_increase += 1
            game.enemy_commander_slot += 2
            
            # 随机消灭一个玩家单位（造成1000点伤害）- 只消灭一个，不是所有
            if game.player_board and len(game.player_board) > 0:
                import random
                # 复制当前玩家随从列表，避免在迭代中修改
                player_board_copy = game.player_board[:]
                target_index = random.randint(0, len(player_board_copy) - 1)
                target_card = player_board_copy[target_index]
                target_name = target_card.get('name', '未知随从')
                
                # 找到这个目标在原始列表中的索引
                original_index = -1
                for i, card in enumerate(game.player_board):
                    if card.get('name') == target_name and card.get('health') == target_card.get('health'):
                        original_index = i
                        break
                
                if original_index >= 0:
                    # 造成1000点伤害（相当于消灭）
                    game.player_board[original_index]['health'] -= 1000
                    print(f"对玩家随从 {target_name} 造成1000点伤害")
                    
                    # 移除死亡的随从
                    if game.player_board[original_index]['health'] <= 0:
                        game.player_board.pop(original_index)
                        game._set_message(f"敌方使用反潜巡逻，随机消灭你的 {target_name}！")
                    else:
                        game._set_message(f"敌方使用反潜巡逻，对你的 {target_name} 造成1000点伤害")
                else:
                    game._set_message("敌方使用反潜巡逻，但无法找到目标")
            else:
                game._set_message("敌方使用反潜巡逻，但你场上没有随从")
            
            print(f"敌方指挥槽增加，当前: {game.enemy_commander_slot}/{game.enemy_max_commander_slot} (最大增加: {max_increase})")
    
    # ===== 仔细生产 - 使卡组里所有单位获得+1攻击力 =====
    if card.get('name') == '仔细生产':
        print("✓ 检测到特殊卡牌: 仔细生产")
        if caster == 'player':
            # 增加玩家卡组中所有单位的攻击力
            attack_bonus = 0
            for card_in_deck in game.player_deck:
                if 'attack' in card_in_deck:  # 只给有攻击力的单位牌加
                    old_attack = card_in_deck.get('attack', 0)
                    card_in_deck['attack'] = old_attack + 1
                    if 'original_attack' in card_in_deck:
                        card_in_deck['original_attack'] = card_in_deck.get('original_attack', 0) + 1
                    attack_bonus += 1
            game._set_message(f"使用仔细生产，卡组中所有单位获得+1攻击力（共{attack_bonus}张卡牌受影响）")
            print(f"玩家卡组攻击力增加，共影响了 {attack_bonus} 张单位牌")
        else:
            # 敌方使用，增加敌方卡组中所有单位的攻击力
            attack_bonus = 0
            for card_in_deck in game.enemy_deck:
                if 'attack' in card_in_deck:  # 只给有攻击力的单位牌加
                    old_attack = card_in_deck.get('attack', 0)
                    card_in_deck['attack'] = old_attack + 1
                    if 'original_attack' in card_in_deck:
                        card_in_deck['original_attack'] = card_in_deck.get('original_attack', 0) + 1
                    attack_bonus += 1
            game._set_message(f"敌方使用仔细生产，敌方卡组中所有单位获得+1攻击力")
            print(f"敌方卡组攻击力增加，共影响了 {attack_bonus} 张单位牌")
    
    # ===== 坚固防线 - 使一个单位获得+1/+1 (修复版：支持攻击过的单位) =====
    if card.get('name') == '坚固防线':
        print("✓ 检测到特殊卡牌: 坚固防线")
        print(f"目标索引: {target}")
        print(f"施法者: {caster}")
        
        # 检查目标是否存在
        if target is None:
            print("错误：目标索引为 None")
            game._set_message("坚固防线需要选择目标")
            return used_card_info
        
        # 确定是哪个玩家的随从可以获得buff
        if caster == 'player':
            # 玩家使用，目标应该是玩家场上的随从
            if 0 <= target < len(game.player_board):
                target_card = game.player_board[target]
                
                # 检查随从是否存在（即使攻击过也能获得buff）
                if target_card:
                    old_attack = target_card.get('attack', 0)
                    old_health = target_card.get('health', 0)
                    
                    # 增加攻击力和生命值
                    target_card['attack'] = old_attack + 1
                    target_card['health'] = old_health + 1
                    
                    # 更新原始值（如果有）
                    if 'original_attack' in target_card:
                        target_card['original_attack'] = target_card.get('original_attack', 0) + 1
                    if 'original_health' in target_card:
                        target_card['original_health'] = target_card.get('original_health', 0) + 1
                    
                    # 保持can_attack状态不变（如果已经攻击过，保持False）
                    # 不需要修改can_attack，让随从保持原有的攻击状态
                    
                    game._set_message(f"使用坚固防线，{target_card.get('name')} 获得+1/+1")
                    print(f"目标随从 {target_card.get('name')} 属性变化: 攻击 {old_attack}->{target_card['attack']}, 生命 {old_health}->{target_card['health']}")
                    print(f"随从攻击状态保持不变: can_attack={target_card.get('can_attack', False)}")
                else:
                    print(f"错误：目标随从不存在")
                    game._set_message("坚固防线目标无效")
            else:
                print(f"错误：无效的目标索引 {target}，玩家场上有 {len(game.player_board)} 个随从")
                game._set_message("坚固防线目标无效")
        else:
            # 敌方使用，目标应该是敌方场上的随从
            if 0 <= target < len(game.enemy_board):
                target_card = game.enemy_board[target]
                
                # 检查随从是否存在（即使攻击过也能获得buff）
                if target_card:
                    old_attack = target_card.get('attack', 0)
                    old_health = target_card.get('health', 0)
                    
                    # 增加攻击力和生命值
                    target_card['attack'] = old_attack + 1
                    target_card['health'] = old_health + 1
                    
                    # 更新原始值（如果有）
                    if 'original_attack' in target_card:
                        target_card['original_attack'] = target_card.get('original_attack', 0) + 1
                    if 'original_health' in target_card:
                        target_card['original_health'] = target_card.get('original_health', 0) + 1
                    
                    # 保持can_attack状态不变（如果已经攻击过，保持False）
                    
                    game._set_message(f"敌方使用坚固防线，敌方 {target_card.get('name')} 获得+1/+1")
                    print(f"敌方目标随从 {target_card.get('name')} 属性变化: 攻击 {old_attack}->{target_card['attack']}, 生命 {old_health}->{target_card['health']}")
                    print(f"随从攻击状态保持不变: can_attack={target_card.get('can_attack', False)}")
                else:
                    print(f"错误：敌方目标随从不存在")
                    game._set_message("敌方坚固防线目标无效")
            else:
                print(f"错误：无效的目标索引 {target}，敌方场上有 {len(game.enemy_board)} 个随从")
                game._set_message("敌方坚固防线目标无效")
    
    # ===== 检查使用的卡牌是否是法术牌，如果是则触发所有机枪机甲 =====
    # 判断卡牌类型是否为'spell'
    if card.get('type') == 'spell':
        print(f"✓ 检测到使用了法术牌: {card.get('name')}，触发场上所有机枪机甲效果")
        trigger_all_machinegun_mechs(game, caster)
    else:
        print(f"✗ 使用的不是法术牌 (类型: {card.get('type')})，不触发机枪机甲")
    # ============================================================
    
    print("========== 应用法术效果完成 ==========\n")
    
    # 返回敌方使用的法术信息
    return used_card_info

def apply_draw_effect(game, card, drawer):
    """
    处理抽到时触发的抽取效果
    :param game: Game实例
    :param card: 抽到的卡牌
    :param drawer: 'player' 或 'enemy'
    """
    effect = card.get('effect', [])
    if not effect:
        return

    # 抽取效果通常是一个独立的列表，检查效果中是否包含特定标记
    draw_triggered = [e for e in effect if e.startswith('抽到时：')]
    for trigger in draw_triggered:
        # 提取具体效果
        if '对友方角色造成1点伤害' in trigger:
            if drawer == 'player':
                # 对玩家所有友方角色造成伤害？这里简单对玩家英雄造成1点
                game.player_health -= 1
                game.message = "抽到时：你对己方英雄造成1点伤害"
            else:
                game.enemy_health -= 1
                game.message = "抽到时：敌方对己方英雄造成1点伤害"
            # 再抽一张牌（注意避免无限递归）
            game.draw_card(1, is_player=(drawer == 'player'))
        # 可以添加更多抽取效果
    
    # 标记已触发，防止多次触发
    if '抽到时' in card:
        card['draw_triggered'] = True
        
def trigger_all_machinegun_mechs(game, caster):
    """
    触发场上的所有机枪机甲效果（修复：多个机甲都会触发）
    友方使用指令（法术）时，每个机甲随机对一个敌方目标造成1点伤害
    """
    print(f"\n========== 触发所有机枪机甲效果 ==========")
    print(f"施法者: {caster}")
    print(f"使用了法术牌，触发场上所有机枪机甲（每个独立触发）")
    
    # 确定哪一方的机枪机甲要触发
    if caster == 'player':
        # 玩家使用法术，检查玩家场上的所有机枪机甲
        print(f"检查玩家场上的机枪机甲...")
        mechs = [card for card in game.player_board if card.get('name') == '等离子机枪机甲']
        print(f"找到玩家场上的等离子机枪机甲数量: {len(mechs)}")
        
        if not mechs:
            print("玩家场上没有等离子机枪机甲，不触发效果")
            return
        
        # 获取敌方目标列表（英雄 + 随从）
        targets = []
        targets.append('hero')  # 敌方英雄
        for i in range(len(game.enemy_board)):
            targets.append(i)   # 敌方随从索引
        
        if not targets:
            print("没有可攻击的目标，返回")
            return
        
        # 每个机甲独立触发一次
        import random
        for i, mech in enumerate(mechs):
            print(f"机甲 #{i+1} 触发效果...")
            
            # 随机选择一个目标
            selected = random.choice(targets)
            print(f"  随机选择的目标: {selected}")
            
            # 造成1点伤害
            if selected == 'hero':
                game.enemy_health = max(0, game.enemy_health - 1)
                print(f"  对敌方英雄造成1点伤害，敌方血量: {game.enemy_health}")
                game._set_message(f"等离子机枪机甲 #{i+1} 对敌方英雄造成1点伤害")
            else:
                target_index = selected
                target_card = game.enemy_board[target_index]
                target_card['health'] -= 1
                print(f"  对敌方随从 {target_card.get('name')} 造成1点伤害")
                game._set_message(f"等离子机枪机甲 #{i+1} 对 {target_card.get('name')} 造成1点伤害")
                
                # 检查目标是否死亡
                if target_card['health'] <= 0:
                    game.enemy_board.pop(target_index)
                    # 重要：移除后需要更新目标列表
                    # 重新构建目标列表
                    targets = ['hero']
                    for j in range(len(game.enemy_board)):
                        targets.append(j)
                    print(f"  目标 {target_card.get('name')} 被消灭，更新目标列表")
                
    else:  # caster == 'enemy'
        # 敌方使用法术，检查敌方场上的所有机枪机甲
        print(f"检查敌方场上的机枪机甲...")
        mechs = [card for card in game.enemy_board if card.get('name') == '等离子机枪机甲']
        print(f"找到敌方场上的等离子机枪机甲数量: {len(mechs)}")
        
        if not mechs:
            print("敌方场上没有等离子机枪机甲，不触发效果")
            return
        
        # 获取玩家方目标列表（英雄 + 随从）
        targets = []
        targets.append('hero')  # 玩家英雄
        for i in range(len(game.player_board)):
            targets.append(i)   # 玩家随从索引
        
        if not targets:
            print("没有可攻击的目标，返回")
            return
        
        # 每个机甲独立触发一次
        import random
        for i, mech in enumerate(mechs):
            print(f"敌方机甲 #{i+1} 触发效果...")
            
            # 随机选择一个目标
            selected = random.choice(targets)
            print(f"  随机选择的目标: {selected}")
            
            # 造成1点伤害
            if selected == 'hero':
                game.player_health = max(0, game.player_health - 1)
                print(f"  对玩家英雄造成1点伤害，玩家血量: {game.player_health}")
                game._set_message(f"敌方等离子机枪机甲 #{i+1} 对你的英雄造成1点伤害")
            else:
                target_index = selected
                target_card = game.player_board[target_index]
                target_card['health'] -= 1
                print(f"  对玩家随从 {target_card.get('name')} 造成1点伤害")
                game._set_message(f"敌方等离子机枪机甲 #{i+1} 对你的 {target_card.get('name')} 造成1点伤害")
                
                # 检查目标是否死亡
                if target_card['health'] <= 0:
                    game.player_board.pop(target_index)
                    # 重要：移除后需要更新目标列表
                    # 重新构建目标列表
                    targets = ['hero']
                    for j in range(len(game.player_board)):
                        targets.append(j)
                    print(f"  目标 {target_card.get('name')} 被消灭，更新目标列表")
    
    print("========== 所有机枪机甲效果触发完成 ==========\n")