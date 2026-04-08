# ===== IMPORTS =====
from flask import Flask
import threading
import requests
import pandas as pd
import time
import os

# ===== FLASK =====
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot running"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ===== CONFIG =====
OANDA_API = os.getenv("OANDA_API")
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

last_signal_time = 0

# ===== TELEGRAM =====
def send(msg):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except:
        pass

# ===== DATA =====
def get_data():
    url = "https://api-fxpractice.oanda.com/v3/instruments/XAU_USD/candles"
    headers = {"Authorization": f"Bearer {OANDA_API}"}
    params = {"granularity": "M1", "count": 150}

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

    return df

# ===== MARKET FILTER =====
def trending(df):
    # Avoid sideways market
    return abs(df['ema9'].iloc[-1] - df['ema20'].iloc[-1]) > 0.3

# ===== SIGNAL =====
def get_signal(df):
    prev = df.iloc[-2]
    curr = df.iloc[-1]

    # BUY (trend + pullback)
    if (curr['ema9'] > curr['ema20'] and
        prev['close'] < prev['ema9'] and
        curr['close'] > curr['ema9'] and
        curr['rsi'] > 50):
        return "BUY"

    # SELL
    if (curr['ema9'] < curr['ema20'] and
        prev['close'] > prev['ema9'] and
        curr['close'] < curr['ema9'] and
        curr['rsi'] < 50):
        return "SELL"

    return None

# ===== SL / TP =====
def calculate_sl_tp(df, signal):
    entry = df['close'].iloc[-1]

    lookback = 10
    buffer = 0.5

    low = df['low'].rolling(lookback).min().iloc[-1]
    high = df['high'].rolling(lookback).max().iloc[-1]

    if signal == "BUY":
        sl = low - buffer
        risk = entry - sl
        tp = entry + (risk * 1.5)
    else:
        sl = high + buffer
        risk = sl - entry
        tp = entry - (risk * 1.5)

    return round(entry,2), round(sl,2), round(tp,2)

# ===== BOT =====
def run_bot():
    global last_signal_time

    send("🚀 Prop Bot Started")

    while True:
        try:
            df = get_data()
            if df is None:
                time.sleep(60)
                continue

            df = add_indicators(df)

            if not trending(df):
                print("Sideways market - skip")
                time.sleep(60)
                continue

            signal = get_signal(df)

            now = time.time()

            if signal and (now - last_signal_time > 300):
                entry, sl, tp = calculate_sl_tp(df, signal)

                msg = f"""
{signal} XAUUSD
Entry: {entry}
SL: {sl}
TP: {tp}
"""

                send(msg)
                last_signal_time = now

                print("Trade sent:", msg)

        except Exception as e:
            print("ERROR:", e)

        time.sleep(60)

# ===== START =====
if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    threading.Thread(target=run_bot, daemon=True).start()

    while True:
        time.sleep(60)
