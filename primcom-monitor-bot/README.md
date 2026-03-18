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

## Production схема

Рекомендуемая схема:

- `primcom-monitor-bot` живет на отдельном сервере;
- целевой сервер с рабочими контейнерами `primcom-bot` и `primcom-lead-api` сейчас: `213.232.204.127`;
- alert-уведомления отправляются в ту же группу, куда приходят заявки;
- доступ к целевому серверу идет по отдельному SSH-ключу monitor-бота.

## Пошаговый деплой

### 1. Создать Telegram-бота

Через `@BotFather` создать нового бота и получить `MONITOR_BOT_TOKEN`.

### 2. Узнать chat_id группы заявок

Взять текущий `GROUP_ID` или `TELEGRAM_GROUP_ID` из окружения рабочего контура `primcom_bot`.

### 3. Подготовить сервер monitor-бота

```bash
apt update
apt install -y python3 python3-venv python3-pip openssh-client rsync
mkdir -p /opt/primcom/primcom-monitor-bot
```

### 4. Залить код

С локальной машины:

```bash
cd "/Volumes/SID/Колян АВТО/CSS&HTML Site/primcom-monitor-bot"
rsync -av --exclude '.venv' --exclude '__pycache__' --exclude '.DS_Store' ./ root@MONITOR_SERVER_IP:/opt/primcom/primcom-monitor-bot/
```

### 5. Сгенерировать SSH-ключ monitor-бота

На сервере monitor-бота:

```bash
mkdir -p /opt/primcom/primcom-monitor-bot
chmod 700 /opt/primcom/primcom-monitor-bot
ssh-keygen -t ed25519 -N '' -f /opt/primcom/primcom-monitor-bot/id_ed25519
cat /opt/primcom/primcom-monitor-bot/id_ed25519.pub
```

### 6. Добавить публичный ключ на целевой сервер

Публичный ключ нужно добавить в `~/.ssh/authorized_keys` пользователя, под которым monitor-бот будет подключаться к целевому хосту.

### 7. Подготовить `.env`

Пример:

```env
MONITOR_BOT_TOKEN=...
MONITOR_ALERT_CHAT_ID=-100...
MONITOR_ALLOWED_IDS=
TARGET_HOST=213.232.204.127
TARGET_USER=root
TARGET_PORT=22
SSH_IDENTITY_FILE=/opt/primcom/primcom-monitor-bot/id_ed25519
SSH_CONNECT_TIMEOUT_SECONDS=10
MONITOR_CONTAINERS=primcom-bot,primcom-lead-api
CHECK_INTERVAL_SECONDS=60
SEND_RECOVERY_ALERT=0
PUBLIC_HEALTHCHECK_URL=
HTTP_TIMEOUT_SECONDS=10
```

### 8. Установить зависимости и systemd unit

```bash
cd /opt/primcom/primcom-monitor-bot
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp deploy/primcom-monitor-bot.service /etc/systemd/system/primcom-monitor-bot.service
systemctl daemon-reload
systemctl enable primcom-monitor-bot.service
systemctl restart primcom-monitor-bot.service
systemctl status primcom-monitor-bot.service --no-pager
```

### 9. Проверка

- В Telegram отправить `/start`, затем `/status`.
- На целевом сервере временно остановить `primcom-bot` и убедиться, что monitor-бот присылает alert.
- После проверки вернуть контейнер в `running`.

## Что считается аварией

- SSH на целевой сервер недоступен;
- контейнер `primcom-bot` отсутствует или не `running`;
- контейнер `primcom-lead-api` отсутствует или не `running`;
- если задан `PUBLIC_HEALTHCHECK_URL`, его ответ вне `2xx`.
