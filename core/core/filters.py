def get_kyiv_session(dt):
    hour = dt.hour
    if 3 <= hour < 9:
        return "Asia"
    elif 9 <= hour < 11:
        return "Frankfurt"
    elif 11 <= hour < 17:
        return "London"
    elif 17 <= hour < 24 or 0 <= hour < 3:
        return "New_York"
    return "Unknown"

def atr_filter(current_atr, atr_min, avg_atr_50):
    return current_atr > atr_min and current_atr > avg_atr_50

def sweep_fractal(high, low, fractal_highs, fractal_lows, pip):
    sweep_up = any(high >= h + pip for h in fractal_highs)
    sweep_down = any(low <= l - pip for l in fractal_lows)
    return sweep_up, sweep_down

def sweep_session(context):
    s = context.get("session")
    high = context.get("high")
    low = context.get("low")
    session_sweep_up = session_sweep_down = False

    if s == "Asia":
        if high > context.get("asia_high_prev", 0):
            session_sweep_up = True
        if low < context.get("asia_low_prev", 0):
            session_sweep_down = True
    elif s == "Frankfurt":
        if high > context.get("frankfurt_high_prev", 0):
            session_sweep_up = True
        if low < context.get("frankfurt_low_prev", 0):
            session_sweep_down = True
    elif s == "London":
        if high > context.get("london_high_prev", 0):
            session_sweep_up = True
        if low < context.get("london_low_prev", 0):
            session_sweep_down = True
    elif s == "New_York":
        if high > context.get("ny_high_prev", 0):
            session_sweep_up = True
        if low < context.get("ny_low_prev", 0):
            session_sweep_down = True

    return session_sweep_up, session_sweep_down

def imb_tested(context):
    return context.get("entry_imb", False)

def cisd_buy_sell(context):
    return context.get("cisd_buy_multi", False), context.get("cisd_sell_multi", False)
