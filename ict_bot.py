import pandas as pd
import numpy as np
from datetime import time, datetime, timedelta
from typing import List, Dict, Tuple, Optional

# ============================================================================
# КОНСТАНТИ ТА КОНФІГУРАЦІЯ
# ============================================================================

SESSIONS = {
    "asia": (time(0, 0), time(9, 0)),
    "frankfurt": (time(9, 0), time(10, 0)),
    "london": (time(10, 0), time(15, 0)),
    "new_york": (time(15, 0), time(21, 0)),
}

DEBUG_MODE = False  # Встановіть True для увімкнення debug-виводу

# ============================================================================
# ДОПОМІЖНІ ФУНКЦІЇ
# ============================================================================

def debug_print(msg: str):
    """Виводить debug повідомлення, якщо DEBUG_MODE увімкнено."""
    if DEBUG_MODE:
        print(f"[DEBUG] {msg}")

def get_session(dt: datetime) -> Optional[str]:
    """Визначає торговельну сесію для заданого часу."""
    t = dt.time()
    for name, (start, end) in SESSIONS.items():
        if name == "asia" and (t >= start or t < end):
            return name
        elif start <= t < end:
            return name
    return None

def get_closest_candle(df: pd.DataFrame, target_time: datetime) -> Optional[pd.Series]:
    """Знаходить найближчу свічку в DataFrame до заданого часу."""
    if df.empty:
        return None
    idx = df.index.get_indexer([target_time], method='nearest')
    if idx[0] >= 0 and idx[0] < len(df):
        return df.iloc[idx[0]]
    return None

# ============================================================================
# ДЕТЕКЦІЯ ІМБАЛАНСІВ (FVG - Fair Value Gap)
# ============================================================================

def detect_fvg(df: pd.DataFrame) -> pd.DataFrame:
    """
    Виявляє FVG (Fair Value Gaps) - імбаланси.
    Bullish FVG: Low[i] > High[i-2]
    Bearish FVG: High[i] < Low[i-2]
    """
    df = df.copy()
    df['fvg_up'] = (df['Low'] > df['High'].shift(2))
    df['fvg_dn'] = (df['High'] < df['Low'].shift(2))
    
    # Зберігаємо зони FVG для подальшого тестування
    high_shift2 = df['High'].shift(2)
    low_shift2 = df['Low'].shift(2)
    
    df['fvg_up_zone_low'] = df['fvg_up'].apply(lambda x: np.nan if not x else None)
    df.loc[df['fvg_up'], 'fvg_up_zone_low'] = high_shift2[df['fvg_up']]
    df.loc[df['fvg_up'], 'fvg_up_zone_high'] = df.loc[df['fvg_up'], 'Low']
    
    df['fvg_dn_zone_low'] = df['fvg_dn'].apply(lambda x: np.nan if not x else None)
    df.loc[df['fvg_dn'], 'fvg_dn_zone_low'] = df.loc[df['fvg_dn'], 'High']
    df.loc[df['fvg_dn'], 'fvg_dn_zone_high'] = low_shift2[df['fvg_dn']]
    
    return df

def test_fvg_zone(price_low: float, price_high: float, fvg_zones: List[Tuple[float, float]], direction: str) -> bool:
    """
    Перевіряє, чи ціна торкнулася незакритої FVG зони.
    direction: 'up' для bullish, 'down' для bearish
    """
    for zone_low, zone_high in fvg_zones:
        if price_low <= zone_high and price_high >= zone_low:
            return True
    return False

# ============================================================================
# ДЕТЕКЦІЯ SWEEP (ЗНЯТТЯ ЛІКВІДНОСТІ)
# ============================================================================

