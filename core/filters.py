import datetime

def get_kyiv_session(now_utc=None):
    # Переводимо час UTC у Київський (UTC+3)
    if now_utc is None:
        now_utc = datetime.datetime.utcnow()
    kyiv_time = now_utc + datetime.timedelta(hours=3)
    hour = kyiv_time.hour
    minute = kyiv_time.minute
    h = hour*100 + minute

    if 300 <= h < 900:
        return "Asia"
    elif 700 <= h < 900:
        return "Frankfurt"
    elif 900 <= h < 1700:
        return "London"
    elif 1500 <= h < 2300:
        return "New_York"
    else:
        return "Other"

def atr_filter(current_atr, atr_min, avg_atr_50):
    return current_atr >= atr_min and current_atr > avg_atr_50

def sweep_fractal(high, low, fractal_highs, fractal_lows, pip):
    sweep_up = any([high > fh + pip for fh in fractal_highs])
    sweep_down = any([low < fl - pip for fl in fractal_lows])
    return sweep_up, sweep_down

def sweep_session(context):
    s = context.get("session")
    high = context.get("high")
    low = context.get("low")
    asia_high = context.get("asia_high_prev")
    asia_low = context.get("asia_low_prev")
    frankfurt_high = context.get("frankfurt_high_prev")
    frankfurt_low = context.get("frankfurt_low_prev")
    london_high = context.get("london_high_prev")
    london_low = context.get("london_low_prev")
    ny_high = context.get("ny_high_prev")
    ny_low = context.get("ny_low_prev")

    session_sweep_up = False
    session_sweep_down = False

    if s == "London":
        if high > asia_high:
            session_sweep_up = True
        if low < asia_low:
            session_sweep_down = True
        if high > frankfurt_high:
            session_sweep_up = True
        if low < frankfurt_low:
            session_sweep_down = True
    if s == "Frankfurt":
        if high > asia_high:
            session_sweep_up = True
        if low < asia_low:
            session_sweep_down = True
    if s == "New_York":
        if high > london_high:
            session_sweep_up = True
        if low < london_low:
            session_sweep_down = True

    return session_sweep_up, session_sweep_down

def imb_tested(context):
    return context.get("entry_imb", False)

def cisd_buy_sell(context):
    # Спрощено, в реалі треба price action + volume spike + BOS
    return context.get("cisd_buy_multi", False), context.get("cisd_sell_multi", False)
