# Manager Listings Bot (Korea/Japan)

Отдельный Telegram-бот для менеджера. Собирает данные карточки в диалоге и отправляет в backend:
`POST /api/manager/manual-listing`.

Этот бот НЕ связан со старым `telegram-bot_clean_2026-01-23`.

## Что бот собирает
- площадка (Корея/Япония)
- марка
- модель
- год
- привод
- объем двигателя
- л.с.
- кузов
- комплектация
- цена
- фото (минимум 1)

## Быстрый запуск локально

```bash
cd manager-listings-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# заполните BOT_TOKEN / MANAGER_API_KEY / MANAGER_ALLOWED_IDS
python main.py
```

## Команды в Telegram
- `/new` — новая карточка
- `/cancel` — отменить текущий диалог

## Безопасность
- В `.env` задайте `MANAGER_ALLOWED_IDS` (список user_id через запятую).
- На backend в `.env` должен быть тот же `MANAGER_API_KEY`, который бот шлет в `X-Manager-Api-Key`.
