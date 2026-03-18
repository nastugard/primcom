# Primcom Monitor Bot

Отдельный Telegram-бот для мониторинга `primcom_bot` и связанных контейнеров на удаленном сервере.

Сценарий:

- монитор-бот работает на отдельной машине;
- по SSH проверяет статус контейнеров на целевом сервере;
- если обязательный контейнер не `running`, отправляет alert в группу заявок;
- если всё штатно, молчит;
- по команде `/status` или `/check` присылает текущий статус вручную.

## Что мониторит

По умолчанию:

- `primcom-bot`
- `primcom-lead-api`

Список можно менять через `MONITOR_CONTAINERS`.

## Как это устроено

- монитор не зависит от polling основного `primcom_bot`;
- проверка идет через SSH на целевой хост;
- целевой хост для текущего контура: `213.232.204.127`.

## Переменные окружения

Обязательные:

- `MONITOR_BOT_TOKEN`
- `MONITOR_ALERT_CHAT_ID`
- `TARGET_HOST`

Рекомендуемые:

- `TARGET_USER=root`
- `TARGET_PORT=22`
- `SSH_IDENTITY_FILE=/opt/primcom/primcom-monitor-bot/id_ed25519`
- `MONITOR_ALLOWED_IDS=...`
- `MONITOR_CONTAINERS=primcom-bot,primcom-lead-api`
- `CHECK_INTERVAL_SECONDS=60`

Опционально:

- `PUBLIC_HEALTHCHECK_URL=https://api.primcom.ru/health`
- `SEND_RECOVERY_ALERT=0`

## Команды в Telegram

- `/start` — краткая справка
- `/status` — текущий статус мониторинга
- `/check` — то же самое, явная ручная проверка

## Быстрый запуск локально

```bash
cd primcom-monitor-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

## Важное по SSH

- лучше использовать отдельный SSH-ключ только для мониторинга;
- на целевом сервере ключу достаточно прав на выполнение `docker inspect` и, при необходимости, `curl`;
- если монитор-бот и целевой сервер находятся на одной машине, такой монитор не увидит полное падение хоста. Надежнее держать monitor-бот на отдельном сервере.
