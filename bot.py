# ===== IMPORTS =====
from flask import Flask
import threading
import requests
import pandas as pd
import time
import os
from datetime import datetime, timedelta

# ===== FLASK SERVER (FOR RENDER) =====
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

last_signal = None

# ===== TELEGRAM =====
def send(msg):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except Exception as e:
        print("Telegram Error:", e)

# ===== TIME FILTER (SGT) =====
def is_trading_time():
    now = datetime.utcnow() + timedelta(hours=8)  # SGT
    return 15 <= now.hour < 21  # 3PM–9PM

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
def calculate_indicators(df):
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema20'] = df['close'].ewm(span=20).mean()

    # RSI
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # Bollinger
    df['ma'] = df['close'].rolling(20).mean()
    df['std'] = df['close'].rolling(20).std()
    df['upper'] = df['ma'] + (df['std'] * 2)
    df['lower'] = df['ma'] - (df['std'] * 2)

    return df

# ===== SIGNAL =====
def get_signal(df):
    latest = df.iloc[-1]

    # BUY
    if (latest['ema9'] > latest['ema20'] and
        latest['rsi'] > 50 and
        latest['close'] <= latest['ma']):
        return "BUY"

    # SELL
    if (latest['ema9'] < latest['ema20'] and
        latest['rsi'] < 50 and
        latest['close'] >= latest['ma']):
        return "SELL"

    return None

# ===== SL / TP =====
def calculate_sl_tp(df, signal):
    latest = df.iloc[-1]
    entry = latest['close']

    lookback = 10
    buffer = 0.5  # important for gold

    recent_low = df['low'].rolling(lookback).min().iloc[-1]
    recent_high = df['high'].rolling(lookback).max().iloc[-1]

    if signal == "BUY":
        sl = recent_low - buffer
        risk = entry - sl
        tp = entry + (risk * 1.5)

    else:
        sl = recent_high + buffer
        risk = sl - entry
        tp = entry - (risk * 1.5)

    return round(entry, 2), round(sl, 2), round(tp, 2)

# ===== MAIN BOT =====
def run_bot():
    global last_signal

    while True:
        print("Bot running...")

        if not is_trading_time():
            print("Outside trading hours")
            time.sleep(60)
            continue

        df = get_data()
        if df is None:
            time.sleep(60)
            continue

        df = calculate_indicators(df)

        signal = get_signal(df)

        if signal and signal != last_signal:
            entry, sl, tp = calculate_sl_tp(df, signal)

            message = f"""
{signal} XAUUSD
Entry: {entry}
SL: {sl}
TP: {tp}
"""

            print("Sending:", message)
            send(message)

            last_signal = signal

        time.sleep(60)

# ===== START =====
if __name__ == "__main__":
    # Start Flask server
    threading.Thread(target=run_server).start()

    # Start bot in separate thread
    threading.Thread(target=run_bot).start()

    # Keep main thread alive
    while True:
        time.sleep(60)
