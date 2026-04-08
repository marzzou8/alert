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

last_signal = None

# ===== TELEGRAM =====
def send(msg):
    try:
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
    df['upper'] = df['ma'] + 2 * df['std']
    df['lower'] = df['ma'] - 2 * df['std']

    return df

# ===== SIGNAL (BALANCED VERSION) =====
def get_signal(df):
    prev = df.iloc[-2]
    curr = df.iloc[-1]

    # BUY (trend + momentum)
    if (curr['ema9'] > curr['ema20'] and
        curr['rsi'] > 50 and
        prev['close'] <= prev['ma'] and
        curr['close'] > curr['ma']):
        return "BUY"

    # SELL
    if (curr['ema9'] < curr['ema20'] and
        curr['rsi'] < 50 and
        prev['close'] >= prev['ma'] and
        curr['close'] < curr['ma']):
        return "SELL"

    return None

# ===== SL / TP =====
def calculate_sl_tp(df, signal):
    entry = df['close'].iloc[-1]

    lookback = 10
    buffer = 0.5

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

# ===== BOT LOOP =====
def run_bot():
    global last_signal

    print("BOT LOOP STARTED")

    while True:
        print("Bot running...")

        df = get_data()
        if df is None:
            time.sleep(60)
            continue

        df = add_indicators(df)

        signal = get_signal(df)

        print("Signal:", signal)

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
    print("STARTING BOT...")

    threading.Thread(target=run_server).start()
    threading.Thread(target=run_bot).start()

    while True:
        time.sleep(60)
