import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from dotenv import load_dotenv


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _allowed_origins() -> list[str] | None:
    raw = (os.getenv("ALLOWED_ORIGINS") or "").strip()
    if not raw:
        return ["*"]
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts or ["*"]


def _origin_allowed(origin: str | None, allowed: list[str]) -> str | None:
    if not origin:
        return "*" if "*" in allowed else None

    if "*" in allowed:
        return origin

    return origin if origin in allowed else None


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict, origin: str | None, allowed_headers: str):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    if origin:
        handler.send_header("Access-Control-Allow-Origin", origin)
        handler.send_header("Vary", "Origin")
    handler.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", allowed_headers)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _format_lead_text(data: dict) -> str:
    name = str(data.get("name") or "").strip()
    phone = str(data.get("phone") or "").strip()
    comment = str(data.get("comment") or data.get("message") or "").strip()
    page_url = str(data.get("page_url") or "").strip()
    user_agent = str(data.get("user_agent") or "").strip()
    source = str(data.get("source") or "").strip()

    parts: list[str] = []
    parts.append("НОВАЯ ЗАЯВКА")
    if source:
        parts.append(f"Источник: {source}")
    if name:
        parts.append(f"Имя: {name}")
    if phone:
        parts.append(f"Телефон: {phone}")
    if comment:
        parts.append(f"Комментарий: {comment}")
    if page_url:
        parts.append(f"Страница: {page_url}")
    if user_agent:
        parts.append(f"UA: {user_agent}")

    return "\n".join(parts)


def _send_telegram_message(bot_token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}, ensure_ascii=False).encode("utf-8")

    req = Request(
        url,
        method="POST",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urlopen(req, timeout=12) as res:
            if getattr(res, "status", 200) >= 400:
                raise RuntimeError(f"Telegram sendMessage failed: HTTP {res.status}")
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        raise RuntimeError(f"Telegram sendMessage failed: HTTP {e.code} {body}") from e
    except URLError as e:
        raise RuntimeError(f"Telegram sendMessage failed: {e}") from e


class LeadHandler(BaseHTTPRequestHandler):
    server_version = "PrimcomLeadAPI/1.0"

    _allowed: list[str] = ["*"]
    _allowed_headers = "Content-Type, X-Primcom-Token"

    _rate_window_s = 60
    _rate_limit = 20
    _ip_hits: dict[str, list[float]] = {}

    def log_message(self, format: str, *args) -> None:
        return

    def _cors_origin(self) -> str | None:
        origin = self.headers.get("Origin")
        return _origin_allowed(origin, self._allowed)

    def _rate_limit_ok(self) -> bool:
        ip = (self.client_address[0] if self.client_address else "") or "unknown"
        now = time.time()
        bucket = self._ip_hits.get(ip)
        if bucket is None:
            bucket = []
            self._ip_hits[ip] = bucket

        cutoff = now - self._rate_window_s
        while bucket and bucket[0] < cutoff:
            bucket.pop(0)

        if len(bucket) >= self._rate_limit:
            return False

        bucket.append(now)
        return True

    def do_OPTIONS(self):
        origin = self._cors_origin()
        self.send_response(204)
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", self._allowed_headers)
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_POST(self):
        if self.path != "/api/lead":
            origin = self._cors_origin()
            _json_response(self, 404, {"ok": False, "error": "Not found"}, origin, self._allowed_headers)
            return

        expected_token = (os.getenv("LEAD_API_TOKEN") or "").strip()
        if expected_token:
            provided_token = (self.headers.get("X-Primcom-Token") or "").strip()
            if provided_token != expected_token:
                origin = self._cors_origin()
                _json_response(self, 401, {"ok": False, "error": "Unauthorized"}, origin, self._allowed_headers)
                return

        if not self._rate_limit_ok():
            origin = self._cors_origin()
            _json_response(self, 429, {"ok": False, "error": "Too many requests"}, origin, self._allowed_headers)
            return

        content_length_raw = self.headers.get("Content-Length") or "0"
        try:
            content_length = int(content_length_raw)
        except ValueError:
            content_length = 0

        if content_length <= 0 or content_length > 32_000:
            origin = self._cors_origin()
            _json_response(self, 400, {"ok": False, "error": "Invalid body"}, origin, self._allowed_headers)
            return

        raw = self.rfile.read(content_length)

        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            origin = self._cors_origin()
            _json_response(self, 400, {"ok": False, "error": "Invalid JSON"}, origin, self._allowed_headers)
            return

        if not isinstance(data, dict):
            origin = self._cors_origin()
            _json_response(self, 400, {"ok": False, "error": "Invalid JSON"}, origin, self._allowed_headers)
            return

        bot_token = (os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
        group_id = (os.getenv("GROUP_ID") or os.getenv("TELEGRAM_GROUP_ID") or "").strip()

        if not bot_token or not group_id:
            origin = self._cors_origin()
            _json_response(self, 500, {"ok": False, "error": "Server is not configured"}, origin, self._allowed_headers)
            return

        text = _format_lead_text(data)

        phone = str(data.get("phone") or "").strip()
        if not phone:
            origin = self._cors_origin()
            _json_response(self, 400, {"ok": False, "error": "Телефон обязателен"}, origin, self._allowed_headers)
            return

        try:
            _send_telegram_message(bot_token, group_id, text)
        except Exception as e:
            origin = self._cors_origin()
            _json_response(self, 502, {"ok": False, "error": str(e)}, origin, self._allowed_headers)
            return

        origin = self._cors_origin()
        _json_response(self, 200, {"ok": True}, origin, self._allowed_headers)


def main() -> None:
    load_dotenv()

    LeadHandler._allowed = _allowed_origins() or ["*"]
    LeadHandler._rate_limit = _env_int("RATE_LIMIT_PER_MINUTE", 20)

    host = (os.getenv("LEAD_API_HOST") or "0.0.0.0").strip()
    port = _env_int("LEAD_API_PORT", 8080)

    httpd = ThreadingHTTPServer((host, port), LeadHandler)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
