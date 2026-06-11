#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/primcom/china_cars_backend"
cd "$APP_DIR"

source .venv/bin/activate

CHINA_LIMIT="${EXTERNAL_MARKET_CHINA_DAILY_LIMIT:-3}"
KOREA_LIMIT="${EXTERNAL_MARKET_KOREA_DAILY_LIMIT:-3}"
MAX_PAGES="${EXTERNAL_MARKET_MAX_PAGES:-20}"
MAX_IMAGES="${EXTERNAL_MARKET_MAX_IMAGES:-10}"
THROTTLE_MS="${EXTERNAL_MARKET_THROTTLE_MS:-1000}"

python -m app.scripts.scrape_external_market_daily \
  --china-limit "$CHINA_LIMIT" \
  --korea-limit "$KOREA_LIMIT" \
  --max-pages "$MAX_PAGES" \
  --max-images "$MAX_IMAGES" \
  --throttle-ms "$THROTTLE_MS"
