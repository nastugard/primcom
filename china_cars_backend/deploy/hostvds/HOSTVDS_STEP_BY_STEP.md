# HostVDS deploy (copy/paste)

## Ready-to-run for your server

Use these concrete values:
- Server IP: `213.232.204.127`
- Linux user: `root`
- API domain: `api.primcom.ru`
- Source in scheduler: `guazi` only

---

## 0) DNS first (required for SSL)

In REG.RU DNS panel create record:
- Type: `A`
- Host: `api`
- Value: `213.232.204.127`
- TTL: default

Wait until record resolves:
```bash
dig +short api.primcom.ru
```
Expected: `213.232.204.127`

---

## 1) Local Mac: upload project files

Run on your Mac terminal:
```bash
rsync -av --delete \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.DS_Store' \
  "/Users/ivannastugard/Documents/New project/china_cars_backend/" \
  root@213.232.204.127:/opt/primcom/china_cars_backend/
```

---

## 2) Server: install packages

```bash
ssh root@213.232.204.127
sudo apt update && sudo apt -y upgrade
sudo apt -y install python3.11 python3.11-venv python3-pip postgresql postgresql-contrib nginx git curl
```

---

## 3) Server: create app folder (if first deploy)

```bash
sudo mkdir -p /opt/primcom
sudo chown -R root:root /opt/primcom
mkdir -p /opt/primcom/china_cars_backend
```

If you did not run step 1 before this step, run step 1 now (on local Mac), then return here.

---

## 4) Server: Python env + dependencies

```bash
cd /opt/primcom/china_cars_backend
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
python -m playwright install chromium
```

---

## 5) Server: PostgreSQL setup

```bash
sudo -u postgres psql <<'SQL'
CREATE USER primcom WITH PASSWORD 'Woixzpen5113!';
CREATE DATABASE primcom_china_cars OWNER primcom;
GRANT ALL PRIVILEGES ON DATABASE primcom_china_cars TO primcom;
SQL
```

---

## 6) Server: create `.env` without manual editing

```bash
cat > /opt/primcom/china_cars_backend/.env <<'EOF'
POSTGRES_DB=primcom_china_cars
POSTGRES_USER=primcom
POSTGRES_PASSWORD=Woixzpen5113!
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
DATABASE_URL=postgresql+asyncpg://primcom:Woixzpen5113!@127.0.0.1:5432/primcom_china_cars

API_HOST=127.0.0.1
API_PORT=8010
CORS_ORIGINS=https://primcom.ru,https://www.primcom.ru,https://api.primcom.ru
MEDIA_DIR=/opt/primcom/china_cars_backend/data/media

OPENAI_API_KEY=PASTE_YOUR_OPENAI_KEY_HERE
OPENAI_TRANSLATION_MODEL=gpt-5-nano
OPENAI_NORMALIZE_MODEL=gpt-5-nano

INITIAL_LOAD_LIMIT=30
DAILY_NEW_LIMIT=5
DAILY_DELETE_LIMIT=5
CHE168_MAX_IMAGES=10
EOF
```

---

## 7) Server: init DB schema

```bash
cd /opt/primcom/china_cars_backend
source .venv/bin/activate
python -m app.scripts.init_db
```

---

## 8) Server: test API once

```bash
cd /opt/primcom/china_cars_backend
source .venv/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Open second terminal:
```bash
ssh root@213.232.204.127
curl -s http://127.0.0.1:8010/health
```
You should get `{"status":"ok"}`.
Stop test API with `Ctrl+C` in first terminal.

---

## 9) Server: install systemd services

```bash
sudo cp /opt/primcom/china_cars_backend/deploy/hostvds/primcom-api.service /etc/systemd/system/
sudo cp /opt/primcom/china_cars_backend/deploy/hostvds/primcom-scraper.service /etc/systemd/system/
sudo cp /opt/primcom/china_cars_backend/deploy/hostvds/primcom-scraper.timer /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now primcom-api.service
sudo systemctl enable --now primcom-scraper.timer

