import asyncio
import contextlib
import logging
import os
import shlex
from dataclasses import dataclass
from datetime import datetime, timezone

import aiohttp
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

try:
    from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation
except ImportError:  # pragma: no cover - compatibility fallback
    from aiogram.fsm.storage.memory import MemoryStorage

    SimpleEventIsolation = None


@dataclass
class MonitorConfig:
    token: str
    alert_chat_id: str
    allowed_ids: set[int]
    target_host: str
    target_user: str
    target_port: int
    ssh_identity_file: str | None
    ssh_connect_timeout_seconds: int
    monitor_containers: list[str]
    check_interval_seconds: int
    send_recovery_alert: bool
    public_healthcheck_url: str | None
    http_timeout_seconds: int


@dataclass
class ContainerStatus:
    name: str
    status: str
    restart_count: int | None
    started_at: str | None
    finished_at: str | None

    @property
    def is_running(self) -> bool:
        return self.status == "running"


@dataclass
class HealthSnapshot:
    checked_at: datetime
    ssh_ok: bool
    target: str
    containers: list[ContainerStatus]
    public_health_ok: bool | None
    public_health_status: int | None
    public_health_error: str | None
    error: str | None

    @property
    def is_healthy(self) -> bool:
        if not self.ssh_ok or self.error:
            return False
        if any(not item.is_running for item in self.containers):
            return False
        if self.public_health_ok is False:
            return False
        return True

    @property
    def problem_signature(self) -> str:
        if self.ssh_ok is False:
            return f"ssh:{self.error or 'unknown'}"
        problems = [f"{item.name}:{item.status}" for item in self.containers if not item.is_running]
        if self.public_health_ok is False:
            problems.append(f"public_health:{self.public_health_status or self.public_health_error or 'failed'}")
        return ";".join(problems)


router = Router()
CONFIG: MonitorConfig | None = None
LAST_PROBLEM_SIGNATURE: str | None = None
LAST_SNAPSHOT: HealthSnapshot | None = None


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "y", "on"}


