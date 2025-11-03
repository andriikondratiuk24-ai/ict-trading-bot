import pandas as pd
import numpy as np
from datetime import time
import argparse

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
        # asia wraps midnight
        if start <= t < end or (name == "asia" and (t >= start or t < end)):
            return name
    return None

# --- Імбаланси (FVG) ---
def detect_fvg(df):
    # Простий FVG: Low(i) > High(i-2) (bullish), High(i) < Low(i-2) (bearish)
    df = df.copy()
    if 'Low' in df.columns and 'High' in df.columns:
        df['fvg_up'] = (df['Low'] > df['High'].shift(2))
        df['fvg_dn'] = (df['High'] < df['Low'].shift(2))
    else:
        df['fvg_up'] = False
        df['fvg_dn'] = False
    return df

# --- Sweep-и ---
def detect_sweep(df, window=20):
    df = df.copy()
    if 'High' in df.columns:
        df['sweep_high'] = df['High'] == df['High'].rolling(window, min_periods=1).max()
    else:
        df['sweep_high'] = False
    if 'Low' in df.columns:
        df['sweep_low'] = df['Low'] == df['Low'].rolling(window, min_periods=1).min()
    else:
        df['sweep_low'] = False
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
    df = df.copy()
    if 'Close' in df.columns:
        df['sma'] = df['Close'].rolling(period).mean()
        df['trend'] = ['up' if c > s else 'down' for c, s in zip(df['Close'], df['sma'])]
    else:
        df['trend'] = 'flat'
    return df