sudo systemctl status primcom-api.service --no-pager
sudo systemctl list-timers --all | grep primcom-scraper || true
```

Manual scraper run:
```bash
sudo systemctl start primcom-scraper.service
journalctl -u primcom-scraper.service -n 200 --no-pager
```

---

## 10) Server: Nginx + SSL

```bash
sudo cp /opt/primcom/china_cars_backend/deploy/hostvds/nginx-primcom-api.conf /etc/nginx/sites-available/primcom-api
sudo ln -sf /etc/nginx/sites-available/primcom-api /etc/nginx/sites-enabled/primcom-api
sudo nginx -t
sudo systemctl reload nginx
```

```bash
sudo apt -y install certbot python3-certbot-nginx
sudo certbot --nginx -d api.primcom.ru
```

---

## 11) Final checks

```bash
curl -I https://api.primcom.ru/health
curl -s "https://api.primcom.ru/api/auto-iz-kitaya?limit=1&offset=0&source=guazi"
```

---

## 0) What this deploy sets up
- Backend API (FastAPI) on `127.0.0.1:8010`
- Nginx reverse proxy on `api.primcom.ru`
- PostgreSQL local DB
- Auto scraper every 2 days (`+5 new`, `-5 old`) via systemd timer
- Translation cache update for unknown Chinese names via OpenAI

---

## 1) Connect to server and install packages
```bash
ssh root@YOUR_SERVER_IP
apt update && apt -y upgrade
apt -y install python3.11 python3.11-venv python3-pip postgresql postgresql-contrib nginx git curl
```

## 2) Create app folder
```bash
mkdir -p /opt/primcom
cd /opt/primcom
```

## 3) Upload project files from local machine
Run this on your local Mac terminal (not on server):
```bash
rsync -av --delete \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.DS_Store' \
  "/Users/ivannastugard/Documents/New project/china_cars_backend/" \
  root@YOUR_SERVER_IP:/opt/primcom/china_cars_backend/
```

## 4) Create Python env and install deps (server)
```bash
cd /opt/primcom/china_cars_backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
python -m playwright install chromium
```

## 5) Setup PostgreSQL (server)
```bash
sudo -u postgres psql <<'SQL'
CREATE USER primcom WITH PASSWORD 'CHANGE_ME_STRONG_PASSWORD';
CREATE DATABASE primcom_china_cars OWNER primcom;
GRANT ALL PRIVILEGES ON DATABASE primcom_china_cars TO primcom;
SQL
```

## 6) Create `.env` from template (server)
```bash
cd /opt/primcom/china_cars_backend
cp deploy/hostvds/.env.prod.example .env
nano .env
```
Edit at minimum:
- `POSTGRES_PASSWORD`
- `DATABASE_URL` (same password)
- `OPENAI_API_KEY`
- `CORS_ORIGINS`

## 7) Init DB schema (server)
```bash
cd /opt/primcom/china_cars_backend
source .venv/bin/activate
python -m app.scripts.init_db
```

## 8) Test API directly (server)
```bash
cd /opt/primcom/china_cars_backend
source .venv/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```
In another terminal:
```bash
curl -s http://127.0.0.1:8010/health
```
Stop test API with `Ctrl+C`.

## 9) Install systemd services (server)
Important: if your Linux user is not `ubuntu`, replace `User=`/`Group=` in service files.

```bash
cp /opt/primcom/china_cars_backend/deploy/hostvds/primcom-api.service /etc/systemd/system/
cp /opt/primcom/china_cars_backend/deploy/hostvds/primcom-scraper.service /etc/systemd/system/
cp /opt/primcom/china_cars_backend/deploy/hostvds/primcom-scraper.timer /etc/systemd/system/

systemctl daemon-reload
systemctl enable --now primcom-api.service
systemctl enable --now primcom-scraper.timer

systemctl status primcom-api.service --no-pager
systemctl list-timers --all | grep primcom-scraper || true
```

Manual scraper run test:
```bash
systemctl start primcom-scraper.service
journalctl -u primcom-scraper.service -n 200 --no-pager
```

## 10) Configure Nginx (server)
```bash
cp /opt/primcom/china_cars_backend/deploy/hostvds/nginx-primcom-api.conf /etc/nginx/sites-available/primcom-api
ln -sf /etc/nginx/sites-available/primcom-api /etc/nginx/sites-enabled/primcom-api
nginx -t
systemctl reload nginx
```

## 11) Add SSL certificate (server)
```bash
apt -y install certbot python3-certbot-nginx
certbot --nginx -d api.primcom.ru
```

## 12) Health checks
```bash
curl -I https://api.primcom.ru/health
curl -s "https://api.primcom.ru/api/auto-iz-kitaya?limit=1&offset=0&source=guazi"
```

---

## Logs and troubleshooting
```bash
journalctl -u primcom-api.service -f
journalctl -u primcom-scraper.service -f
systemctl restart primcom-api.service
```

If API returns 500 with DB error:
```bash
systemctl status postgresql --no-pager
ss -lntp | grep 5432 || true
cat /opt/primcom/china_cars_backend/.env | grep DATABASE_URL
```
