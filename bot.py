import requests
import pandas as pd
import time

OANDA_API = "ecf88b39a29b09f99c60c5a91d6ff12d-cf0972461303e57ee09cb17d088f363c"
TOKEN = "8607725356:AAFZBbYV583Y21mooLmkYvoWy8iyZzuOUyQ"
CHAT_ID = "8607725356"

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

    prices = [float(c["mid"]["c"]) for c in data["candles"]]
    df = pd.DataFrame(prices, columns=["close"])
    return df

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