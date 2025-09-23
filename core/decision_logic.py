from .filters import get_kyiv_session, atr_filter, sweep_fractal, sweep_session, imb_tested, cisd_buy_sell

def decide_signal(context):
    """
    Основна логіка прийняття рішення для ICT сигналу.
    Повертає 'buy', 'sell' або None.
    """

    # ATR фільтр
    atr_ok = atr_filter(context["current_atr"], context["atr_min"], context["avg_atr_50"])
    if not atr_ok:
        return None

    # Sweep fractal
    sweep_up, sweep_down = sweep_fractal(
        context["high"], context["low"],
        context["fractal_highs"], context["fractal_lows"], context["pip"]
    )

    # Sweep session
    session_sweep_up, session_sweep_down = sweep_session(context)

    # IMB (imbalance) протестовано
    imb_ok = imb_tested(context)

    # CISD сигнали
    cisd_buy, cisd_sell = cisd_buy_sell(context)

    # Логіка для buy
    if (sweep_down or session_sweep_down) and imb_ok and cisd_buy:
        return "buy"

    # Логіка для sell
    if (sweep_up or session_sweep_up) and imb_ok and cisd_sell:
        return "sell"

    # Якщо не виконано умови — немає сигналу
    return None
