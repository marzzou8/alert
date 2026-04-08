# ===== IMPROVED BOT LOOP =====
import numpy as np

def get_data():
    try:
        url = "https://api-fxpractice.oanda.com/v3/instruments/XAU_USD/candles"
        headers = {"Authorization": f"Bearer {OANDA_API}"}
        params = {"granularity": "M1", "count": 100}  # need more candles for EMAs

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

def calculate_indicators(df):
    """Return latest values of all indicators"""
    close = df['close']
    
    # EMAs
    ema9 = close.ewm(span=9, adjust=False).mean()
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()
    
    # RSI (14)
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    # Bollinger Bands (20,2)
    bb_middle = close.rolling(window=20).mean()
    bb_std = close.rolling(window=20).std()
    bb_upper = bb_middle + 2 * bb_std
    bb_lower = bb_middle - 2 * bb_std
    
    return {
        'ema9': ema9.iloc[-1],
        'ema20': ema20.iloc[-1],
        'ema200': ema200.iloc[-1],
        'rsi': rsi.iloc[-1],
        'close': close.iloc[-1],
        'bb_lower': bb_lower.iloc[-1],
        'bb_upper': bb_upper.iloc[-1],
        'prev_ema9': ema9.iloc[-2],
        'prev_ema20': ema20.iloc[-2]
    }

def run_bot():
    global last_signal
    send("✅ Gold Scalping Bot STARTED (EMA+RSI+BB Strategy)")
    
    # Cooldown: don't send another signal for 5 minutes
    last_signal_time = 0
    
    while True:
        try:
            df = get_data()
            if df is None or len(df) < 200:
                time.sleep(30)
                continue
            
            ind = calculate_indicators(df)
            
            # --- Crossover detection ---
            ema9_above_20 = ind['ema9'] > ind['ema20']
            prev_ema9_above_20 = ind['prev_ema9'] > ind['prev_ema20']
            
            bullish_crossover = (not prev_ema9_above_20) and ema9_above_20
            bearish_crossover = prev_ema9_above_20 and (not ema9_above_20)
            
            # --- Trend filter ---
            above_200ema = ind['close'] > ind['ema200']
            below_200ema = ind['close'] < ind['ema200']
            
            # --- RSI extremes ---
            oversold = ind['rsi'] < 30
            overbought = ind['rsi'] > 70
            
            # --- Bollinger Band touch ---
            touch_lower = ind['close'] <= ind['bb_lower']
            touch_upper = ind['close'] >= ind['bb_upper']
            
            # --- Final signal logic (matching our backtest) ---
            buy_signal = (bullish_crossover and above_200ema and oversold and touch_lower)
            sell_signal = (bearish_crossover and below_200ema and overbought and touch_upper)
            
            # Optional: remove BB touch for more signals (but lower quality)
            # buy_signal = (bullish_crossover and above_200ema and oversold)
            # sell_signal = (bearish_crossover and below_200ema and overbought)
            
            current_time = time.time()
            signal = None
            if buy_signal and (current_time - last_signal_time > 300):  # 5 min cooldown
                signal = "BUY"
                last_signal_time = current_time
            elif sell_signal and (current_time - last_signal_time > 300):
                signal = "SELL"
                last_signal_time = current_time
            
            if signal and signal != last_signal:
                msg = (f"{signal} XAUUSD\n"
                       f"Price: {ind['close']:.2f}\n"
                       f"EMA9: {ind['ema9']:.2f}  EMA20: {ind['ema20']:.2f}\n"
                       f"200 EMA: {ind['ema200']:.2f}\n"
                       f"RSI: {ind['rsi']:.1f}\n"
                       f"BB: lower={ind['bb_lower']:.2f} upper={ind['bb_upper']:.2f}")
                send(msg)
                last_signal = signal
            
            print(f"Checked at {time.ctime()}: EMA9/20 cross={bullish_crossover or bearish_crossover}, RSI={ind['rsi']:.1f}")
            
        except Exception as e:
            print("BOT ERROR:", e)
        
        time.sleep(60)  # check every minute
