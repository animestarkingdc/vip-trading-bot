import telebot
import requests
import sqlite3
from flask import Flask, request, jsonify
import threading, time, json, hmac, hashlib
from datetime import datetime, timedelta

# ========= CONFIG =========
BOT_TOKEN = "YOUR_BOT_TOKEN"
CHANNEL_ID = -100XXXXXXXXXX
ADMIN_ID = 123456789
SECRET_KEY = "supersecret"
PAYSTACK_SECRET = "YOUR_PAYSTACK_SECRET"

SYMBOLS = ["XAUUSDT"]

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ========= DATABASE =========
conn = sqlite3.connect("data.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, expiry TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS signals (id INTEGER PRIMARY KEY, symbol TEXT, side TEXT, price REAL, time TEXT)")
conn.commit()

# ========= MARKET =========
def get_price():
    try:
        res = requests.get("https://api.gold-api.com/price/XAUUSD").json()
        return float(res["price"])
    except:
        return 0

# ========= SIGNAL =========
def generate():
    price = get_price()

    if price == 0:
        return None

    # Simple logic (can upgrade later)
    if int(price) % 2 == 0:
        side = "BUY"
        sl = price - 5
        tp1 = price + 7
        tp2 = price + 15
    else:
        side = "SELL"
        sl = price + 5
        tp1 = price - 7
        tp2 = price - 15

    return "XAUUSD", side, price, sl, tp1, tp2

# ========= SEND =========
def send(sig):
    symbol, side, price, sl, tp1, tp2 = sig

    msg = f"""🔥 {symbol} {side} @{price}

SL: {round(sl,2)}
TP1: {round(tp1,2)}
TP2: {round(tp2,2)}

⚡ Auto Signal"""

    bot.send_message(CHANNEL_ID, msg)

    cur.execute("INSERT INTO signals(symbol,side,price,time) VALUES(?,?,?,?)",
                (symbol, side, price, str(datetime.now())))
    conn.commit()

# ========= AUTO BOT =========
def trader():
    while True:
        sig = generate()
        if sig:
            send(sig)
        time.sleep(600)

# ========= TELEGRAM =========
@bot.message_handler(commands=['start'])
def start(msg):
    uid = msg.from_user.id

    cur.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    user = cur.fetchone()

    if user:
        expiry = datetime.fromisoformat(user[1])
        if datetime.now() < expiry:
            bot.reply_to(msg, "💎 VIP ACTIVE")
        else:
            bot.reply_to(msg, "❌ VIP expired")
    else:
        bot.reply_to(msg, "❌ Not VIP. Pay to join.")

# ========= PAYSTACK WEBHOOK =========
@app.route('/paystack-webhook', methods=['POST'])
def paystack_webhook():
    signature = request.headers.get('x-paystack-signature')
    payload = request.data

    computed = hmac.new(
        PAYSTACK_SECRET.encode(),
        payload,
        hashlib.sha512
    ).hexdigest()

    if signature != computed:
        return "Invalid", 403

    event = json.loads(payload)

    if event['event'] == 'charge.success':
        data = event['data']
        telegram_id = data['metadata']['telegram_id']

        expiry = datetime.now() + timedelta(days=30)

        cur.execute("INSERT OR REPLACE INTO users VALUES(?,?)",
                    (telegram_id, expiry))
        conn.commit()

        invite = bot.create_chat_invite_link(CHANNEL_ID)

        bot.send_message(telegram_id,
            f"💎 VIP Activated!\nJoin here:\n{invite.invite_link}")

    return "OK", 200

# ========= DASHBOARD =========
@app.route('/')
def dash():
    users = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    signals = cur.execute("SELECT COUNT(*) FROM signals").fetchone()[0]

    return f"""
    <h1>VIP PANEL</h1>
    <p>Users: {users}</p>
    <p>Signals Sent: {signals}</p>
    """

# ========= RUN =========
threading.Thread(target=bot.polling).start()
threading.Thread(target=trader).start()
app.run(host="0.0.0.0", port=5000)