# --- CISD proxy (signed rolling volume) ---
def compute_cisd_proxy(df: pd.DataFrame, window: int = 50, normalize: bool = True) -> pd.Series:
    """
    Signed-volume CISD proxy:
    signed = sign(close - open) * volume
    raw = rolling_sum(signed, window)
    if normalize: rel = raw / rolling_sum(volume, window)
    returns pd.Series aligned to df.index
    """
    if df is None or df.empty:
        return pd.Series(dtype=float)
    # Ensure numeric
    close = pd.to_numeric(df.get("Close", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    open_ = pd.to_numeric(df.get("Open", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    vol = pd.to_numeric(df.get("Volume", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    signed = np.sign(close - open_) * vol
    raw = signed.rolling(window=window, min_periods=1).sum()
    if normalize:
        denom = vol.rolling(window=window, min_periods=1).sum().replace(0, np.nan)
        rel = (raw / denom).fillna(0.0)
        return rel
    return raw

# --- CISD detector wrapper to add column ---
def detect_cisd(df: pd.DataFrame, window: int = 50, normalize: bool = True, colname: str = "cisd"):
    df = df.copy()
    df[colname] = compute_cisd_proxy(df, window=window, normalize=normalize)
    return df

# --- Parse note for boolean flags ---
def parse_note_flags(note):
    """
    Extract boolean flags from note text.
    Returns dict with sweep_flag, retest_flag, imb_flag.
    """
    if not note or not isinstance(note, str):
        return {"sweep_flag": False, "retest_flag": False, "imb_flag": False}
    
    note_lower = note.lower()
    
    # Check for sweep
    sweep_flag = "sweep" in note_lower
    
    # Check for retest (Latin and Cyrillic)
    retest_flag = "retest" in note_lower or "ретест" in note_lower
    
    # Check for imb or imbalance
    imb_flag = "imb" in note_lower or "imbalance" in note_lower
    
    return {
        "sweep_flag": sweep_flag,
        "retest_flag": retest_flag,
        "imb_flag": imb_flag
    }

# --- Основна логіка сигналу ---
def generate_signals(m15, m30, h1, h4, d1, w1, m1,
                     cisd_window=50, cisd_threshold=0.02,
                     require_cisd_15_and_30=True, require_cisd_1h=False,
                     rare_1h_rule=False):
    """
    rare_1h_rule: if True, require H1 CISD only when 15/30 are borderline (close to threshold)
    """
    signals = []
    # compute indicators minimally / safely
    try:
        m15 = detect_cisd(m15, window=cisd_window, normalize=True, colname='cisd_15')
    except Exception:
        m15['cisd_15'] = 0.0
    try:
        m30 = detect_cisd(m30, window=max(10, int(cisd_window * 0.67)), normalize=True, colname='cisd_30')
    except Exception:
        m30['cisd_30'] = 0.0
    try:
        h1 = detect_cisd(h1, window=max(10, int(cisd_window * 0.2)), normalize=True, colname='cisd_1h')
    except Exception:
        h1['cisd_1h'] = 0.0

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

    # Precompute nearest-asof indices for m30/h1 relative to m15
    if (m30 is not None) and (not m30.empty):
        m30_index = m30.index
    else:
        m30_index = None
    if (h1 is not None) and (not h1.empty):
        h1_index = h1.index
    else:
        h1_index = None

    total_checked = 0
    total_signals = 0

    for idx, row in m15.iterrows():
        total_checked += 1
        dt = idx
        session = get_session(dt)
        if not session:
            continue

        # CISD values: m15 directly, m30/h1 nearest <= idx
        try:
            cisd_15_val = float(row.get('cisd_15', 0.0)) if pd.notna(row.get('cisd_15', 0.0)) else 0.0
        except Exception:
            cisd_15_val = 0.0

        cisd_30_val = 0.0
        if m30_index is not None:
            t30 = m30_index.asof(idx)
            if pd.notna(t30):
                try:
                    cisd_30_val = float(m30.at[t30, 'cisd_30'])
                except Exception:
                    cisd_30_val = 0.0

        cisd_1h_val = 0.0
        if h1_index is not None:
            t1h = h1_index.asof(idx)
            if pd.notna(t1h):
                try:
                    cisd_1h_val = float(h1.at[t1h, 'cisd_1h'])
                except Exception:
                    cisd_1h_val = 0.0

        # CISD checks
        cisd_ok_15 = abs(cisd_15_val) >= cisd_threshold
        cisd_ok_30 = abs(cisd_30_val) >= cisd_threshold
        cisd_ok_1h = abs(cisd_1h_val) >= cisd_threshold

        # rare 1H rule: if 15&30 are close to threshold but not both above, require 1H
        borderline_factor = 0.8
        borderline_15 = abs(cisd_15_val) >= (cisd_threshold * borderline_factor)
        borderline_30 = abs(cisd_30_val) >= (cisd_threshold * borderline_factor)
        need_1h = False
        if require_cisd_1h:
            need_1h = True
        elif rare_1h_rule and (borderline_15 or borderline_30) and not (cisd_ok_15 and cisd_ok_30):
            need_1h = True

        # apply required CISD condition
        if require_cisd_15_and_30:
            if not (cisd_ok_15 and cisd_ok_30):
                continue
            if need_1h and not cisd_ok_1h:
                continue
        else:
            # if not strict, allow when either 15 or 30 ok; but if need_1h then require 1h too
            if not (cisd_ok_15 or cisd_ok_30):
                continue
            if need_1h and not cisd_ok_1h:
                continue

        # Example signal logic (keeps original placeholders but now CISD gating applied)
        # You can expand with FVG touch, sweep checks, trend, etc.
        fvg_touch = False  # TODO
        sweep = False      # TODO
        trend_ok = True    # TODO

        # Minimal rule: if (sweep or fvg_touch) and trend_ok and CISD gates passed -> collect
        sweep_up = bool(row.get('sweep_low', False))
        sweep_dn = bool(row.get('sweep_high', False))
        bos_up = bool(row.get('bos_up', False)) if 'bos_up' in row.index else False
        bos_dn = bool(row.get('bos_dn', False)) if 'bos_dn' in row.index else False

        long_condition = sweep_up and (not bos_dn) and ( (h4.get('trend', pd.Series(['flat'])).iloc[-1] if ('trend' in h4.columns and not h4.empty) else 'flat') in ("up","flat"))
        short_condition = sweep_dn and (not bos_up) and ( (h4.get('trend', pd.Series(['flat'])).iloc[-1] if ('trend' in h4.columns and not h4.empty) else 'flat') in ("down","flat"))

        # simple fallback: if either condition true, create signal
        if (long_condition or short_condition):
            direction = "long" if long_condition else "short"
            entry_price = None
            # try to get entry as Close of current m15
            try:
                entry_price = float(row.get('Close', np.nan))
            except Exception:
                entry_price = None
            if entry_price is None or pd.isna(entry_price):
                continue

            # Build note and parse flags from it
            note_text = f"cisd15={cisd_15_val:.4f} cisd30={cisd_30_val:.4f} cisd1h={cisd_1h_val:.4f}"
            
            # Check for existing note/sweep_fractal_note in row
            if 'note' in row.index and pd.notna(row.get('note')):
                note_text = str(row.get('note')) + " " + note_text
            elif 'sweep_fractal_note' in row.index and pd.notna(row.get('sweep_fractal_note')):
                note_text = str(row.get('sweep_fractal_note')) + " " + note_text
            
            # Parse note for flags
            note_flags = parse_note_flags(note_text)

            sig = {
                "datetime": dt,
                "entry": entry_price,
                "session": session,
                "sweep": sweep_up if direction == "long" else sweep_dn,
                "imbalance": bool(row.get('imbalance', False)) if 'imbalance' in row.index else False,
                "cisd_15": cisd_15_val,
                "cisd_30": cisd_30_val,
                "cisd_1h": cisd_1h_val,
                "note": note_text,
                "trend": (h4.get('trend', pd.Series(['flat'])).iloc[-1] if ('trend' in h4.columns and not h4.empty) else 'flat'),
                "type": direction,
                **note_flags
            }
            signals.append(sig)
            total_signals += 1

    print(f"Checked bars: {total_checked}, Signals: {total_signals}")
    return signals

# --- Завантаження даних ---
def load_data(base_name="GBPUSD"):
    # try multiple filenames similar to existing project layout
    def read_try(name):
        try:
            return pd.read_csv(name, parse_dates=["Datetime"], index_col="Datetime")
        except Exception:
            try:
                return pd.read_csv(name, parse_dates=["date"], index_col="date")
            except Exception:
                return pd.DataFrame()
    m15 = read_try(f"{base_name}_M15_filled.csv") if PathLike_available() else read_try(f"{base_name}_M15_filled.csv")
    if m15.empty:
        # fallback
        m15 = read_try(f"{base_name}_M15.csv")
    m30 = read_try(f"{base_name}_M30.csv")
    h1 = read_try(f"{base_name}_H1.csv")
    h4 = read_try(f"{base_name}_H4.csv")
    d1 = read_try(f"{base_name}_D1.csv")
    w1 = read_try(f"{base_name}_W1.csv")
    m1 = read_try(f"{base_name}_M1.csv")
    return m15, m30, h1, h4, d1, w1, m1

# small helper to avoid import error if pathlib not yet used
def PathLike_available():
    # this is a tiny guard: prefer standard simple read; real code can import pathlib.Path if desired
    return False

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="GBPUSD", help="Base symbol name prefix for CSVs (default GBPUSD)")
    p.add_argument("--cisd-window", type=int, default=50, help="CISD rolling window (bars) for M15 baseline")
    p.add_argument("--cisd-threshold", type=float, default=0.02, help="Minimum absolute CISD value (normalized) to consider")
    p.add_argument("--require-cisd-15-and-30", dest="require_cisd_15_and_30", action="store_true", help="Require CISD on both 15m and 30m")
    p.add_argument("--no-require-cisd-15-and-30", dest="require_cisd_15_and_30", action="store_false", help="Do NOT require CISD on both 15m and 30m (allow either)")
    p.add_argument("--require-cisd-1h", dest="require_cisd_1h", action="store_true", help="Require CISD also on 1h (strict)")
    p.add_argument("--rare-1h-rule", dest="rare_1h_rule", action="store_true", help="Apply 'rare' 1H requirement when 15m and 30m are borderline")
    p.set_defaults(require_cisd_15_and_30=True, require_cisd_1h=False, rare_1h_rule=False)
    args = p.parse_args()

    # load data
    try:
        m15, m30, h1, h4, d1, w1, m1 = load_data(base_name=args.base)
    except Exception as e:
        print("Error loading data:", e)
        m15 = m30 = h1 = h4 = d1 = w1 = m1 = pd.DataFrame()

    signals = generate_signals(m15, m30, h1, h4, d1, w1, m1,
                               cisd_window=args.cisd_window,
                               cisd_threshold=args.cisd_threshold,
                               require_cisd_15_and_30=args.require_cisd_15_and_30,
                               require_cisd_1h=args.require_cisd_1h,
                               rare_1h_rule=args.rare_1h_rule)

    for sig in signals:
        print(sig)
    
    # CSV Export Example:
    # To export signals to CSV with all fields including the new boolean flags:
    # import csv
    # with open('signals.csv', 'w', newline='') as csvfile:
    #     fieldnames = ['datetime', 'entry', 'session', 'sweep', 'imbalance', 
    #                   'cisd_15', 'cisd_30', 'cisd_1h', 'note', 'trend', 'type',
    #                   'sweep_flag', 'retest_flag', 'imb_flag']
    #     writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    #     writer.writeheader()
    #     for sig in signals:
    #         writer.writerow(sig)


# --- Unit Test Style Example ---
# Example demonstrating expected signal dict structure with the three new boolean fields:
#
# Example 1: Signal with sweep in note
# signal_1 = {
#     "datetime": "2024-01-15 10:30:00",
#     "entry": 1.2345,
#     "session": "london",
#     "sweep": True,
#     "imbalance": False,
#     "cisd_15": 0.0234,
#     "cisd_30": 0.0212,
#     "cisd_1h": 0.0189,
#     "note": "sweep detected cisd15=0.0234 cisd30=0.0212 cisd1h=0.0189",
#     "trend": "up",
#     "type": "long",
#     "sweep_flag": True,    # 'sweep' found in note
#     "retest_flag": False,  # no 'retest' or 'ретест' in note
#     "imb_flag": False      # no 'imb' or 'imbalance' in note
# }
#
# Example 2: Signal with retest and imbalance
# signal_2 = {
#     "datetime": "2024-01-15 14:45:00",
#     "entry": 1.2367,
#     "session": "new_york",
#     "sweep": False,
#     "imbalance": True,
#     "cisd_15": -0.0256,
#     "cisd_30": -0.0243,
#     "cisd_1h": -0.0221,
#     "note": "retest of imbalance zone cisd15=-0.0256 cisd30=-0.0243 cisd1h=-0.0221",
#     "trend": "down",
#     "type": "short",
#     "sweep_flag": False,   # no 'sweep' in note
#     "retest_flag": True,   # 'retest' found in note (case-insensitive)
#     "imb_flag": True       # 'imbalance' found in note
# }
#
# Example 3: Cyrillic retest keyword
# signal_3 = {
#     "datetime": "2024-01-15 16:00:00",
#     "entry": 1.2389,
#     "session": "new_york",
#     "sweep": True,
#     "imbalance": False,
#     "cisd_15": 0.0298,
#     "cisd_30": 0.0267,
#     "cisd_1h": 0.0245,
#     "note": "Sweep with ретест cisd15=0.0298 cisd30=0.0267 cisd1h=0.0245",
#     "trend": "up",
#     "type": "long",
#     "sweep_flag": True,    # 'Sweep' found (case-insensitive)
#     "retest_flag": True,   # 'ретест' found (Cyrillic variant)
#     "imb_flag": False      # no 'imb' or 'imbalance' in note
# }