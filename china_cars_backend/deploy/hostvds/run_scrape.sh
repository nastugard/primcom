#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/primcom/china_cars_backend"
cd "$APP_DIR"

# Activate virtualenv
source .venv/bin/activate

# Read params from .env (fallback defaults tuned for catalog growth)
SOURCE="${SCRAPER_SOURCE:-guazi}"
NEW_LIMIT="${DAILY_NEW_LIMIT:-30}"
DEL_LIMIT="${DAILY_DELETE_LIMIT:-0}"
MAX_IMAGES="${CHE168_MAX_IMAGES:-12}"
THROTTLE_MS="${SCRAPER_THROTTLE_MS:-700}"
SKIP_EXISTING="${SCRAPER_SKIP_EXISTING:-1}"
ALLOW_NON_ENGLISH="${SCRAPER_ALLOW_NON_ENGLISH:-1}"
TRANSLATE_CHINESE="${SCRAPER_TRANSLATE_CHINESE:-1}"

ARGS=(
  --source "$SOURCE"
  --limit "$NEW_LIMIT"
  --delete-old "$DEL_LIMIT"
  --max-images "$MAX_IMAGES"
  --throttle-ms "$THROTTLE_MS"
)

if [[ "$SKIP_EXISTING" == "1" ]]; then
  ARGS+=(--skip-existing)
else
  ARGS+=(--no-skip-existing)
fi

if [[ "$ALLOW_NON_ENGLISH" == "1" ]]; then
  ARGS+=(--allow-non-english-brand)
fi

if [[ "$TRANSLATE_CHINESE" == "1" ]]; then
  ARGS+=(--translate-chinese)
fi

python -m app.scripts.scrape_che168 "${ARGS[@]}"
