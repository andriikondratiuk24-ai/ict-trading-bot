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
    # Check non-Asia sessions first (they have priority)
    if time(9, 0) <= t < time(10, 0):
        return "frankfurt"
    elif time(10, 0) <= t < time(15, 0):
        return "london"
    elif time(15, 0) <= t < time(21, 0):
        return "new_york"
    elif t >= time(21, 0) or t < time(9, 0):
        return "asia"
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
    m15 = detect_fvg(m15.copy())
    m15 = detect_cisd(m15)
    h4 = detect_fvg(h4.copy())
    d1 = detect_fvg(d1.copy())
    w1 = detect_fvg(w1.copy())
    m1 = detect_fvg(m1.copy())
    h4 = detect_sweep(h4)
    d1 = detect_sweep(d1)
    w1 = detect_sweep(w1)
    m1 = detect_sweep(m1)
    h4 = detect_trend(h4)
    d1 = detect_trend(d1)
    
    # Track FVG zones from higher timeframes
    h4_fvg_zones = []
    for idx, row in h4.iterrows():
        if row['fvg_up']:
            h4_fvg_zones.append({'time': idx, 'type': 'up', 'low': row['Low'], 'high': row['High']})
        if row['fvg_dn']:
            h4_fvg_zones.append({'time': idx, 'type': 'down', 'low': row['Low'], 'high': row['High']})
    
    d1_fvg_zones = []
    for idx, row in d1.iterrows():
        if row['fvg_up']:
            d1_fvg_zones.append({'time': idx, 'type': 'up', 'low': row['Low'], 'high': row['High']})
        if row['fvg_dn']:
            d1_fvg_zones.append({'time': idx, 'type': 'down', 'low': row['Low'], 'high': row['High']})
    
    for idx, row in m15.iterrows():
        dt = idx
        session = get_session(dt)
        if not session:
            continue

        # Check for FVG touch from higher timeframes
        fvg_touch = False
        fvg_type = None
        
        # Check H4 FVG zones
        for zone in h4_fvg_zones:
            if zone['time'] <= dt:  # Only consider past FVGs
                if zone['low'] <= row['Low'] <= zone['high'] or zone['low'] <= row['High'] <= zone['high']:
                    fvg_touch = True
                    fvg_type = zone['type']
                    break
        
        # Check D1 FVG zones if H4 didn't trigger
        if not fvg_touch:
            for zone in d1_fvg_zones:
                if zone['time'] <= dt:
                    if zone['low'] <= row['Low'] <= zone['high'] or zone['low'] <= row['High'] <= zone['high']:
                        fvg_touch = True
                        fvg_type = zone['type']
                        break
        
        # Get current H4 and D1 context
        h4_current = h4[h4.index <= dt].iloc[-1] if len(h4[h4.index <= dt]) > 0 else None
        d1_current = d1[d1.index <= dt].iloc[-1] if len(d1[d1.index <= dt]) > 0 else None
        
        # Check for sweep
        sweep = row.get('sweep_high', False) or row.get('sweep_low', False)
        
        # Check trend alignment
        trend_ok = False
        if h4_current is not None and d1_current is not None:
            h4_trend = h4_current.get('trend', 'down')
            d1_trend = d1_current.get('trend', 'down')
            trend_ok = (h4_trend == d1_trend)
        
        # Check CISD
        cisd_now = row['cisd']
        
        # Generate signal if conditions are met
        # More relaxed conditions for demonstration
        if fvg_touch and (sweep or cisd_now):
            direction = "LONG" if fvg_type == 'up' else "SHORT"
            signals.append({
                "datetime": dt,
                "session": session,
                "direction": direction,
                "price": row['Close'],
                "conditions": {
                    "fvg_touch": fvg_touch,
                    "sweep": sweep,
                    "cisd": cisd_now,
                    "trend_aligned": trend_ok
                }
            })
        
        # Additional simplified signal: just based on M15 patterns
        # Detect strong FVG on M15 itself
        if row.get('fvg_up', False) and cisd_now:
            signals.append({
                "datetime": dt,
                "session": session,
                "direction": "LONG",
                "price": row['Close'],
                "conditions": {
                    "m15_fvg": True,
                    "cisd": cisd_now
                }
            })
        elif row.get('fvg_dn', False) and cisd_now:
            signals.append({
                "datetime": dt,
                "session": session,
                "direction": "SHORT",
                "price": row['Close'],
                "conditions": {
                    "m15_fvg": True,
                    "cisd": cisd_now
                }
            })
    
    return signals

# --- Завантаження даних ---
def load_data():
    m15 = pd.read_csv("data/GBPUSD_M15.csv", parse_dates=["Datetime"], index_col="Datetime")
    h4 = pd.read_csv("data/GBPUSD_H4.csv", parse_dates=["Datetime"], index_col="Datetime")
    d1 = pd.read_csv("data/GBPUSD_D1.csv", parse_dates=["Datetime"], index_col="Datetime")
    w1 = pd.read_csv("data/GBPUSD_W1.csv", parse_dates=["Datetime"], index_col="Datetime")
    m1 = pd.read_csv("data/GBPUSD_M1.csv", parse_dates=["Datetime"], index_col="Datetime")
    return m15, h4, d1, w1, m1

if __name__ == "__main__":
    print("Loading data...")
    m15, h4, d1, w1, m1 = load_data()
    print(f"Loaded {len(m15)} M15 candles, {len(h4)} H4 candles, {len(d1)} D1 candles")
    
    print("\nGenerating signals...")
    signals = generate_signals(m15, h4, d1, w1, m1)
    
    print(f"\n{'='*60}")
    print(f"Total signals generated: {len(signals)}")
    print(f"{'='*60}\n")
    
    if signals:
        print("Sample signals:")
        for i, sig in enumerate(signals[:10]):  # Show first 10 signals
            print(f"{i+1}. {sig}")
    else:
        print("No signals generated. The strategy conditions were not met.")
