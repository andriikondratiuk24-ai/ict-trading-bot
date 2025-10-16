import pandas as pd
from datetime import time

# --- Сесії ---
SESSIONS = {
    "asia": (time(0, 0), time(9, 0)),
    "frankfurt": (time(9, 0), time(10, 0)),
    "london": (time(10, 0), time(15, 0)),
    "new_york": (time(15, 0), time(21, 0)),
}

def get_session(dt):
    t = dt.time()
    for name, (start, end) in SESSIONS.items():
        if start <= t < end or (name == "asia" and (t >= start or t < end)):
            return name
    return None

# --- Імбаланси (FVG) ---
def detect_fvg(df):
    # Простий FVG: Low(i) > High(i-2) (bullish), High(i) < Low(i-2) (bearish)
    df['fvg_up'] = (df['Low'] > df['High'].shift(2))
    df['fvg_dn'] = (df['High'] < df['Low'].shift(2))
    return df

# --- Sweep-и ---
def detect_sweep(df, window=20):
    df['sweep_high'] = df['High'] == df['High'].rolling(window, min_periods=1).max()
    df['sweep_low'] = df['Low'] == df['Low'].rolling(window, min_periods=1).min()
    return df

def detect_session_sweep(session_high, session_low, row):
    # Чи оновлено максимум/мінімум поточної сесії
    if row['High'] >= session_high:
        return "high"
    if row['Low'] <= session_low:
        return "low"
    return None

# --- Тренд ---
def detect_trend(df, period=20):
    df['sma'] = df['Close'].rolling(period).mean()
    df['trend'] = ['up' if c > s else 'down' for c, s in zip(df['Close'], df['sma'])]
    return df

# --- CISD ---
def detect_cisd(df, window=10):
    # Примітивна логіка консолідації
    df['cisd'] = (df['High'].rolling(window).max() - df['Low'].rolling(window).min()) < (df['Close'].mean() * 0.005)
    return df

# --- Основна логіка сигналу ---
def generate_signals(m15, h4, d1, w1, m1):
    signals = []
    m15 = detect_cisd(m15)
    h4 = detect_fvg(h4)
    d1 = detect_fvg(d1)
    w1 = detect_fvg(w1)
    m1 = detect_fvg(m1)
    h4 = detect_sweep(h4)
    d1 = detect_sweep(d1)
    w1 = detect_sweep(w1)
    m1 = detect_sweep(m1)
    h4 = detect_trend(h4)
    d1 = detect_trend(d1)
    for idx, row in m15.iterrows():
        dt = idx
        session = get_session(dt)
        if not session:
            continue

        # --- 1. Sweep та сесійні sweep-и ---
        # (можна розширити під свої сесійні екстремуми)
        # --- 2. Тест/реакція від імбалансу (по всіх фракталах) ---
        # --- 3. Sweep на фракталі чи сесії ---
        # --- 4. Тренд H4/D1 ---
        # --- 5. CISD на M15/M30 ---
        # --- 6. Формування сигналу ---
        # Тут реалізується твоя логіка з усіма перевірками

        # ПРИКЛАД (для доопрацювання):
        # Якщо на D1 або H4 незакритий FVG і ціна торкнулась FVG,
        # і sweep на H4 чи сесії, і сформовано CISD — сигнал
        fvg_touch = False  # TODO: реалізувати детекцію по історії
        sweep = False  # TODO: реалізувати перевірку sweep по сесії/глобально
        trend_ok = True  # TODO: перевірка тренду
        cisd_now = row['cisd']

        if fvg_touch and sweep and trend_ok and cisd_now:
            signals.append({
                "datetime": dt,
                "session": session,
                "signal": "entry",
                "note": "FVG, sweep, trend, CISD",
            })
    return signals

# --- Завантаження даних ---
def load_data():
    m15 = pd.read_csv("GBPUSD_M15.csv", parse_dates=["Datetime"], index_col="Datetime")
    h4 = pd.read_csv("GBPUSD_H4.csv", parse_dates=["Datetime"], index_col="Datetime")
    d1 = pd.read_csv("GBPUSD_D1.csv", parse_dates=["Datetime"], index_col="Datetime")
    w1 = pd.read_csv("GBPUSD_W1.csv", parse_dates=["Datetime"], index_col="Datetime")
    m1 = pd.read_csv("GBPUSD_M1.csv", parse_dates=["Datetime"], index_col="Datetime")
    return m15, h4, d1, w1, m1

if __name__ == "__main__":
    m15, h4, d1, w1, m1 = load_data()
    signals = generate_signals(m15, h4, d1, w1, m1)
    for sig in signals:
        print(sig)
