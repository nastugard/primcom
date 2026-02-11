#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/primcom/china_cars_backend"
cd "$APP_DIR"

# Activate virtualenv
source .venv/bin/activate

# Read limits from .env (fallback defaults)
NEW_LIMIT="${DAILY_NEW_LIMIT:-5}"
DEL_LIMIT="${DAILY_DELETE_LIMIT:-5}"

# Single source currently in production: guazi
python -m app.scripts.scrape_che168 \
  --source guazi \
  --limit "$NEW_LIMIT" \
  --delete-old "$DEL_LIMIT" \
  --skip-existing \
  --translate-chinese \
  --max-images 10
