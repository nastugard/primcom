# Primcom Translation Proxy

Мини-сервис для вынесения перевода (OpenAI) на зарубежный сервер.

## Endpoints

- `GET /health`
- `POST /translate` body: `{"text":"..."}`
- `POST /translate-batch` body: `{"values":["...","..."]}`

Если задан `TRANSLATION_PROXY_TOKEN`, запросы должны идти с заголовком:

`Authorization: Bearer <TOKEN>`

## Быстрый запуск

1. Создать рабочую директорию:
`/opt/primcom/translation-proxy`
2. Положить туда `translator_proxy.py`
3. Создать venv и установить:
`fastapi uvicorn openai pydantic`
4. Создать `.env` c `OPENAI_API_KEY`, `OPENAI_TRANSLATION_MODEL`, `TRANSLATION_PROXY_TOKEN`
5. Установить systemd unit `primcom-translation-proxy.service`
6. Запустить сервис и проверить:
`curl -s http://127.0.0.1:8040/health`
7. Ограничить доступ на порт 8040 (UFW) только с IP российского парсер-сервера.
