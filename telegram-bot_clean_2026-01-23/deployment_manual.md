# Инструкция по деплою бота на сервер (HostVDS)

Эта инструкция поможет:

- запустить **Telegram-бота** (polling)
- запустить **HTTP API** для сайта: `POST https://api.primcom.ru/api/lead`
- настроить **Nginx + HTTPS** (Let's Encrypt) для домена `api.primcom.ru`

## 0. Что важно знать заранее

- Сайт (статические файлы) вы выкладываете на reg.ru, а приём заявок делаем на HostVDS.
- Когда сайт будет на `https://primcom.ru`, браузер **не позволит** отправлять заявки на `http://IP:порт`. Поэтому API обязательно должен быть на **HTTPS** (например, `https://api.primcom.ru`).

## 1. DNS на reg.ru (обязательно перед получением SSL)

В панели reg.ru для домена `primcom.ru` добавьте запись:

- **A-запись**
  - Имя/хост: `api`
  - Значение: `213.232.204.127`

Подождите обновления DNS (обычно 5–60 минут, иногда до нескольких часов).

## 2. Подготовка файлов на Mac

### 2.1 Проверьте `.env`

Файл: `telegram-bot/.env`

Нужно заполнить:

- `BOT_TOKEN=...`
- `GROUP_ID=-1003540261166`

Рекомендуемые дополнительные переменные:

- `LEAD_API_PORT=8080`
- `ALLOWED_ORIGINS=https://primcom.ru,https://www.primcom.ru`
- `RATE_LIMIT_PER_MINUTE=20`

Опционально (простая защита от случайного спама):

- `LEAD_API_TOKEN=любая_строка`

Важно: `LEAD_API_TOKEN` нельзя считать секретом, если вы задаёте его на фронте (его можно подсмотреть в браузере). Основная защита — rate limit и фильтрация.

## 3. Подключение к серверу (HostVDS)

Откройте Терминал на Mac:

```bash
ssh root@213.232.204.127
```

Введите пароль (символы не отображаются — это нормально).

## 4. Установка Docker + Nginx (на сервере)

### 4.1 Обновление пакетов

```bash
apt update
apt -y upgrade
```

### 4.2 Docker

```bash
curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh
```

Проверка:

```bash
docker --version
```

### 4.3 Nginx

```bash
apt install -y nginx
systemctl enable nginx
systemctl start nginx
```

## 5. Загрузка папки `telegram-bot` на сервер (с Mac)

Не закрывая SSH-сессию, откройте **второе** окно Терминала на Mac.

1) Перейдите в папку проекта на Mac:

```bash
cd "/Volumes/SID/Колян АВТО/CSS&HTML Site"
```

2) Загрузите папку `telegram-bot` на сервер:

```bash
scp -r "telegram-bot" root@213.232.204.127:/root/
```

## 6. Запуск контейнеров (на сервере)

Вернитесь в SSH-окно (где вы подключены к серверу).

### 6.1 Перейдите в папку

```bash
cd /root/telegram-bot
```

### 6.2 Соберите Docker-образ

```bash
docker build -t primcom-telegram .
```

### 6.3 Запустите Telegram-бота (polling)

Если был старый контейнер — остановить/удалить:

```bash
docker stop primcom-bot || true
docker rm primcom-bot || true
```

Запуск:

```bash
docker run -d --restart=always --env-file .env --name primcom-bot primcom-telegram
```

### 6.4 Запустите Lead API (`POST /api/lead`)

Остановить/удалить если был:

```bash
docker stop primcom-lead-api || true
docker rm primcom-lead-api || true
```

Запуск (порт наружу не светим, только localhost:8080):

```bash
docker run -d --restart=always --env-file .env -p 127.0.0.1:8080:8080 --name primcom-lead-api primcom-telegram python lead_api.py
```

Проверка:

```bash
docker ps
```

Вы должны увидеть:

- `primcom-bot`
- `primcom-lead-api`

## 7. Nginx proxy для `api.primcom.ru`

### 7.1 Создайте конфиг

Создайте файл:

`/etc/nginx/sites-available/api.primcom.ru`

Содержимое:

```nginx
server {
  listen 80;
  server_name api.primcom.ru;

  location /api/lead {
    proxy_pass http://127.0.0.1:8080;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
```

Включите сайт и перезагрузите nginx:

```bash
ln -sf /etc/nginx/sites-available/api.primcom.ru /etc/nginx/sites-enabled/api.primcom.ru
nginx -t
systemctl reload nginx
```

## 8. HTTPS (Let's Encrypt) для `api.primcom.ru`

Установите certbot:

```bash
apt install -y certbot python3-certbot-nginx
```

Выпустите сертификат:

```bash
certbot --nginx -d api.primcom.ru
```

Проверка автообновления:

```bash
certbot renew --dry-run
```

## 9. Проверка API

### 9.1 Проверка с сервера

```bash
curl -i -X POST http://127.0.0.1:8080/api/lead \
  -H 'Content-Type: application/json' \
  -d '{"name":"Тест","phone":"+79990000000","comment":"Проверка"}'
```

### 9.2 Проверка с компьютера (после HTTPS)

```bash
curl -i -X POST https://api.primcom.ru/api/lead \
  -H 'Content-Type: application/json' \
  -d '{"name":"Тест","phone":"+79990000000","comment":"Проверка"}'
```

Если всё ок — сообщение придёт в группу.

## 10. Как обновлять код

1) На Mac снова сделайте `scp -r telegram-bot root@213.232.204.127:/root/`
2) На сервере:

```bash
cd /root/telegram-bot

docker stop primcom-bot primcom-lead-api || true
docker rm primcom-bot primcom-lead-api || true

docker build -t primcom-telegram .

docker run -d --restart=always --env-file .env --name primcom-bot primcom-telegram
docker run -d --restart=always --env-file .env -p 127.0.0.1:8080:8080 --name primcom-lead-api primcom-telegram python lead_api.py