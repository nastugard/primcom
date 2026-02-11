from __future__ import annotations

import argparse

from sqlalchemy import text

from app.db import SessionLocal
from app.storage.repository import get_source_id


async def run(source: str, limit: int) -> None:
    async with SessionLocal() as session:
        source_id = await get_source_id(session, source)

        res = await session.execute(
            text(
                "SELECT id, source_listing_id, brand, model, mileage_km, year, original_url "
                "FROM listings WHERE source_id=:sid ORDER BY scraped_at DESC LIMIT :lim"
            ),
            {"sid": source_id, "lim": limit},
        )
        rows = res.all()

        print(f"source={source} rows={len(rows)}")
        for r in rows:
            listing_id = r[0]
            img_res = await session.execute(
                text("SELECT COUNT(*) FROM listing_images WHERE listing_id=:lid"),
                {"lid": listing_id},
            )
            img_count = int(img_res.scalar() or 0)
            print(
                {
                    "listing_id": str(listing_id),
                    "source_listing_id": r[1],
                    "brand": r[2],
                    "model": r[3],
                    "mileage_km": r[4],
                    "year": r[5],
                    "images": img_count,
                    "url": r[6],
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="che168")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    import asyncio

    asyncio.run(run(source=args.source, limit=args.limit))


if __name__ == "__main__":
    main()
