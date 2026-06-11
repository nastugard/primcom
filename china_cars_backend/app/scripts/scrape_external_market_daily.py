from __future__ import annotations

import argparse
import asyncio
import pathlib
from typing import Any

from sqlalchemy import text

from app.core import settings
from app.db import SessionLocal
from app.scrapers.external_market import ExternalMarketBlockedError, ExternalMarketScraper
from app.storage.repository import get_listing_by_source, upsert_image, upsert_listing
from app.utils.media import download_image


_MARKET_TO_SOURCE = {
    "china": "guazi",
    "korea": "korea_manual",
}
_SOURCE_DEFAULTS = {
    "guazi": ("Guazi", "https://www.guazi.com"),
    "korea_manual": ("Korea manual", "manual://korea"),
}


async def _ensure_source(session, code: str) -> int:
    name, base_url = _SOURCE_DEFAULTS.get(code, (code, f"internal://{code}"))
    await session.execute(
        text(
            "INSERT INTO listing_sources (code, name, base_url) "
            "VALUES (:code, :name, :base_url) ON CONFLICT (code) DO NOTHING"
        ),
        {"code": code, "name": name, "base_url": base_url},
    )
    row = (await session.execute(text("SELECT id FROM listing_sources WHERE code=:code"), {"code": code})).first()
    if not row:
        raise RuntimeError(f"Failed to resolve source id for {code}")
    return int(row[0])


def _normalized_for_db(listing) -> dict[str, Any]:
    return {
        "brand": listing.normalized.get("brand"),
        "model": listing.normalized.get("model"),
        "year": listing.normalized.get("year"),
        "first_registration_date": listing.normalized.get("first_registration_date"),
        "mileage_km": listing.normalized.get("mileage_km"),
        "engine_type": listing.normalized.get("engine_type"),
        "engine_volume_l": listing.normalized.get("engine_volume_l"),
        "power_hp": listing.normalized.get("power_hp"),
        "transmission": listing.normalized.get("transmission"),
        "drive_type": listing.normalized.get("drive_type"),
        "price_cny": listing.normalized.get("price_cny"),
        "city": listing.normalized.get("city"),
        "region": listing.normalized.get("region"),
        "vin": listing.normalized.get("vin"),
        "owners_count": listing.normalized.get("owners_count"),
        "eco_standard": listing.normalized.get("eco_standard"),
        "color": listing.normalized.get("color"),
        "trim": listing.normalized.get("trim"),
        "interior_material": listing.normalized.get("interior_material"),
    }


