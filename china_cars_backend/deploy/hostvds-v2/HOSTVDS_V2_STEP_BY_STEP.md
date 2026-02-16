# Primcom Backend v2 - Step by step

## 0) Backup + Freeze
```bash
cd /opt/primcom/china_cars_backend
chmod +x deploy/hostvds-v2/backup_freeze_v2.sh
./deploy/hostvds-v2/backup_freeze_v2.sh
```

## 1) Sync code to server
Use rsync/scp from local project to `/opt/primcom/china_cars_backend`.

## 2) Install deps (if needed)
```bash
cd /opt/primcom/china_cars_backend
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
python -m playwright install-deps chromium
```

## 3) Cutover to v2
```bash
cd /opt/primcom/china_cars_backend
chmod +x deploy/hostvds-v2/cutover_v2.sh
./deploy/hostvds-v2/cutover_v2.sh
```

## 4) Manual smoke run
```bash
cd /opt/primcom/china_cars_backend
source .venv/bin/activate
python -m app.jobs.run_ingest --sources che168,dongchedi,guazi --limit 20 --max-images 6 --skip-existing --throttle-ms 700
curl -s "https://api.primcom.ru/api/auto-iz-kitaya?source=all&limit=5&offset=0"
curl -s "https://api.primcom.ru/api/scrape-runs?source=all&limit=10"
```

## 5) Rollback
```bash
cd /opt/primcom/china_cars_backend
chmod +x deploy/hostvds-v2/rollback_to_legacy.sh
./deploy/hostvds-v2/rollback_to_legacy.sh
```
