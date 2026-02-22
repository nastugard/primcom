from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import text

from app.db import SessionLocal
from app.storage.repository import get_source_id


async def run(source: str, dry_run: bool, preview_limit: int) -> None:
    async with SessionLocal() as session:
        source_id = await get_source_id(session, source)

        rows = (
            await session.execute(
                text(
                    "SELECT l.id, l.source_listing_id "
                    "FROM listings l "
                    "WHERE l.source_id=:sid AND l.status!='deleted' "
                    "AND NOT EXISTS ("
                    "  SELECT 1 FROM listing_images li "
                    "  WHERE li.listing_id=l.id "
                    "    AND li.local_path IS NOT NULL "
                    "    AND BTRIM(li.local_path) <> ''"
                    "    AND LOWER(BTRIM(li.local_path)) ~ '\\.(webp|jpe?g|png)$'"
                    ") "
                    "ORDER BY l.scraped_at DESC"
                ),
                {"sid": source_id},
            )
        ).all()

        print(
            {
                "stage": "empty_image_candidates",
                "source": source,
                "count": len(rows),
                "preview_source_listing_ids": [str(r[1]) for r in rows[: max(0, int(preview_limit))]],
                "dry_run": dry_run,
            },
            flush=True,
        )

        if dry_run or not rows:
            return

        deleted = (
            await session.execute(
                text(
                    "WITH z AS ("
                    "  SELECT l.id "
                    "  FROM listings l "
                    "  WHERE l.source_id=:sid AND l.status!='deleted' "
                    "  AND NOT EXISTS ("
                    "    SELECT 1 FROM listing_images li "
                    "    WHERE li.listing_id=l.id "
                    "      AND li.local_path IS NOT NULL "
                    "      AND BTRIM(li.local_path) <> ''"
                    "      AND LOWER(BTRIM(li.local_path)) ~ '\\.(webp|jpe?g|png)$'"
                    "  )"
                    ") "
                    "DELETE FROM listings l USING z "
                    "WHERE l.id=z.id "
                    "RETURNING l.source_listing_id"
                ),
                {"sid": source_id},
            )
        ).all()

        await session.commit()
        print(
            {
                "stage": "empty_image_deleted",
                "source": source,
                "deleted_count": len(deleted),
                "preview_source_listing_ids": [str(r[0]) for r in deleted[: max(0, int(preview_limit))]],
            },
            flush=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="guazi")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--preview-limit", type=int, default=50)
    args = parser.parse_args()
    asyncio.run(run(source=str(args.source), dry_run=bool(args.dry_run), preview_limit=int(args.preview_limit)))


if __name__ == "__main__":
    main()
