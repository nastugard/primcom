#!/usr/bin/env bash
set -euo pipefail

TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="/opt/primcom/backups/${TS}"
APP_DIR="/opt/primcom/china_cars_backend"
mkdir -p "$BACKUP_DIR"

# DB dump
sudo -u postgres pg_dump -Fc primcom_china_cars -f "${BACKUP_DIR}/primcom_china_cars.dump"

# media backup
tar -C "$APP_DIR" -czf "${BACKUP_DIR}/media.tar.gz" data/media || true

# service/nginx backups
cp -a /etc/systemd/system/primcom-api.service "${BACKUP_DIR}/" 2>/dev/null || true
cp -a /etc/systemd/system/primcom-scraper.service "${BACKUP_DIR}/" 2>/dev/null || true
cp -a /etc/systemd/system/primcom-scraper.timer "${BACKUP_DIR}/" 2>/dev/null || true
cp -a /etc/nginx/sites-enabled/primcom-api "${BACKUP_DIR}/nginx-primcom-api.conf" 2>/dev/null || true

# freeze legacy jobs during migration
systemctl disable --now primcom-scraper.timer || true
systemctl stop primcom-scraper.service || true

echo "Backup+freeze done: ${BACKUP_DIR}"
