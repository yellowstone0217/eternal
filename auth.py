import json
import os
from werkzeug.security import generate_password_hash, check_password_hash

USER_FILE = 'users.json'

def load_users():
    if not os.path.exists(USER_FILE):
        return {}
    with open(USER_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_users(users):
    with open(USER_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def register(username, password):
    users = load_users()
    if username in users:
        return False, "用户名已存在"
    users[username] = {
        "password_hash": generate_password_hash(password),
        "cards": {},
        "decks": [],
        "shop": {
            "free_card": None,
            "last_refresh": 0
        },
        "gold": 0,                        # 新增金币字段
        "redeemed_codes": []               # 记录已领取的兑换码
    }
    save_users(users)
    return True, "注册成功"

def login(username, password):
    users = load_users()
    if username not in users:
        return False, "用户名不存在"
    if not check_password_hash(users[username]["password_hash"], password):
        return False, "密码错误"
    return True, "登录成功"