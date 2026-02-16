#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/primcom/china_cars_backend"
cd "$APP_DIR"
source .venv/bin/activate

SOURCES="${SCRAPER_SOURCES:-che168,dongchedi,guazi}"
LIMIT="${DAILY_NEW_LIMIT:-75}"
MAX_IMAGES="${CHE168_MAX_IMAGES:-10}"
THROTTLE_MS="${SCRAPER_THROTTLE_MS:-700}"
SKIP_EXISTING="${SCRAPER_SKIP_EXISTING:-1}"

ARGS=(
  --sources "$SOURCES"
  --limit "$LIMIT"
  --max-images "$MAX_IMAGES"
  --throttle-ms "$THROTTLE_MS"
)

if [[ "$SKIP_EXISTING" == "1" ]]; then
  ARGS+=(--skip-existing)
fi

python -m app.jobs.run_ingest "${ARGS[@]}"
