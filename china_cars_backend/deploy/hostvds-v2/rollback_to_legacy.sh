#!/usr/bin/env bash
set -euo pipefail

systemctl disable --now primcom-scraper-v2.timer || true
systemctl stop primcom-scraper-v2.service || true
systemctl disable --now primcom-api-v2.service || true

systemctl enable --now primcom-api.service
systemctl enable --now primcom-scraper.timer

echo "Rolled back to legacy services"
