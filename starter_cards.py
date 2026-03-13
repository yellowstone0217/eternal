STARTER_CARDS = ["智慧电机","黄色菌毯","羽毛笔","轰炸虫","探察者"]

def give_starter_cards(username):
    from auth import load_users, save_users
    users = load_users()
    if username not in users:
        return
    
    # 给予初始卡牌
    for card in STARTER_CARDS:
        users[username]["cards"][card] = users[username]["cards"].get(card, 0) + 2  # 每种给2张
    
    # 创建默认卡组
    if not users[username].get('decks'):
        users[username]['decks'] = [{
            'name': '默认卡组',
            'cards': STARTER_CARDS * 2  # 每种两张，共6张（可根据需要调整）
        }]
    
    save_users(users)