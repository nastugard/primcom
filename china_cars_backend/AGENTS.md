# Backend Instructions

Перед любыми изменениями в этом репозитории:

1. Обязательно прочитать `/Volumes/SID/Колян АВТО/CSS&HTML Site/china_cars_backend/BACKEND_RUNBOOK.md`.
2. Обязательно прочитать `/Volumes/SID/Колян АВТО/CSS&HTML Site/china_cars_backend/BACKEND_CHANGELOG.md` (последние записи).
3. Уточнить активный deploy-контур на сервере (`hostvds` или `hostvds-v2`) и работать только в нем.
4. Не давать команды/советы для неустановленных systemd unit.

После любых изменений:

1. Обновить `/Volumes/SID/Колян АВТО/CSS&HTML Site/china_cars_backend/BACKEND_RUNBOOK.md`.
2. Добавить запись в `/Volumes/SID/Колян АВТО/CSS&HTML Site/china_cars_backend/BACKEND_CHANGELOG.md` (что, зачем, файлы, проверка, действия на сервере).
3. При изменении env-параметров обновить шаблоны:
   - `/Volumes/SID/Колян АВТО/CSS&HTML Site/china_cars_backend/.env.example`
   - `/Volumes/SID/Колян АВТО/CSS&HTML Site/china_cars_backend/deploy/hostvds/.env.prod.example`
4. Проверить синтаксис измененных файлов (`python -m py_compile`, `bash -n` для shell).
