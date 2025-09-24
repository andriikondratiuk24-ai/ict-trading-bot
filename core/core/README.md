# ICT Trading Bot

Цей проєкт — модульний бот для трейдингу за методологією ICT (Inner Circle Trader).

## Структура проєкту

- `core/filters.py` — функції для визначення торгових сесій, ATR-фільтри, sweep-фільтри тощо.
- `core/decision_logic.py` — основна логіка прийняття торгових рішень (buy/sell/none).
- `core/filter_chain.py` — ланцюжок фільтрів для послідовної перевірки сигналу.
- `entrypoint.py` — стартовий скрипт для запуску логіки бота.

## Як запустити

1. Склонуйте репозиторій:
   ```bash
   git clone https://github.com/andriikondratiuk24-ai/ict-trading-bot.git
   cd ict-trading-bot
   ```
2. Запустіть файл:
   ```bash
   python entrypoint.py
   ```

## Контекст (параметри) для тесту

Ви можете змінювати тестовий контекст у `entrypoint.py`, щоб перевірити різні сценарії ринку.

---

**Цей проєкт — основа для побудови власної автоматизації трейдингу на Python.**
