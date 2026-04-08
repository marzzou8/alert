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
    print(f"Starting Flask on port {port}")
    app.run(host='0.0.0.0', port=port)

# ===== CONFIG =====
OANDA_API = os.getenv("OANDA_API")
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

last_signal = None

# ===== TELEGRAM =====
def send(msg):
    try:
        print("Sending Telegram:", msg)
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except Exception as e:
        print("Telegram Error:", e)

# ===== GET DATA =====
def get_data():
    try:
        url = "https://api-fxpractice.oanda.com/v3/instruments/XAU_USD/candles"
        headers = {"Authorization": f"Bearer {OANDA_API}"}
        params = {"granularity": "M1", "count": 50}

        r = requests.get(url, headers=headers, params=params)
        data = r.json()

        if "candles" not in data:
            print("API ERROR:", data)
            return None

        prices = [float(c["mid"]["c"]) for c in data["candles"]]
        return pd.DataFrame(prices, columns=["close"])

    except Exception as e:
        print("Data Error:", e)
        return None

# ===== BOT LOOP =====
def run_bot():
    global last_signal

    print(">>> BOT LOOP STARTED <<<")

    # 🔥 TEST MESSAGE (you MUST receive this)
    send("✅ BOT STARTED SUCCESSFULLY")

    while True:
        try:
            print("Bot running...")

            df = get_data()
            if df is None:
                time.sleep(60)
                continue

            ema9 = df['close'].ewm(span=9).mean()
            ema20 = df['close'].ewm(span=20).mean()

            if ema9.iloc[-1] > ema20.iloc[-1]:
                signal = "BUY"
            else:
                signal = "SELL"

            print("Signal:", signal)

            # Only send if changed
            if signal != last_signal:
                send(f"{signal} XAUUSD")
                last_signal = signal

        except Exception as e:
            print("BOT ERROR:", e)

        time.sleep(60)

# ===== SAFE WRAPPER =====
def safe_run_bot():
    try:
        run_bot()
    except Exception as e:
        print("BOT CRASHED:", e)

# ===== START =====
if __name__ == "__main__":
    print("=== STARTING BOT SYSTEM ===")

    # Start Flask
    threading.Thread(target=run_server, daemon=True).start()

    # Start Bot
    threading.Thread(target=safe_run_bot, daemon=True).start()

    # Keep alive
    while True:
        print("MAIN THREAD ALIVE")
        time.sleep(60)
