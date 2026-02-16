from __future__ import annotations

import asyncio
import datetime as dt

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import settings
from app.repositories.catalog import create_scrape_run, finalize_scrape_run, get_source_id, insert_raw_listing
from app.scrapers.base import ScrapedListing
from app.services.canonical import upsert_canonical_vehicle
from app.services.translation import translate_term
from app.sources.factory import create_adapter
from app.storage.repository import get_listing_by_source, upsert_image, upsert_listing
from app.utils.media import download_image


async def _download_images(
    session: AsyncSession,
    *,
    listing_id,
    listing: ScrapedListing,
    throttle_ms: int,
) -> None:
    if not listing.image_urls:
        return
    for pos, source_url in enumerate(listing.image_urls):
        local_path = None
        checksum = None
        try:
            base = f"{settings.media_dir}/{listing.source_code}/{listing.source_listing_id}/{pos:03d}"
            local_path, checksum = await download_image(source_url, base)
        except Exception:
            local_path, checksum = None, None
        await upsert_image(
            session,
            listing_id=listing_id,
            position=pos,
            source_url=source_url,
            local_path=local_path,
            checksum=checksum,
        )
        if throttle_ms > 0:
            await asyncio.sleep(max(0, int(throttle_ms)) / 1000.0)


async def run_ingestion(
    session: AsyncSession,
    *,
    sources: list[str],
    limit: int,
    max_images: int,
    skip_existing: bool,
    throttle_ms: int,
    download_images: bool,
) -> dict[str, dict]:
    client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
    result: dict[str, dict] = {}

    for source in sources:
        started_at = dt.datetime.now(dt.timezone.utc)
        run_id = await create_scrape_run(session, source=source, started_at=started_at)
        fetched = upserted = skipped = 0
        errors: list[str] = []
        status = "success"
        try:
            adapter = create_adapter(source, max_images=max_images)
            source_id = await get_source_id(session, source)
            listings = await adapter.scrape(limit=limit)
            fetched = len(listings)

            for listing in listings:
                try:
                    if adapter.detect_placeholder(listing):
                        skipped += 1
                        continue

                    if skip_existing:
                        existing = await get_listing_by_source(session, source_id, listing.source_listing_id)
                        if existing:
                            skipped += 1
                            continue

                    # translate only unknown/new chinese terms
                    listing.normalized["brand"] = await translate_term(session, client, listing.normalized.get("brand"))
                    listing.normalized["model"] = await translate_term(session, client, listing.normalized.get("model"))
                    if listing.normalized.get("trim"):
                        listing.normalized["trim"] = await translate_term(session, client, listing.normalized.get("trim"))

                    listing_id = await upsert_listing(
                        session,
                        source_id=source_id,
                        source_listing_id=listing.source_listing_id,
                        original_url=listing.original_url,
                        scraped_at=listing.scraped_at,
                        status=listing.status,
                        ad_hash=listing.ad_hash,
                        content_checksum=listing.content_checksum,
                        normalized=listing.normalized,
                        originals=listing.originals,
                        raw_data=listing.raw_data,
                    )
                    await insert_raw_listing(
                        session,
                        run_id=run_id,
                        source_id=source_id,
                        source_listing_id=listing.source_listing_id,
                        content_checksum=listing.content_checksum,
                        payload=listing.raw_data,
                    )
                    await upsert_canonical_vehicle(
                        session,
                        listing_id=str(listing_id),
                        brand=listing.normalized.get("brand"),
                        model=listing.normalized.get("model"),
                        generation=listing.normalized.get("generation"),
                        trim=listing.normalized.get("trim"),
                    )
                    if download_images:
                        await _download_images(
                            session,
                            listing_id=listing_id,
                            listing=listing,
                            throttle_ms=throttle_ms,
                        )
                    upserted += 1
                except Exception as e:
                    errors.append(f"{listing.source_listing_id}: {e}")
                    continue

            if errors and upserted > 0:
                status = "partial"
            elif errors and upserted == 0:
                status = "failed"

        except Exception as e:
            status = "failed"
            errors.append(str(e))

        finally:
            await finalize_scrape_run(
                session,
                run_id=run_id,
                finished_at=dt.datetime.now(dt.timezone.utc),
                status=status,
                fetched=fetched,
                upserted=upserted,
                skipped=skipped,
                errors=errors,
            )
            await session.commit()
            result[source] = {
                "run_id": run_id,
                "status": status,
                "fetched": fetched,
                "upserted": upserted,
                "skipped": skipped,
                "errors": errors,
            }

    return result
