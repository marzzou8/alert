# ===== IMPORTS =====
from flask import Flask
import threading
import requests
import pandas as pd
import time
import os

# ===== FLASK SERVER =====
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ===== CONFIG =====
OANDA_API = os.getenv("OANDA_API")
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

current_trade = None

# ===== TELEGRAM =====
def send(msg):
    try:
        print("Sending:", msg)
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except Exception as e:
        print("Telegram Error:", e)

# ===== GET DATA =====
def get_data():
    try:
        url = "https://api-fxpractice.oanda.com/v3/instruments/XAU_USD/candles"
        headers = {"Authorization": f"Bearer {OANDA_API}"}
        params = {"granularity": "M1", "count": 100}

        r = requests.get(url, headers=headers, params=params)
        data = r.json()

        if "candles" not in data:
            print("API ERROR:", data)
            return None

        rows = []
        for c in data["candles"]:
            rows.append({
                "close": float(c["mid"]["c"]),
                "high": float(c["mid"]["h"]),
                "low": float(c["mid"]["l"])
            })

        return pd.DataFrame(rows)

    except Exception as e:
        print("Data Error:", e)
        return None

# ===== INDICATORS =====
def add_indicators(df):
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema20'] = df['close'].ewm(span=20).mean()
    return df

# ===== SIGNAL =====
def get_signal(df):
    prev = df.iloc[-2]
    curr = df.iloc[-1]

    # BUY
    if (curr['ema9'] > curr['ema20'] and
        prev['close'] < prev['ema9'] and
        curr['close'] > curr['ema9']):
        return "BUY"

    # SELL
    if (curr['ema9'] < curr['ema20'] and
        prev['close'] > prev['ema9'] and
        curr['close'] < curr['ema9']):
        return "SELL"

    return None

# ===== SL / TP =====
def calculate_sl_tp(entry, signal):
    sl_distance = 10.0

    if signal == "BUY":
        sl = entry - sl_distance
        tp = entry + (sl_distance * 1.5)
    else:
        sl = entry + sl_distance
        tp = entry - (sl_distance * 1.5)

    return round(sl, 2), round(tp, 2)

# ===== MONITOR TRADE =====
def monitor_trade(df):
    global current_trade

    if current_trade is None:
        return

    price = df['close'].iloc[-1]
    entry = current_trade['entry']
    direction = current_trade['type']

    if direction == "BUY":
        move = price - entry
    else:
        move = entry - price

    print(f"Monitoring trade | Move: {move:.2f}")

    # Move to BE at +3
    if move >= 3 and not current_trade["be_sent"]:
        send(f"""
⚡ MOVE SL TO BE
{direction} XAUUSD
Entry: {entry}
""")
        current_trade["be_sent"] = True

# ===== MAIN BOT =====
def run_bot():
    global current_trade

    print("BOT STARTED")
    send("✅ Bot is LIVE")

    while True:
        try:
            print("Bot running...")

            df = get_data()
            if df is None:
                time.sleep(60)
                continue

            df = add_indicators(df)

            # Monitor existing trade
            monitor_trade(df)

            # Only take new trade if none active
            if current_trade is None:
                signal = get_signal(df)

                if signal:
                    entry = df['close'].iloc[-1]
                    sl, tp = calculate_sl_tp(entry, signal)

                    current_trade = {
                        "type": signal,
                        "entry": entry,
                        "sl": sl,
                        "tp": tp,
                        "be_sent": False
                    }

                    send(f"""
🚀 {signal} XAUUSD
Entry: {entry}
SL: {sl}
TP: {tp}
""")

        except Exception as e:
            print("BOT ERROR:", e)

        time.sleep(60)

# ===== START =====
if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    threading.Thread(target=run_bot, daemon=True).start()

    while True:
        time.sleep(60)
