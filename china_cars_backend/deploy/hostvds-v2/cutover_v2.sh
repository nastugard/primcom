#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/primcom/china_cars_backend"
cd "$APP_DIR"
source .venv/bin/activate

python -m app.scripts.init_db

cp "$APP_DIR/deploy/hostvds-v2/primcom-api-v2.service" /etc/systemd/system/
cp "$APP_DIR/deploy/hostvds-v2/primcom-scraper-v2.service" /etc/systemd/system/
cp "$APP_DIR/deploy/hostvds-v2/primcom-scraper-v2.timer" /etc/systemd/system/
chmod +x "$APP_DIR/deploy/hostvds-v2/run_ingest_v2.sh"
chmod +x "$APP_DIR/deploy/hostvds-v2/rollback_to_legacy.sh"

systemctl daemon-reload

systemctl disable --now primcom-api.service || true
systemctl disable --now primcom-scraper.timer || true

systemctl enable --now primcom-api-v2.service
systemctl enable --now primcom-scraper-v2.timer

echo "Cutover v2 done"
systemctl status primcom-api-v2.service --no-pager -l || true
systemctl status primcom-scraper-v2.timer --no-pager -l || true
