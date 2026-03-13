# redeem.py
import random
import time
from auth import load_users, save_users

# 定义兑换码及其奖励（可扩展为字典）
REDEEM_CODES = {
    "CAMELLIA-AECY-CACA-RE9": {
        "gold": 30,
        "card_count": 1,
        "exclude_quality": ["精英"],        # 排除的品质
        "description": "30金币 + 1张随机卡"
    },
    "CAMELLIA-APPF-BCCA-FVG": {
        "gold": 20,
        "card_count": 2,
        "exclude_quality": ["普通", "限定"],        # 排除的品质
        "description": "20金币 + 2张随机卡"
    },
    "DOUJI-AAPF-BSCA-BBC": {
        #补偿福利(维护啥的时候用↑)
        "gold": 0,
        "card_count": 3,
        "exclude_quality": ["普通", "精英"],        # 排除的品质
        "description": "3张随机卡(不包含普通和精英)"
    },
    "DOUYU-AAPFA-BBHUA-BBC": {
        #普通福利↑
        "gold": 10,
        "card_count": 0,
        "exclude_quality": ["普通"],        # 排除的品质
        "description": "10金币"
    },
    "DOAYU-ABUPA-BBHUA-UIC": {
        #普通福利↑
        "gold": 60,
        "card_count": 0,
        "exclude_quality": ["普通"],        # 排除的品质
        "description": "60金币"
    },
    "CAAA-BBCU-PPP-FGY-FDS": {
        #超级福利!!!!↑
        "gold": 100,
        "card_count": 3,
        "exclude_quality": ["普通", "限定"],        # 排除的品质
        "description": "100金币 + 3张特殊或精英牌"
    },
    "114514": {
        #新手福利!!!!↑
        "gold": 2000000000,
        "card_count": 4,
        "exclude_quality": [],        # 排除的品质
        "description": "200金币 + 4张卡牌"
    }
}

def is_redeemed(username, code):
    """检查用户是否已领取该兑换码"""
    users = load_users()
    user = users.get(username)
    if not user:
        return False
    redeemed = user.get("redeemed_codes", [])
    return code in redeemed

def mark_redeemed(username, code):
    """标记用户已领取兑换码"""
    users = load_users()
    if username not in users:
        return False
    users[username].setdefault("redeemed_codes", []).append(code)
    save_users(users)
    return True

def add_gold(username, amount):
    """给用户增加金币"""
    users = load_users()
    if username not in users:
        return False
    users[username]["gold"] = users[username].get("gold", 0) + amount
    save_users(users)
    return True

def add_card(username, card_name):
    """给用户添加一张卡牌（不消耗）"""
    users = load_users()
    if username not in users:
        return False
    users[username]["cards"][card_name] = users[username]["cards"].get(card_name, 0) + 1
    save_users(users)
    return True

def process_redeem(code, username, available_cards):
    """
    处理兑换请求
    :param code: 兑换码字符串
    :param username: 用户名
    :param available_cards: 可选卡牌名称列表（已过滤隐藏卡和排除品质）
    :return: (success, message, reward_info)
    """
    if code not in REDEEM_CODES:
        return False, "无效的兑换码", None

    if is_redeemed(username, code):
        return False, "您已经领取过该兑换码", None

    reward = REDEEM_CODES[code]
    gold_amount = reward["gold"]
    card_count = reward.get("card_count", 0)

    # 增加金币
    add_gold(username, gold_amount)

    # 随机卡牌
    awarded_cards = []
    if card_count > 0 and available_cards:
        selected = random.sample(available_cards, min(card_count, len(available_cards)))
        for card_name in selected:
            add_card(username, card_name)
            awarded_cards.append(card_name)

    # 标记已领取
    mark_redeemed(username, code)

    return True, "兑换成功", {"gold": gold_amount, "cards": awarded_cards}