def _split_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def load_config() -> MonitorConfig:
    load_dotenv()

    token = (os.getenv("MONITOR_BOT_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("MONITOR_BOT_TOKEN is not set")

    alert_chat_id = (os.getenv("MONITOR_ALERT_CHAT_ID") or "").strip()
    if not alert_chat_id:
        raise RuntimeError("MONITOR_ALERT_CHAT_ID is not set")

    target_host = (os.getenv("TARGET_HOST") or "").strip()
    if not target_host:
        raise RuntimeError("TARGET_HOST is not set")

    allowed_ids: set[int] = set()
    for part in _split_csv(os.getenv("MONITOR_ALLOWED_IDS")):
        try:
            allowed_ids.add(int(part))
        except ValueError:
            logging.warning("Skip invalid MONITOR_ALLOWED_IDS value: %s", part)

    monitor_containers = _split_csv(os.getenv("MONITOR_CONTAINERS")) or ["primcom-bot", "primcom-lead-api"]

    ssh_identity_file = (os.getenv("SSH_IDENTITY_FILE") or "").strip() or None
    public_healthcheck_url = (os.getenv("PUBLIC_HEALTHCHECK_URL") or "").strip() or None

    return MonitorConfig(
        token=token,
        alert_chat_id=alert_chat_id,
        allowed_ids=allowed_ids,
        target_host=target_host,
        target_user=(os.getenv("TARGET_USER") or "root").strip(),
        target_port=_env_int("TARGET_PORT", 22),
        ssh_identity_file=ssh_identity_file,
        ssh_connect_timeout_seconds=_env_int("SSH_CONNECT_TIMEOUT_SECONDS", 10),
        monitor_containers=monitor_containers,
        check_interval_seconds=max(15, _env_int("CHECK_INTERVAL_SECONDS", 60)),
        send_recovery_alert=_env_bool("SEND_RECOVERY_ALERT", False),
        public_healthcheck_url=public_healthcheck_url,
        http_timeout_seconds=max(3, _env_int("HTTP_TIMEOUT_SECONDS", 10)),
    )


def _allowed(message: Message) -> bool:
    global CONFIG
    if CONFIG is None or not CONFIG.allowed_ids:
        return True
    user_id = message.from_user.id if message.from_user else 0
    return user_id in CONFIG.allowed_ids


async def _deny_if_needed(message: Message) -> bool:
    if _allowed(message):
        return False
    await message.answer("Доступ запрещен.")
    return True


def _build_ssh_command(config: MonitorConfig, remote_script: str) -> list[str]:
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={config.ssh_connect_timeout_seconds}",
        "-p",
        str(config.target_port),
    ]
    if config.ssh_identity_file:
        cmd.extend(["-i", config.ssh_identity_file])
    cmd.append(f"{config.target_user}@{config.target_host}")
    cmd.append(remote_script)
    return cmd


async def _run_ssh(config: MonitorConfig, remote_script: str) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *_build_ssh_command(config, remote_script),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")


async def _fetch_public_health(config: MonitorConfig) -> tuple[bool | None, int | None, str | None]:
    if not config.public_healthcheck_url:
        return None, None, None
    timeout = aiohttp.ClientTimeout(total=config.http_timeout_seconds)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(config.public_healthcheck_url) as resp:
                await resp.text()
                return 200 <= resp.status < 300, resp.status, None
    except Exception as exc:
        return False, None, f"{exc.__class__.__name__}: {exc}"


def _container_probe_script(container_names: list[str]) -> str:
    lines = ["set -u"]
    for name in container_names:
        quoted_name = shlex.quote(name)
        lines.append(
            f"printf '%s\\t' {quoted_name}; "
            f"docker inspect -f '{{{{.State.Status}}}}|{{{{.RestartCount}}}}|{{{{.State.StartedAt}}}}|{{{{.State.FinishedAt}}}}' {quoted_name} 2>/dev/null || echo 'missing||||'"
        )
    return "\n".join(lines)


def _parse_container_output(stdout: str) -> list[ContainerStatus]:
    result: list[ContainerStatus] = []
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line or "\t" not in line:
            continue
        name, payload = line.split("\t", 1)
        parts = payload.split("|")
        while len(parts) < 4:
            parts.append("")
        restart_count: int | None = None
        if parts[1].strip():
            try:
                restart_count = int(parts[1].strip())
            except ValueError:
                restart_count = None
        result.append(
            ContainerStatus(
                name=name.strip(),
                status=parts[0].strip() or "unknown",
                restart_count=restart_count,
                started_at=parts[2].strip() or None,
                finished_at=parts[3].strip() or None,
            )
        )
    return result


async def collect_snapshot(config: MonitorConfig) -> HealthSnapshot:
    checked_at = datetime.now(timezone.utc)
    public_ok, public_status, public_error = await _fetch_public_health(config)
    target = f"{config.target_user}@{config.target_host}:{config.target_port}"

    returncode, stdout, stderr = await _run_ssh(config, _container_probe_script(config.monitor_containers))
    if returncode != 0:
        return HealthSnapshot(
            checked_at=checked_at,
            ssh_ok=False,
            target=target,
            containers=[],
            public_health_ok=public_ok,
            public_health_status=public_status,
            public_health_error=public_error,
            error=(stderr.strip() or stdout.strip() or f"ssh exit code {returncode}")[:1000],
        )

    containers = _parse_container_output(stdout)
    if not containers:
        return HealthSnapshot(
            checked_at=checked_at,
            ssh_ok=False,
            target=target,
            containers=[],
            public_health_ok=public_ok,
            public_health_status=public_status,
            public_health_error=public_error,
            error="ssh succeeded but no container data returned",
        )

    return HealthSnapshot(
        checked_at=checked_at,
        ssh_ok=True,
        target=target,
        containers=containers,
        public_health_ok=public_ok,
        public_health_status=public_status,
        public_health_error=public_error,
        error=None,
    )


def _format_dt_iso(raw: str | None) -> str:
    if not raw:
        return "—"
    return raw.replace("T", " ").replace("Z", " UTC")


def format_snapshot(snapshot: HealthSnapshot) -> str:
    lines = [
        "Статус мониторинга Primcom",
        f"Проверено: {snapshot.checked_at.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"Цель: {snapshot.target}",
        f"SSH: {'OK' if snapshot.ssh_ok else 'ERROR'}",
    ]
    if snapshot.error:
        lines.append(f"Ошибка: {snapshot.error}")

    if snapshot.containers:
        lines.append("")
        lines.append("Контейнеры:")
        for item in snapshot.containers:
            lines.append(
                f"- {item.name}: {item.status}, restart_count={item.restart_count if item.restart_count is not None else '—'}, started={_format_dt_iso(item.started_at)}"
            )

    if snapshot.public_health_ok is not None:
        lines.append("")
        if snapshot.public_health_ok:
            lines.append(f"Public health: OK ({snapshot.public_health_status})")
        else:
            detail = snapshot.public_health_error or str(snapshot.public_health_status or "error")
            lines.append(f"Public health: ERROR ({detail})")

    lines.append("")
    lines.append(f"Итог: {'OK' if snapshot.is_healthy else 'ALERT'}")
    return "\n".join(lines)


async def send_alert(bot: Bot, text: str) -> None:
    global CONFIG
    if CONFIG is None:
        return
    await bot.send_message(chat_id=CONFIG.alert_chat_id, text=text)


async def monitor_loop(bot: Bot) -> None:
    global CONFIG, LAST_PROBLEM_SIGNATURE, LAST_SNAPSHOT
    if CONFIG is None:
        raise RuntimeError("CONFIG is not initialized")

    while True:
        try:
            snapshot = await collect_snapshot(CONFIG)
            LAST_SNAPSHOT = snapshot
            signature = snapshot.problem_signature if not snapshot.is_healthy else None

            if signature and signature != LAST_PROBLEM_SIGNATURE:
                await send_alert(bot, "ALERT: primcom monitor detected a problem.\n\n" + format_snapshot(snapshot))
            elif signature is None and LAST_PROBLEM_SIGNATURE and CONFIG.send_recovery_alert:
                await send_alert(bot, "RECOVERY: monitored services are healthy again.\n\n" + format_snapshot(snapshot))

            LAST_PROBLEM_SIGNATURE = signature
        except Exception:
            logging.exception("monitor loop iteration failed")
        await asyncio.sleep(CONFIG.check_interval_seconds)


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    if await _deny_if_needed(message):
        return
    await message.answer("Команды: /status, /check")


@router.message(Command("status"))
@router.message(Command("check"))
async def on_status(message: Message) -> None:
    global CONFIG, LAST_SNAPSHOT
    if await _deny_if_needed(message):
        return
    if CONFIG is None:
        await message.answer("CONFIG is not initialized")
        return

    snapshot = await collect_snapshot(CONFIG)
    LAST_SNAPSHOT = snapshot
    await message.answer(format_snapshot(snapshot))


async def main() -> None:
    global CONFIG
    CONFIG = load_config()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    bot = Bot(token=CONFIG.token)
    dispatcher_kwargs = {"storage": MemoryStorage()}
    if SimpleEventIsolation is not None:
        dispatcher_kwargs["events_isolation"] = SimpleEventIsolation()
    dp = Dispatcher(**dispatcher_kwargs)
    dp.include_router(router)

    monitor_task = asyncio.create_task(monitor_loop(bot))
    logging.info("primcom-monitor-bot started")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        monitor_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await monitor_task


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
