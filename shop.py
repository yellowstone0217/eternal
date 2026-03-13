# shop.py
import time
import random
import json
from auth import load_users, save_users

with open('cards.json', 'r', encoding='utf-8') as f:
    CARDS = json.load(f)

def get_cards_by_quality(quality):
    return [c for c in CARDS if c.get('quality') == quality and c.get('visible', True)]

def refresh_shop(username):
    users = load_users()
    if username not in users:
        return None
    
    user = users[username]
    now = time.time()
    last_refresh = user['shop']['last_refresh']
    
    # 如果未到20分钟，返回当前免费卡
    if now - last_refresh < 1200:
        return user['shop']['free_card']
    
    # 随机抽取
    r = random.random() * 100
    if r < 2:  # 2% 精英
        quality = '精英'
    elif r < 14:  # 12% 特殊
        quality = '特殊'
    else:  # 86% 普通或限定（各43%？实际各43%总86%）
        quality = random.choice(['普通', '限定'])
    
    candidates = get_cards_by_quality(quality)
    if not candidates:
        # 降级
        quality = '普通'
        candidates = get_cards_by_quality('普通')
    
    free_card = random.choice(candidates)['name'] if candidates else None
    
    # 更新商店
    user['shop']['free_card'] = free_card
    user['shop']['last_refresh'] = now
    save_users(users)
    
    return free_card

def claim_free_card(username):
    users = load_users()
    if username not in users:
        return False
    
    user = users[username]
    free_card = user['shop']['free_card']
    if not free_card:
        return False
    
    # 添加到用户卡牌
    user['cards'][free_card] = user['cards'].get(free_card, 0) + 1
    # 清除免费卡（下次刷新时重新生成）
    user['shop']['free_card'] = None
    save_users(users)
    
    return True
    
    
def get_random_card_by_quality(quality, exclude_hidden=True):
    """从指定品质的卡牌中随机选择一张（排除隐藏卡）"""
    candidates = [c for c in CARDS if c.get('quality') == quality and (not exclude_hidden or not c.get('hidden', False))]
    if not candidates:
        return None
    return random.choice(candidates)['name']

def purchase_random_pack(username):
    """购买随机礼包，消耗20金币，获得1张普通和1张限定/特殊卡"""
    users = load_users()
    if username not in users:
        return False, "用户不存在", None

    user = users[username]
    gold = user.get('gold', 0)
    if gold < 20:
        return False, "金币不足", None

    # 获取普通卡
    common_card = get_random_card_by_quality('普通')
    # 随机选择限定或特殊品质
    rare_quality = random.choice(['限定', '特殊'])
    rare_card = get_random_card_by_quality(rare_quality)

    if not common_card or not rare_card:
        return False, "卡池中没有足够的卡牌", None

    # 扣除金币
    user['gold'] = gold - 20
    # 添加卡牌
    user['cards'][common_card] = user['cards'].get(common_card, 0) + 1
    user['cards'][rare_card] = user['cards'].get(rare_card, 0) + 1

    save_users(users)

    reward = {
        'cards': [common_card, rare_card],
        'gold_cost': 20
    }
    return True, "购买成功", reward