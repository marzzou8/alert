from flask import Flask
import threading
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running"

def run_server():
    port = int(os.environ.get("PORT", 10000))  # 🔥 IMPORTANT
    app.run(host='0.0.0.0', port=port)
    
import requests
import pandas as pd
import time
import os

OANDA_API = os.getenv("OANDA_API")
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

last_signal = None

def send(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

def get_data():
    url = "https://api-fxpractice.oanda.com/v3/instruments/XAU_USD/candles"
    headers = {"Authorization": f"Bearer {OANDA_API}"}
    params = {"granularity": "M1", "count": 50}

    r = requests.get(url, headers=headers, params=params)
    data = r.json()

    print("API RESPONSE:", data)  # 👈 ADD THIS

    prices = [float(c["mid"]["c"]) for c in data["candles"]]
    return pd.DataFrame(prices, columns=["close"])

while True:
    df = get_data()

    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema20'] = df['close'].ewm(span=20).mean()
    rsi = df['close'].diff().apply(lambda x: max(x,0)).rolling(14).mean() / \
          df['close'].diff().abs().rolling(14).mean() * 100

    current_signal = None

    if df['ema9'].iloc[-1] > df['ema20'].iloc[-1] and rsi.iloc[-1] > 50:
        current_signal = "BUY"
    elif df['ema9'].iloc[-1] < df['ema20'].iloc[-1] and rsi.iloc[-1] < 50:
        current_signal = "SELL"

    if current_signal and current_signal != last_signal:
        send(f"{current_signal} XAUUSD")
        last_signal = current_signal

    time.sleep(60)

threading.Thread(target=run_server).start()
