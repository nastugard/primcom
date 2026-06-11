from __future__ import annotations

import argparse
import asyncio
import pathlib

from sqlalchemy import text

from app.core import settings
from app.db import SessionLocal
from app.utils.media import guazi_brand_art_metrics, is_guazi_brand_art_image


def _resolve_local_path(local_path: str) -> pathlib.Path:
    raw = str(local_path or "").strip()
    path = pathlib.Path(raw)
    if path.is_absolute():
        return path

    cwd_path = pathlib.Path.cwd() / path
    if cwd_path.exists():
        return cwd_path

    media_root = pathlib.Path(settings.media_dir).resolve()
    posix = path.as_posix().lstrip("./")
    marker = "data/media/"
    if marker in posix:
        return media_root / posix.split(marker, 1)[1]
    return cwd_path


async def _compact_positions(session, listing_ids: set[str]) -> None:
    for listing_id in sorted(listing_ids):
        rows = (
            await session.execute(
                text(
                    """
                    SELECT id::text
                    FROM listing_images
                    WHERE listing_id = :listing_id
                    ORDER BY position ASC, id ASC
                    """
                ),
                {"listing_id": listing_id},
            )
        ).all()
        for position, row in enumerate(rows):
            await session.execute(
                text("UPDATE listing_images SET position = :position WHERE id = :image_id"),
                {"position": position, "image_id": row[0]},
            )


async def run(*, source: str, dry_run: bool, preview_limit: int, delete_files: bool) -> None:
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT
                        li.id::text AS image_id,
                        li.listing_id::text AS listing_id,
                        l.source_listing_id,
                        li.position,
                        li.local_path
                    FROM listing_images li
                    JOIN listings l ON l.id = li.listing_id
                    JOIN listing_sources s ON s.id = l.source_id
                    WHERE s.code = :source
                      AND l.status != 'deleted'
                      AND li.local_path IS NOT NULL
                      AND BTRIM(li.local_path) <> ''
                    ORDER BY l.source_listing_id, li.position ASC
                    """
                ),
                {"source": source},
            )
        ).all()

        bad: list[dict[str, object]] = []
        top_green: list[dict[str, object]] = []
        scanned_files = 0
        missing_files = 0
        unreadable_files = 0
        for row in rows:
            path = _resolve_local_path(str(row.local_path))
            if not path.exists() or not path.is_file():
                missing_files += 1
                continue
            try:
                data = path.read_bytes()
            except OSError:
                unreadable_files += 1
                continue
            scanned_files += 1
            metrics = guazi_brand_art_metrics(data)
            if metrics.get("valid"):
                top_green.append(
                    {
                        "source_listing_id": row.source_listing_id,
                        "position": row.position,
                        "local_path": str(path),
                        "metrics": metrics,
                    }
                )
            if not is_guazi_brand_art_image(data):
                continue
            bad.append(
                {
                    "image_id": row.image_id,
                    "listing_id": row.listing_id,
                    "source_listing_id": row.source_listing_id,
                    "position": row.position,
                    "local_path": str(path),
                }
            )

        print(
            {
                "stage": "guazi_brand_image_candidates",
                "source": source,
                "db_rows": len(rows),
                "scanned_files": scanned_files,
                "missing_files": missing_files,
                "unreadable_files": unreadable_files,
                "count": len(bad),
                "preview": bad[:preview_limit],
                "top_green_preview": sorted(
                    top_green,
                    key=lambda item: float(item["metrics"].get("score", 0.0)),  # type: ignore[union-attr]
                    reverse=True,
                )[: min(preview_limit, 20)],
                "dry_run": dry_run,
            },
            flush=True,
        )

        if dry_run or not bad:
            return

        affected_listing_ids = {str(item["listing_id"]) for item in bad}
        for item in bad:
            await session.execute(
                text("DELETE FROM listing_images WHERE id = :image_id"),
                {"image_id": item["image_id"]},
            )
            if delete_files:
                try:
                    pathlib.Path(str(item["local_path"])).unlink(missing_ok=True)
                except OSError:
                    pass

        await _compact_positions(session, affected_listing_ids)
        await session.commit()
        print(
            {
                "stage": "guazi_brand_image_cleanup_done",
                "source": source,
                "deleted_images": len(bad),
                "affected_listings": len(affected_listing_ids),
                "delete_files": delete_files,
            },
            flush=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove saved Guazi service/brand images from listing_images.")
    parser.add_argument("--source", default="guazi")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--preview-limit", type=int, default=20)
    parser.add_argument("--delete-files", action="store_true")
    args = parser.parse_args()

    asyncio.run(
        run(
            source=args.source,
            dry_run=bool(args.dry_run),
            preview_limit=int(args.preview_limit),
            delete_files=bool(args.delete_files),
        )
    )


if __name__ == "__main__":
    main()