async def _download_listing_images(*, listing, media_root: pathlib.Path, throttle_s: float) -> list[tuple[str, str, str]]:
    kept: list[tuple[str, str, str]] = []
    for pos, img_url in enumerate(listing.image_urls):
        try:
            base = media_root / listing.source_code / listing.source_listing_id / f"{pos:03d}"
            local_path, checksum = await download_image(
                img_url,
                base,
                timeout_s=45.0,
                force_reencode=True,
                min_width=180,
                min_height=120,
            )
            kept.append((img_url, local_path, checksum))
        except Exception as exc:
            print(
                {
                    "stage": "external_market_download_image_failed",
                    "source_listing_id": listing.source_listing_id,
                    "position": pos,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
                flush=True,
            )
        if throttle_s > 0:
            await asyncio.sleep(throttle_s)
    return kept


async def _run_market(*, market: str, target_limit: int, max_pages: int, max_images: int, dry_run: bool, throttle_ms: int) -> dict[str, int]:
    candidate_limit = max(int(target_limit) * 5, int(target_limit), 1)
    scraper = ExternalMarketScraper(
        market=market,
        max_pages=max_pages,
        max_images=max_images,
        throttle_ms=throttle_ms,
    )
    listings = await scraper.scrape(limit=candidate_limit)
    print(
        {
            "stage": "external_market_candidates",
            "market": market,
            "count": len(listings),
            "target": target_limit,
            "sample_ids": [x.source_listing_id for x in listings[:5]],
        },
        flush=True,
    )
    if dry_run:
        return {"candidates": len(listings), "inserted": 0, "skipped": 0, "no_images": 0}

    media_root = pathlib.Path(settings.media_dir)
    throttle_s = max(0, int(throttle_ms)) / 1000.0
    inserted = 0
    skipped = 0
    no_images = 0
    source_code = _MARKET_TO_SOURCE[market]

    async with SessionLocal() as session:
        source_id = await _ensure_source(session, source_code)
        for listing in listings:
            if inserted >= target_limit:
                break
            existing = await get_listing_by_source(session, source_id, listing.source_listing_id)
            if existing:
                skipped += 1
                print(
                    {
                        "stage": "external_market_skip_existing",
                        "market": market,
                        "source_listing_id": listing.source_listing_id,
                    },
                    flush=True,
                )
                continue

            kept = await _download_listing_images(listing=listing, media_root=media_root, throttle_s=throttle_s)
            if not kept:
                no_images += 1
                print(
                    {
                        "stage": "external_market_skip_no_downloaded_images",
                        "market": market,
                        "source_listing_id": listing.source_listing_id,
                    },
                    flush=True,
                )
                continue

            listing_id = await upsert_listing(
                session,
                source_id=source_id,
                source_listing_id=listing.source_listing_id,
                original_url=listing.original_url,
                scraped_at=listing.scraped_at,
                status=listing.status,
                ad_hash=listing.ad_hash,
                content_checksum=listing.content_checksum,
                normalized=_normalized_for_db(listing),
                originals=listing.originals,
                raw_data=listing.raw_data,
            )
            await session.execute(text("DELETE FROM listing_images WHERE listing_id=:listing_id"), {"listing_id": listing_id})
            for pos, (source_url, local_path, checksum) in enumerate(kept):
                await upsert_image(
                    session,
                    listing_id=listing_id,
                    position=pos,
                    source_url=source_url,
                    local_path=local_path,
                    checksum=checksum,
                )
            inserted += 1
            print(
                {
                    "stage": "external_market_upsert_listing",
                    "market": market,
                    "source_listing_id": listing.source_listing_id,
                    "listing_id": str(listing_id),
                    "images": len(kept),
                },
                flush=True,
            )
        await session.commit()

    return {"candidates": len(listings), "inserted": inserted, "skipped": skipped, "no_images": no_images}


async def run(*, china_limit: int, korea_limit: int, max_pages: int, max_images: int, dry_run: bool, throttle_ms: int) -> None:
    print(
        {
            "stage": "external_market_run_start",
            "china_limit": china_limit,
            "korea_limit": korea_limit,
            "max_pages": max_pages,
            "max_images": max_images,
            "dry_run": dry_run,
        },
        flush=True,
    )
    results: dict[str, dict[str, int]] = {}
    try:
        if china_limit > 0:
            results["china"] = await _run_market(
                market="china",
                target_limit=china_limit,
                max_pages=max_pages,
                max_images=max_images,
                dry_run=dry_run,
                throttle_ms=throttle_ms,
            )
        if korea_limit > 0:
            results["korea"] = await _run_market(
                market="korea",
                target_limit=korea_limit,
                max_pages=max_pages,
                max_images=max_images,
                dry_run=dry_run,
                throttle_ms=throttle_ms,
            )
    except ExternalMarketBlockedError as exc:
        print({"stage": "external_market_blocked", "error": str(exc)}, flush=True)
        raise

    print({"stage": "external_market_run_done", "results": results}, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--china-limit", type=int, default=int(settings.external_market_china_daily_limit))
    parser.add_argument("--korea-limit", type=int, default=int(settings.external_market_korea_daily_limit))
    parser.add_argument("--max-pages", type=int, default=int(settings.external_market_max_pages))
    parser.add_argument("--max-images", type=int, default=int(settings.external_market_max_images))
    parser.add_argument("--throttle-ms", type=int, default=int(settings.external_market_throttle_ms))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(
        run(
            china_limit=max(0, int(args.china_limit)),
            korea_limit=max(0, int(args.korea_limit)),
            max_pages=max(1, int(args.max_pages)),
            max_images=max(1, int(args.max_images)),
            dry_run=bool(args.dry_run),
            throttle_ms=max(0, int(args.throttle_ms)),
        )
    )


if __name__ == "__main__":
    main()
