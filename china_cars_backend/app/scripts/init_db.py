from __future__ import annotations

import asyncio
import pathlib

import asyncpg

from app.settings import settings


def _to_asyncpg_dsn(sqlalchemy_url: str) -> str:
    if sqlalchemy_url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + sqlalchemy_url[len("postgresql+asyncpg://") :]
    return sqlalchemy_url


async def run() -> None:
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    schema_paths = [repo_root / "schema.sql", repo_root / "schema_v2.sql"]

    dsn = _to_asyncpg_dsn(settings.database_url)

    conn = None
    last_err: Exception | None = None
    for _ in range(30):
        try:
            conn = await asyncpg.connect(dsn)
            last_err = None
            break
        except Exception as e:
            last_err = e
            await asyncio.sleep(1.0)
    if conn is None:
        raise RuntimeError(f"Failed to connect to Postgres after retries: {last_err}")
    try:
        for schema_path in schema_paths:
            if not schema_path.exists():
                continue
            ddl = schema_path.read_text(encoding="utf-8")
            await conn.execute(ddl)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