def detect_sweep(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """
    Виявляє sweep (зняття ліквідності) - коли ціна оновлює локальні екстремуми.
    """
    df = df.copy()
    df['sweep_high'] = df['High'] == df['High'].rolling(window, min_periods=1).max()
    df['sweep_low'] = df['Low'] == df['Low'].rolling(window, min_periods=1).min()
    return df

def detect_session_sweep(session_data: Dict, current_high: float, current_low: float, current_session: str) -> Tuple[bool, bool]:
    """
    Виявляє sweep при відкритті сесії або sweep сесійних екстремумів.
    Повертає: (sweep_high, sweep_low)
    """
    sweep_high = False
    sweep_low = False
    
    if current_session == "frankfurt":
        # Frankfurt може знімати Asia ліквідність
        if 'asia_high' in session_data and current_high > session_data['asia_high']:
            sweep_high = True
        if 'asia_low' in session_data and current_low < session_data['asia_low']:
            sweep_low = True
    
    elif current_session == "london":
        # London може знімати Asia та Frankfurt ліквідність
        if 'asia_high' in session_data and current_high > session_data['asia_high']:
            sweep_high = True
        if 'asia_low' in session_data and current_low < session_data['asia_low']:
            sweep_low = True
        if 'frankfurt_high' in session_data and current_high > session_data['frankfurt_high']:
            sweep_high = True
        if 'frankfurt_low' in session_data and current_low < session_data['frankfurt_low']:
            sweep_low = True
    
    elif current_session == "new_york":
        # NY може знімати London ліквідність
        if 'london_high' in session_data and current_high > session_data['london_high']:
            sweep_high = True
        if 'london_low' in session_data and current_low < session_data['london_low']:
            sweep_low = True
    
    return sweep_high, sweep_low

# ============================================================================
# ДЕТЕКЦІЯ ТРЕНДУ
# ============================================================================

def detect_trend(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """
    Визначає тренд на основі простої ковзної середньої (SMA).
    """
    df = df.copy()
    df['sma'] = df['Close'].rolling(period).mean()
    df['trend'] = df.apply(lambda x: 'up' if x['Close'] > x['sma'] else 'down', axis=1)
    return df

# ============================================================================
# ДЕТЕКЦІЯ CISD (CONSOLIDATION/INTERNAL STRUCTURE DISPLACEMENT)
# ============================================================================

def detect_cisd(df: pd.DataFrame, window: int = 10) -> pd.DataFrame:
    """
    Виявляє CISD - консолідацію з подальшим різким рухом.
    Спрощена версія: консолідація + волатильність менша за поріг.
    """
    df = df.copy()
    range_val = df['High'].rolling(window).max() - df['Low'].rolling(window).min()
    avg_close = df['Close'].rolling(window).mean()
    df['cisd'] = range_val < (avg_close * 0.005)
    return df

# ============================================================================
# ДЕТЕКЦІЯ BOS (BREAK OF STRUCTURE)
# ============================================================================

def detect_bos(df: pd.DataFrame, lookback: int = 10) -> pd.DataFrame:
    """
    Виявляє BOS (Break of Structure) - пробиття локального рівня структури.
    Bullish BOS: ціна пробиває попередній значущий максимум
    Bearish BOS: ціна пробиває попередній значущий мінімум
    """
    df = df.copy()
    df['local_high'] = df['High'].rolling(lookback).max().shift(1)
    df['local_low'] = df['Low'].rolling(lookback).min().shift(1)
    
    df['bos_bullish'] = df['Close'] > df['local_high']
    df['bos_bearish'] = df['Close'] < df['local_low']
    
    return df

# ============================================================================
# ДЕТЕКЦІЯ DOUBLE SWEEP
# ============================================================================

def detect_double_sweep(df: pd.DataFrame, window: int = 10) -> pd.DataFrame:
    """
    Виявляє подвійний sweep - два sweep-и за короткий період.
    """
    df = df.copy()
    df['sweep_high_count'] = df['sweep_high'].rolling(window).sum()
    df['sweep_low_count'] = df['sweep_low'].rolling(window).sum()
    
    df['double_sweep_high'] = df['sweep_high_count'] >= 2
    df['double_sweep_low'] = df['sweep_low_count'] >= 2
    
    return df

# ============================================================================
# ЗБІР СЕСІЙНИХ ДАНИХ
# ============================================================================

def collect_session_data(df: pd.DataFrame) -> Dict[datetime, Dict]:
    """
    Збирає дані по сесіях: максимуми, мінімуми, FVG зони.
    Повертає словник з даними для кожної дати.
    """
    session_data = {}
    current_date = None
    day_sessions = {}
    
    for idx, row in df.iterrows():
        dt = idx
        date_key = dt.date()
        session = get_session(dt)
        
        if date_key != current_date:
            if current_date is not None:
                session_data[current_date] = day_sessions.copy()
            current_date = date_key
            day_sessions = {}
        
        if session:
            session_key = f"{session}_high"
            session_key_low = f"{session}_low"
            
            if session_key not in day_sessions:
                day_sessions[session_key] = row['High']
            else:
                day_sessions[session_key] = max(day_sessions[session_key], row['High'])
            
            if session_key_low not in day_sessions:
                day_sessions[session_key_low] = row['Low']
            else:
                day_sessions[session_key_low] = min(day_sessions[session_key_low], row['Low'])
    
    if current_date is not None:
        session_data[current_date] = day_sessions
    
    return session_data

# ============================================================================
# ОСНОВНА ЛОГІКА ГЕНЕРАЦІЇ СИГНАЛІВ
# ============================================================================

def check_pattern_1_sweep_fvg_cisd(context: Dict) -> Optional[Dict]:
    """
    Патерн 1: Sweep + FVG + CISD
    - Ціна знімає ліквідність (sweep)
    - Відбувається тест або реакція на незакритий імбаланс (FVG)
    - Формується CISD на молодшому ТФ
    """
    if not (context['sweep_detected'] and context['fvg_tested'] and context['cisd_detected']):
        return None
    
    signal_type = "BUY" if context['sweep_direction'] == 'low' else "SELL"
    
    return {
        "pattern": "Sweep + FVG + CISD",
        "type": signal_type,
        "reason": f"Sweep {context['sweep_timeframe']}, FVG tested on {context['fvg_timeframe']}, CISD on M15",
        "confidence": "HIGH"
    }

def check_pattern_2_double_sweep(context: Dict) -> Optional[Dict]:
    """
    Патерн 2: Double Sweep
    - Два sweep-и за короткий період
    - Після другого sweep відбувається тест FVG/CISD
    """
    if not (context['double_sweep_detected'] and (context['fvg_tested'] or context['cisd_detected'])):
        return None
    
    signal_type = "BUY" if context['sweep_direction'] == 'low' else "SELL"
    
    return {
        "pattern": "Double Sweep",
        "type": signal_type,
        "reason": f"Double sweep on {context['sweep_timeframe']}, followed by FVG/CISD reaction",
        "confidence": "VERY HIGH"
    }

def check_pattern_3_session_open_grab(context: Dict) -> Optional[Dict]:
    """
    Патерн 3: Session Open Liquidity Grab
    - Sweep/зняття ліквідності при відкритті сесії
    - Реакція ціни на імбаланс і формування CISD
    """
    if not (context['session_sweep'] and context['fvg_tested'] and context['cisd_detected']):
        return None
    
    signal_type = "BUY" if context['sweep_direction'] == 'low' else "SELL"
    
    return {
        "pattern": "Session Open Liquidity Grab",
        "type": signal_type,
        "reason": f"Session sweep at {context['session']} open, FVG tested, CISD formed",
        "confidence": "HIGH"
    }

def check_pattern_4_bos_after_sweep(context: Dict) -> Optional[Dict]:
    """
    Патерн 4: Break of Structure (BOS) після sweep-а
    - Sweep супроводжується пробиттям локального рівня структури
    - Після BOS відбувається тест FVG або формування CISD
    """
    if not (context['sweep_detected'] and context['bos_detected'] and (context['fvg_tested'] or context['cisd_detected'])):
        return None
    
    signal_type = "BUY" if context['bos_direction'] == 'bullish' else "SELL"
    
    return {
        "pattern": "BOS after Sweep",
        "type": signal_type,
        "reason": f"Sweep followed by {context['bos_direction']} BOS on {context['bos_timeframe']}, FVG/CISD confirmed",
        "confidence": "HIGH"
    }

def check_pattern_5_asia_frankfurt_context(context: Dict) -> Optional[Dict]:
    """
    Патерн 5: Asia/Frankfurt контекст для London/NY
    - Sweep та/або імбаланс на Asia/Frankfurt
    - Реакція на ці зони в London/NY (sweep, FVG, CISD)
    """
    if not context['early_session_context']:
        return None
    
    if context['session'] not in ['london', 'new_york']:
        return None
    
    if not (context['session_sweep'] and context['fvg_tested']):
        return None
    
    signal_type = "BUY" if context['sweep_direction'] == 'low' else "SELL"
    
    return {
        "pattern": "Asia/Frankfurt Context",
        "type": signal_type,
        "reason": f"Early session setup from {context['context_session']}, reacted in {context['session']}",
        "confidence": "MEDIUM-HIGH"
    }

def generate_signals(m15: pd.DataFrame, h4: pd.DataFrame, d1: pd.DataFrame, 
                    w1: pd.DataFrame, m1: pd.DataFrame) -> List[Dict]:
    """
    Головна функція генерації сигналів.
    Аналізує всі таймфрейми та шукає патерни згідно з умовами.
    """
    signals = []
    
    # Підготовка даних
    debug_print("Preparing data for all timeframes...")
    m15 = detect_cisd(m15)
    m15 = detect_sweep(m15, window=20)
    
    h4 = detect_fvg(h4)
    h4 = detect_sweep(h4, window=10)
    h4 = detect_trend(h4)
    h4 = detect_bos(h4)
    h4 = detect_double_sweep(h4)
    
    d1 = detect_fvg(d1)
    d1 = detect_sweep(d1, window=10)
    d1 = detect_trend(d1)
    d1 = detect_bos(d1)
    
    w1 = detect_fvg(w1)
    w1 = detect_sweep(w1, window=5)
    
    m1 = detect_fvg(m1)
    m1 = detect_sweep(m1, window=30)
    
    # Збір сесійних даних
    debug_print("Collecting session data...")
    session_data = collect_session_data(m15)
    
    # Аналіз кожної свічки M15
    debug_print(f"Analyzing {len(m15)} M15 candles...")
    
    for idx, row in m15.iterrows():
        dt = idx
        session = get_session(dt)
        if not session:
            continue
        
        date_key = dt.date()
        prev_date = date_key - timedelta(days=1)
        
        # Отримуємо дані попередніх сесій
        prev_session_data = session_data.get(prev_date, {})
        current_session_data = session_data.get(date_key, {})
        
        # Ініціалізація контексту
        context = {
            'datetime': dt,
            'session': session,
            'sweep_detected': False,
            'sweep_direction': None,
            'sweep_timeframe': None,
            'double_sweep_detected': False,
            'session_sweep': False,
            'fvg_tested': False,
            'fvg_timeframe': None,
            'cisd_detected': row.get('cisd', False),
            'bos_detected': False,
            'bos_direction': None,
            'bos_timeframe': None,
            'trend_h4': None,
            'trend_d1': None,
            'early_session_context': False,
            'context_session': None,
        }
        
        # 1. Перевірка sweep на M15
        if row.get('sweep_high', False) or row.get('sweep_low', False):
            context['sweep_detected'] = True
            context['sweep_direction'] = 'high' if row.get('sweep_high', False) else 'low'
            context['sweep_timeframe'] = 'M15'
        
        # 2. Перевірка session sweep
        sweep_high, sweep_low = detect_session_sweep(
            {**prev_session_data, **current_session_data},
            row['High'], row['Low'], session
        )
        
        if sweep_high or sweep_low:
            context['session_sweep'] = True
            context['sweep_detected'] = True
            context['sweep_direction'] = 'high' if sweep_high else 'low'
            if not context['sweep_timeframe']:
                context['sweep_timeframe'] = 'SESSION'
        
        # 3. Перевірка sweep на вищих таймфреймах
        h4_candle = get_closest_candle(h4, dt)
        if h4_candle is not None:
            if h4_candle.get('sweep_high', False) or h4_candle.get('sweep_low', False):
                context['sweep_detected'] = True
                if not context['sweep_direction']:
                    context['sweep_direction'] = 'high' if h4_candle.get('sweep_high', False) else 'low'
                context['sweep_timeframe'] = 'H4'
            
            # Перевірка double sweep на H4
            if h4_candle.get('double_sweep_high', False) or h4_candle.get('double_sweep_low', False):
                context['double_sweep_detected'] = True
                context['sweep_direction'] = 'high' if h4_candle.get('double_sweep_high', False) else 'low'
                context['sweep_timeframe'] = 'H4'
            
            # Тренд H4
            context['trend_h4'] = h4_candle.get('trend', None)
            
            # BOS на H4
            if h4_candle.get('bos_bullish', False) or h4_candle.get('bos_bearish', False):
                context['bos_detected'] = True
                context['bos_direction'] = 'bullish' if h4_candle.get('bos_bullish', False) else 'bearish'
                context['bos_timeframe'] = 'H4'
        
        # 4. Перевірка D1 та W1
        d1_candle = get_closest_candle(d1, dt)
        if d1_candle is not None:
            context['trend_d1'] = d1_candle.get('trend', None)
            
            if d1_candle.get('sweep_high', False) or d1_candle.get('sweep_low', False):
                context['sweep_detected'] = True
                if not context['sweep_direction']:
                    context['sweep_direction'] = 'high' if d1_candle.get('sweep_high', False) else 'low'
                context['sweep_timeframe'] = 'D1'
            
            # BOS на D1
            if not context['bos_detected']:
                if d1_candle.get('bos_bullish', False) or d1_candle.get('bos_bearish', False):
                    context['bos_detected'] = True
                    context['bos_direction'] = 'bullish' if d1_candle.get('bos_bullish', False) else 'bearish'
                    context['bos_timeframe'] = 'D1'
        
        w1_candle = get_closest_candle(w1, dt)
        if w1_candle is not None:
            if w1_candle.get('sweep_high', False) or w1_candle.get('sweep_low', False):
                context['sweep_detected'] = True
                if not context['sweep_direction']:
                    context['sweep_direction'] = 'high' if w1_candle.get('sweep_high', False) else 'low'
                context['sweep_timeframe'] = 'W1'
        
        # 5. Перевірка FVG тесту
        # Перевіряємо, чи ціна торкнулася незакритих FVG зон на вищих таймфреймах
        fvg_zones = []
        
        # Збираємо FVG зони з H4
        for h4_idx, h4_row in h4.iterrows():
            if h4_idx > dt:
                break
            if h4_row.get('fvg_up', False):
                zone_low = h4_row.get('High') if pd.notna(h4_row.get('High')) else None
                zone_high = h4_row.get('Low') if pd.notna(h4_row.get('Low')) else None
                if zone_low and zone_high:
                    fvg_zones.append((zone_low, zone_high))
            if h4_row.get('fvg_dn', False):
                zone_low = h4_row.get('High') if pd.notna(h4_row.get('High')) else None
                zone_high = h4_row.get('Low') if pd.notna(h4_row.get('Low')) else None
                if zone_low and zone_high:
                    fvg_zones.append((zone_low, zone_high))
        
        # Перевіряємо тест FVG
        if fvg_zones and test_fvg_zone(row['Low'], row['High'], fvg_zones, context['sweep_direction']):
            context['fvg_tested'] = True
            context['fvg_timeframe'] = 'H4'
        
        # 6. Контекст Asia/Frankfurt для London/NY
        if session in ['london', 'new_york']:
            if 'asia_high' in prev_session_data or 'frankfurt_high' in current_session_data:
                context['early_session_context'] = True
                context['context_session'] = 'Asia/Frankfurt'
        
        # 7. Перевірка тренду (додаткова умова для входу)
        trend_ok = True
        if context['trend_h4'] and context['trend_d1']:
            # Якщо є sweep на W1/M1, можливий розворот
            if context['sweep_timeframe'] not in ['W1', 'M1']:
                # Інакше тренд має співпадати
                if context['sweep_direction'] == 'low' and context['trend_h4'] != 'up':
                    trend_ok = False
                if context['sweep_direction'] == 'high' and context['trend_h4'] != 'down':
                    trend_ok = False
        
        # 8. Перевірка всіх патернів
        if trend_ok:
            patterns = [
                check_pattern_1_sweep_fvg_cisd,
                check_pattern_2_double_sweep,
                check_pattern_3_session_open_grab,
                check_pattern_4_bos_after_sweep,
                check_pattern_5_asia_frankfurt_context,
            ]
            
            for pattern_func in patterns:
                result = pattern_func(context)
                if result:
                    signal = {
                        "datetime": dt,
                        "session": session,
                        "pattern": result['pattern'],
                        "type": result['type'],
                        "reason": result['reason'],
                        "confidence": result['confidence'],
                        "trend_h4": context['trend_h4'],
                        "trend_d1": context['trend_d1'],
                        "timeframes": f"Entry: M15, Sweep: {context['sweep_timeframe']}, Trend: H4/D1"
                    }
                    signals.append(signal)
                    debug_print(f"Signal found: {result['pattern']} at {dt}")
                    break  # Один сигнал на свічку
    
    return signals

# ============================================================================
# ЗАВАНТАЖЕННЯ ДАНИХ
# ============================================================================

def load_data():
    """Завантажує CSV дані для всіх таймфреймів."""
    try:
        m15 = pd.read_csv("data/GBPUSD_M15.csv", parse_dates=["Datetime"], index_col="Datetime")
        h4 = pd.read_csv("data/GBPUSD_H4.csv", parse_dates=["Datetime"], index_col="Datetime")
        d1 = pd.read_csv("data/GBPUSD_D1.csv", parse_dates=["Datetime"], index_col="Datetime")
        w1 = pd.read_csv("data/GBPUSD_W1.csv", parse_dates=["Datetime"], index_col="Datetime")
        m1 = pd.read_csv("data/GBPUSD_M1.csv", parse_dates=["Datetime"], index_col="Datetime")
        return m15, h4, d1, w1, m1
    except Exception as e:
        print(f"Error loading data: {e}")
        raise

# ============================================================================
# ГОЛОВНА ФУНКЦІЯ
# ============================================================================

def main():
    """Головна функція для запуску ICT бота."""
    import sys
    
    # Перевірка аргументів командного рядка
    global DEBUG_MODE
    if '--debug' in sys.argv or '-d' in sys.argv:
        DEBUG_MODE = True
        print("DEBUG MODE: ENABLED")
    
    print("=" * 80)
    print("ICT TRADING BOT - MULTI-TIMEFRAME SESSION ANALYSIS")
    print("=" * 80)
    
    try:
        # Завантаження даних
        print("\nЗавантаження даних...")
        m15, h4, d1, w1, m1 = load_data()
        print(f"✓ M15: {len(m15)} свічок")
        print(f"✓ H4:  {len(h4)} свічок")
        print(f"✓ D1:  {len(d1)} свічок")
        print(f"✓ W1:  {len(w1)} свічок")
        print(f"✓ M1:  {len(m1)} свічок")
        
        # Генерація сигналів
        print("\nАналіз даних та пошук сигналів...")
        signals = generate_signals(m15, h4, d1, w1, m1)
        
        # Виведення результатів
        print("\n" + "=" * 80)
        print(f"ЗНАЙДЕНО СИГНАЛІВ: {len(signals)}")
        print("=" * 80)
        
        if signals:
            for i, sig in enumerate(signals, 1):
                print(f"\n--- СИГНАЛ #{i} ---")
                print(f"Дата/Час:     {sig['datetime']}")
                print(f"Сесія:        {sig['session'].upper()}")
                print(f"Патерн:       {sig['pattern']}")
                print(f"Тип сигналу:  {sig['type']}")
                print(f"Впевненість:  {sig['confidence']}")
                print(f"Причина:      {sig['reason']}")
                print(f"Тренд H4:     {sig['trend_h4']}")
                print(f"Тренд D1:     {sig['trend_d1']}")
                print(f"Таймфрейми:   {sig['timeframes']}")
        else:
            print("\n⚠ Жоден патерн не виявлено.")
            print("Можливі причини:")
            print("  - Недостатньо історичних даних")
            print("  - Умови патернів не виконані")
            print("  - Потрібно більше даних для аналізу")
        
        print("\n" + "=" * 80)
        print("Аналіз завершено!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ ПОМИЛКА: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
