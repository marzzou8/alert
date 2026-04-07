# ===== IMPORTS =====
from flask import Flask
import threading
import requests
import pandas as pd
import time
import os

# ===== FLASK SERVER (FOR RENDER PORT) =====
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running"

def run_server():
    port = int(os.environ.get("PORT", 10000))  # IMPORTANT
    app.run(host='0.0.0.0', port=port)

# ===== ENV VARIABLES =====
OANDA_API = os.getenv("OANDA_API")
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

last_signal = None

# ===== TELEGRAM FUNCTION =====
def send(msg):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except Exception as e:
        print("Telegram Error:", e)

# ===== GET DATA FROM OANDA =====
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

# ===== MAIN BOT LOOP =====
def run_bot():
    global last_signal

    while True:
        print("Bot running...")

        df = get_data()
        if df is None:
            time.sleep(60)
            continue

        # EMA
        df['ema9'] = df['close'].ewm(span=9).mean()
        df['ema20'] = df['close'].ewm(span=20).mean()

        # RSI
        delta = df['close'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        current_signal = None

        if df['ema9'].iloc[-1] > df['ema20'].iloc[-1] and rsi.iloc[-1] > 50:
            current_signal = "BUY"
        elif df['ema9'].iloc[-1] < df['ema20'].iloc[-1] and rsi.iloc[-1] < 50:
            current_signal = "SELL"

        if current_signal and current_signal != last_signal:
            message = f"{current_signal} XAUUSD"
            print("Sending:", message)
            send(message)
            last_signal = current_signal

        time.sleep(60)

# ===== START EVERYTHING =====
if __name__ == "__main__":
    threading.Thread(target=run_server).start()
    run_bot()
