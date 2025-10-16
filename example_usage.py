#!/usr/bin/env python3
"""
ICT Trading Bot - Example Usage Script

This script demonstrates different ways to use the ICT bot
and shows how to filter signals by different criteria.
"""

import pandas as pd
from datetime import datetime
from ict_bot import (
    load_data, 
    generate_signals,
    get_session,
    DEBUG_MODE
)

def print_header(title):
    """Друкує красивий заголовок."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def filter_signals_by_pattern(signals, pattern_name):
    """Фільтрує сигнали за типом патерну."""
    return [s for s in signals if s['pattern'] == pattern_name]

def filter_signals_by_session(signals, session_name):
    """Фільтрує сигнали за сесією."""
    return [s for s in signals if s['session'].lower() == session_name.lower()]

def filter_signals_by_confidence(signals, min_confidence):
    """Фільтрує сигнали за рівнем впевненості."""
    confidence_levels = {
        'VERY HIGH': 3,
        'HIGH': 2,
        'MEDIUM-HIGH': 1
    }
    min_level = confidence_levels.get(min_confidence, 0)
    return [s for s in signals if confidence_levels.get(s['confidence'], 0) >= min_level]

def filter_signals_by_timeframe(signals, timeframe):
    """Фільтрує сигнали за таймфреймом sweep."""
    return [s for s in signals if timeframe in s['timeframes']]

def print_signal_summary(signals):
    """Виводить короткий звіт по сигналах."""
    if not signals:
        print("⚠ Сигналів не знайдено.")
        return
    
    print(f"\n📊 Всього сигналів: {len(signals)}")
    
    # Підрахунок по патернах
    pattern_counts = {}
    for sig in signals:
        pattern = sig['pattern']
        pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
    
    print("\n📋 Розподіл по патернах:")
    for pattern, count in sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  • {pattern}: {count} сигналів")
    
    # Підрахунок по сесіях
    session_counts = {}
    for sig in signals:
        session = sig['session']
        session_counts[session] = session_counts.get(session, 0) + 1
    
    print("\n🕐 Розподіл по сесіях:")
    for session, count in sorted(session_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  • {session}: {count} сигналів")
    
    # Підрахунок BUY vs SELL
    buy_count = sum(1 for s in signals if s['type'] == 'BUY')
    sell_count = sum(1 for s in signals if s['type'] == 'SELL')
    
    print("\n📈 Розподіл по типу:")
    print(f"  • BUY: {buy_count} сигналів")
    print(f"  • SELL: {sell_count} сигналів")

def print_signal(sig, index):
    """Виводить один сигнал у красивому форматі."""
    print(f"\n--- СИГНАЛ #{index} ---")
    print(f"🕐 Дата/Час:     {sig['datetime']}")
    print(f"📍 Сесія:        {sig['session'].upper()}")
    print(f"🎯 Патерн:       {sig['pattern']}")
    print(f"{'📈' if sig['type'] == 'BUY' else '📉'} Тип сигналу:  {sig['type']}")
    print(f"✅ Впевненість:  {sig['confidence']}")
    print(f"💡 Причина:      {sig['reason']}")
    print(f"📊 Тренд H4:     {sig['trend_h4']}")
    print(f"📊 Тренд D1:     {sig['trend_d1']}")
    print(f"⏰ Таймфрейми:   {sig['timeframes']}")

def example_1_all_signals():
    """Приклад 1: Виведення всіх сигналів."""
    print_header("ПРИКЛАД 1: Всі сигнали")
    
    print("\nЗавантаження даних...")
    m15, h4, d1, w1, m1 = load_data()
    
    print("Генерація сигналів...")
    signals = generate_signals(m15, h4, d1, w1, m1)
    
    print_signal_summary(signals)
    
    # Показуємо перші 5 сигналів
    print("\n" + "-" * 80)
    print("Перші 5 сигналів:")
    print("-" * 80)
    for i, sig in enumerate(signals[:5], 1):
        print_signal(sig, i)

def example_2_double_sweep_only():
    """Приклад 2: Тільки Double Sweep сигнали."""
    print_header("ПРИКЛАД 2: Тільки Double Sweep сигнали")
    
    m15, h4, d1, w1, m1 = load_data()
    signals = generate_signals(m15, h4, d1, w1, m1)
    
    double_sweep_signals = filter_signals_by_pattern(signals, "Double Sweep")
    
    print(f"\n✨ Знайдено {len(double_sweep_signals)} Double Sweep сигналів")
    print_signal_summary(double_sweep_signals)
    
    # Показуємо перші 3 сигнали
    print("\n" + "-" * 80)
    print("Перші 3 Double Sweep сигнали:")
    print("-" * 80)
    for i, sig in enumerate(double_sweep_signals[:3], 1):
        print_signal(sig, i)

def example_3_london_session():
    """Приклад 3: Сигнали тільки з London сесії."""
    print_header("ПРИКЛАД 3: Сигнали London сесії")
    
    m15, h4, d1, w1, m1 = load_data()
    signals = generate_signals(m15, h4, d1, w1, m1)
    
    london_signals = filter_signals_by_session(signals, "london")
    
    print(f"\n🇬🇧 Знайдено {len(london_signals)} сигналів у London сесії")
    print_signal_summary(london_signals)
    
    # Показуємо всі London сигнали (якщо їх не багато)
    if len(london_signals) <= 5:
        print("\n" + "-" * 80)
        print("Всі London сигнали:")
        print("-" * 80)
        for i, sig in enumerate(london_signals, 1):
            print_signal(sig, i)
    else:
        print("\n" + "-" * 80)
        print("Перші 5 London сигналів:")
        print("-" * 80)
        for i, sig in enumerate(london_signals[:5], 1):
            print_signal(sig, i)

def example_4_high_confidence():
    """Приклад 4: Тільки високо впевнені сигнали."""
    print_header("ПРИКЛАД 4: Високо впевнені сигнали (VERY HIGH)")
    
    m15, h4, d1, w1, m1 = load_data()
    signals = generate_signals(m15, h4, d1, w1, m1)
    
    high_conf_signals = filter_signals_by_confidence(signals, "VERY HIGH")
    
    print(f"\n⭐ Знайдено {len(high_conf_signals)} сигналів з VERY HIGH впевненістю")
    print_signal_summary(high_conf_signals)

def example_5_buy_signals_only():
    """Приклад 5: Тільки BUY сигнали."""
    print_header("ПРИКЛАД 5: Тільки BUY сигнали")
    
    m15, h4, d1, w1, m1 = load_data()
    signals = generate_signals(m15, h4, d1, w1, m1)
    
    buy_signals = [s for s in signals if s['type'] == 'BUY']
    
    print(f"\n📈 Знайдено {len(buy_signals)} BUY сигналів")
    print_signal_summary(buy_signals)
    
    # Показуємо перші 3 BUY сигнали
    print("\n" + "-" * 80)
    print("Перші 3 BUY сигнали:")
    print("-" * 80)
    for i, sig in enumerate(buy_signals[:3], 1):
        print_signal(sig, i)

def example_6_pattern_comparison():
    """Приклад 6: Порівняння ефективності патернів."""
    print_header("ПРИКЛАД 6: Порівняння патернів")
    
    m15, h4, d1, w1, m1 = load_data()
    signals = generate_signals(m15, h4, d1, w1, m1)
    
    print("\n📊 Аналіз патернів:")
    print("-" * 80)
    
    pattern_names = [
        "Sweep + FVG + CISD",
        "Double Sweep",
        "Session Open Liquidity Grab",
        "BOS after Sweep",
        "Asia/Frankfurt Context"
    ]
    
    for pattern in pattern_names:
        pattern_signals = filter_signals_by_pattern(signals, pattern)
        buy_count = sum(1 for s in pattern_signals if s['type'] == 'BUY')
        sell_count = sum(1 for s in pattern_signals if s['type'] == 'SELL')
        
        print(f"\n🎯 {pattern}")
        print(f"   Всього: {len(pattern_signals)} сигналів")
        if len(pattern_signals) > 0:
            buy_pct = (buy_count / len(pattern_signals)) * 100
            sell_pct = (sell_count / len(pattern_signals)) * 100
            print(f"   BUY:  {buy_count} ({buy_pct:.1f}%)")
            print(f"   SELL: {sell_count} ({sell_pct:.1f}%)")

def example_7_custom_filter():
    """Приклад 7: Власний фільтр (London + BUY + VERY HIGH)."""
    print_header("ПРИКЛАД 7: Власний фільтр (London + BUY + VERY HIGH)")
    
    m15, h4, d1, w1, m1 = load_data()
    signals = generate_signals(m15, h4, d1, w1, m1)
    
    # Застосовуємо кілька фільтрів
    filtered = signals
    filtered = filter_signals_by_session(filtered, "london")
    filtered = [s for s in filtered if s['type'] == 'BUY']
    filtered = filter_signals_by_confidence(filtered, "VERY HIGH")
    
    print(f"\n🎯 Знайдено {len(filtered)} сигналів з комбінованим фільтром:")
    print("   • Сесія: London")
    print("   • Тип: BUY")
    print("   • Впевненість: VERY HIGH")
    
    if len(filtered) > 0:
        print_signal_summary(filtered)
        print("\n" + "-" * 80)
        print("Відфільтровані сигнали:")
        print("-" * 80)
        for i, sig in enumerate(filtered[:5], 1):
            print_signal(sig, i)
    else:
        print("\n⚠ Сигналів не знайдено з такими критеріями.")

def main():
    """Головна функція для запуску прикладів."""
    print("=" * 80)
    print(" " * 20 + "ICT TRADING BOT - EXAMPLES")
    print("=" * 80)
    
    examples = [
        ("Всі сигнали", example_1_all_signals),
        ("Double Sweep тільки", example_2_double_sweep_only),
        ("London сесія", example_3_london_session),
        ("Високо впевнені", example_4_high_confidence),
        ("BUY сигнали", example_5_buy_signals_only),
        ("Порівняння патернів", example_6_pattern_comparison),
        ("Власний фільтр", example_7_custom_filter),
    ]
    
    print("\nДоступні приклади:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")
    print("  0. Всі приклади")
    print("  q. Вихід")
    
    max_example_num = len(examples)
    
    while True:
        choice = input(f"\nОберіть приклад (0-{max_example_num}, q для виходу): ").strip().lower()
        
        if choice == 'q':
            print("\nДо побачення! 👋")
            break
        
        if choice == '0':
            # Запустити всі приклади
            for name, func in examples:
                func()
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(examples):
                examples[idx][1]()
            else:
                print("❌ Невірний номер прикладу!")
        else:
            print("❌ Невірний вибір!")

if __name__ == "__main__":
    main()
