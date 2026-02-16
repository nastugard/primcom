from __future__ import annotations

import datetime as dt
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_source_id(session: AsyncSession, code: str) -> int:
    res = await session.execute(text("SELECT id FROM listing_sources WHERE code=:code"), {"code": code})
    row = res.first()
    if not row:
        raise RuntimeError(f"Unknown source code: {code}")
    return int(row[0])


async def create_scrape_run(session: AsyncSession, *, source: str, started_at: dt.datetime) -> str:
    res = await session.execute(
        text(
            "INSERT INTO scrape_runs(source_code, started_at, status) "
            "VALUES (:source, :started_at, 'running') RETURNING id"
        ),
        {"source": source, "started_at": started_at},
    )
    row = res.first()
    if not row:
        raise RuntimeError("Failed to create scrape run")
    return str(row[0])


async def finalize_scrape_run(
    session: AsyncSession,
    *,
    run_id: str,
    finished_at: dt.datetime,
    status: str,
    fetched: int,
    upserted: int,
    skipped: int,
    errors: list[str],
) -> None:
    await session.execute(
        text(
            "UPDATE scrape_runs SET finished_at=:finished_at, status=:status, fetched=:fetched, "
            "upserted=:upserted, skipped=:skipped, errors_json=(:errors)::jsonb WHERE id=:run_id"
        ),
        {
            "run_id": run_id,
            "finished_at": finished_at,
            "status": status,
            "fetched": fetched,
            "upserted": upserted,
            "skipped": skipped,
            "errors": json.dumps(errors, ensure_ascii=False),
        },
    )


async def insert_raw_listing(
    session: AsyncSession,
    *,
    run_id: str,
    source_id: int,
    source_listing_id: str,
    content_checksum: str | None,
    payload: dict[str, Any],
) -> None:
    await session.execute(
        text(
            "INSERT INTO raw_listings(run_id, source_id, source_listing_id, content_checksum, payload) "
            "VALUES (:run_id, :source_id, :source_listing_id, :content_checksum, (:payload)::jsonb)"
        ),
        {
            "run_id": run_id,
            "source_id": source_id,
            "source_listing_id": source_listing_id,
            "content_checksum": content_checksum,
            "payload": json.dumps(payload, ensure_ascii=False, default=str),
        },
    )


async def get_translation_cache(
    session: AsyncSession,
    *,
    source_text: str,
    lang_from: str,
    lang_to: str,
) -> str | None:
    res = await session.execute(
        text(
            "SELECT normalized_text FROM translation_cache "
            "WHERE source_text=:source_text AND lang_from=:lang_from AND lang_to=:lang_to"
        ),
        {"source_text": source_text, "lang_from": lang_from, "lang_to": lang_to},
    )
    row = res.first()
    return str(row[0]) if row and row[0] else None


async def increment_translation_hits(
    session: AsyncSession,
    *,
    source_text: str,
    lang_from: str,
    lang_to: str,
) -> None:
    await session.execute(
        text(
            "UPDATE translation_cache SET hits = hits + 1, last_used_at=NOW() "
            "WHERE source_text=:source_text AND lang_from=:lang_from AND lang_to=:lang_to"
        ),
        {"source_text": source_text, "lang_from": lang_from, "lang_to": lang_to},
    )


async def upsert_translation_cache(
    session: AsyncSession,
    *,
    source_text: str,
    normalized_text: str,
    lang_from: str,
    lang_to: str,
    provider: str,
    model: str,
    checksum: str,
) -> None:
    await session.execute(
        text(
            "INSERT INTO translation_cache(source_text, normalized_text, lang_from, lang_to, provider, model, checksum) "
            "VALUES (:source_text, :normalized_text, :lang_from, :lang_to, :provider, :model, :checksum) "
            "ON CONFLICT (source_text, lang_from, lang_to) DO UPDATE SET "
            "normalized_text=EXCLUDED.normalized_text, provider=EXCLUDED.provider, model=EXCLUDED.model, checksum=EXCLUDED.checksum, "
            "last_used_at=NOW()"
        ),
        {
            "source_text": source_text,
            "normalized_text": normalized_text,
            "lang_from": lang_from,
            "lang_to": lang_to,
            "provider": provider,
            "model": model,
            "checksum": checksum,
        },
    )


async def list_recent_runs(session: AsyncSession, *, limit: int = 50, source: str | None = None) -> list[dict[str, Any]]:
    if source and source != "all":
        res = await session.execute(
            text(
                "SELECT id, source_code, started_at, finished_at, status, fetched, upserted, skipped, errors_json "
                "FROM scrape_runs WHERE source_code=:source ORDER BY started_at DESC LIMIT :limit"
            ),
            {"source": source, "limit": limit},
        )
    else:
        res = await session.execute(
            text(
                "SELECT id, source_code, started_at, finished_at, status, fetched, upserted, skipped, errors_json "
                "FROM scrape_runs ORDER BY started_at DESC LIMIT :limit"
            ),
            {"limit": limit},
        )
    out = []
    for r in res.all():
        out.append(
            {
                "id": str(r[0]),
                "source": str(r[1]),
                "started_at": r[2],
                "finished_at": r[3],
                "status": str(r[4]),
                "fetched": int(r[5] or 0),
                "upserted": int(r[6] or 0),
                "skipped": int(r[7] or 0),
                "errors": r[8] if isinstance(r[8], list) else [],
            }
        )
    return out
