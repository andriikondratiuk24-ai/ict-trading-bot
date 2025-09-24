from core.decision_logic import decide_signal
from core.filter_chain import FilterChain

def main(context):
    # Запускаємо ланцюжок фільтрів
    chain = FilterChain(context)
    passed = chain.run()

    if not passed:
        print("Фільтри не пройдені, сигналу немає.")
        return None

    # Основна логіка прийняття рішення
    signal = decide_signal(context)
    if signal == "buy":
        print("Buy Signal!")
    elif signal == "sell":
        print("Sell Signal!")
    else:
        print("Сигналу немає.")
    return signal

if __name__ == "__main__":
    # Приклад тестового контексту
    context = {
        "current_atr": 0.002,
        "atr_min": 0.0015,
        "avg_atr_50": 0.0014,
        "high": 1.2345,
        "low": 1.2301,
        "fractal_highs": [1.2330, 1.2335],
        "fractal_lows": [1.2300, 1.2302],
        "pip": 0.0002,
        "session": "London",
        "asia_high_prev": 1.2330,
        "asia_low_prev": 1.2300,
        "frankfurt_high_prev": 1.2335,
        "frankfurt_low_prev": 1.2302,
        "london_high_prev": 1.2340,
        "london_low_prev": 1.2310,
        "ny_high_prev": 1.2350,
        "ny_low_prev": 1.2315,
        "entry_imb": True,
        "cisd_buy_multi": True,
        "cisd_sell_multi": False,
    }
    main(context)
