from __future__ import annotations

import datetime as dt
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_source_id(session: AsyncSession, code: str) -> int:
    res = await session.execute(text("SELECT id FROM listing_sources WHERE code = :code"), {"code": code})
    row = res.first()
    if not row:
        raise RuntimeError(f"Unknown source code: {code}")
    return int(row[0])


async def get_listing_by_source(session: AsyncSession, source_id: int, source_listing_id: str):
    res = await session.execute(
        text(
            "SELECT id, price_cny FROM listings WHERE source_id = :sid AND source_listing_id = :slid"
        ),
        {"sid": source_id, "slid": source_listing_id},
    )
    row = res.first()
    if not row:
        return None
    return {"id": row[0], "price_cny": row[1]}


async def insert_price_history(session: AsyncSession, listing_id, price_cny: float) -> None:
    await session.execute(
        text(
            "INSERT INTO listing_price_history (listing_id, price_cny) VALUES (:lid, :price)"
        ),
        {"lid": listing_id, "price": price_cny},
    )


async def upsert_listing(
    session: AsyncSession,
    *,
    source_id: int,
    source_listing_id: str,
    original_url: str,
    scraped_at: dt.datetime,
    status: str,
    ad_hash: str,
    content_checksum: str | None,
    normalized: dict[str, Any],
    originals: dict[str, Any],
    raw_data: dict[str, Any],
):
    existing = await get_listing_by_source(session, source_id, source_listing_id)

    payload: dict[str, Any] = {}
    payload.update(normalized)
    payload.update(originals)

    def p(key: str) -> Any:
        return payload.get(key)

    raw_json = json.dumps(raw_data, ensure_ascii=False, default=str)

    if existing:
        await session.execute(
            text(
                "UPDATE listings SET original_url=:original_url, scraped_at=:scraped_at, updated_at=NOW(), status=:status, ad_hash=:ad_hash, content_checksum=:content_checksum, "
                "brand=:brand, model=:model, year=:year, first_registration_date=:first_registration_date, mileage_km=:mileage_km, engine_type=:engine_type, engine_volume_l=:engine_volume_l, "
                "power_hp=:power_hp, transmission=:transmission, drive_type=:drive_type, price_cny=:price_cny, city=:city, region=:region, vin=:vin, owners_count=:owners_count, eco_standard=:eco_standard, "
                "color=:color, trim=:trim, interior_material=:interior_material, "
                "title_original=:title_original, description_original=:description_original, equipment_original=:equipment_original, seller_comments_original=:seller_comments_original, raw_data=(:raw_data)::jsonb "
                "WHERE id=:id"
            ),
            {
                "id": existing["id"],
                "original_url": original_url,
                "scraped_at": scraped_at,
                "status": status,
                "ad_hash": ad_hash,
                "content_checksum": content_checksum,
                "raw_data": raw_json,
                "brand": p("brand"),
                "model": p("model"),
                "year": p("year"),
                "first_registration_date": p("first_registration_date"),
                "mileage_km": p("mileage_km"),
                "engine_type": p("engine_type"),
                "engine_volume_l": p("engine_volume_l"),
                "power_hp": p("power_hp"),
                "transmission": p("transmission"),
                "drive_type": p("drive_type"),
                "price_cny": p("price_cny"),
                "city": p("city"),
                "region": p("region"),
                "vin": p("vin"),
                "owners_count": p("owners_count"),
                "eco_standard": p("eco_standard"),
                "color": p("color"),
                "trim": p("trim"),
                "interior_material": p("interior_material"),
                "title_original": p("title_original"),
                "description_original": p("description_original"),
                "equipment_original": p("equipment_original"),
                "seller_comments_original": p("seller_comments_original"),
            },
        )

        new_price = payload.get("price_cny")
        old_price = existing.get("price_cny")
        if new_price is not None and (old_price is None or float(old_price) != float(new_price)):
            await insert_price_history(session, existing["id"], float(new_price))
        return existing["id"]

    res = await session.execute(
        text(
            "INSERT INTO listings (source_id, source_listing_id, original_url, scraped_at, status, ad_hash, content_checksum, "
            "brand, model, year, first_registration_date, mileage_km, engine_type, engine_volume_l, power_hp, transmission, drive_type, price_cny, city, region, vin, owners_count, eco_standard, "
            "color, trim, interior_material, "
            "title_original, description_original, equipment_original, seller_comments_original, raw_data) "
            "VALUES (:source_id, :source_listing_id, :original_url, :scraped_at, :status, :ad_hash, :content_checksum, "
            ":brand, :model, :year, :first_registration_date, :mileage_km, :engine_type, :engine_volume_l, :power_hp, :transmission, :drive_type, :price_cny, :city, :region, :vin, :owners_count, :eco_standard, "
            ":color, :trim, :interior_material, "
            ":title_original, :description_original, :equipment_original, :seller_comments_original, (:raw_data)::jsonb) "
            "RETURNING id"
        ),
        {
            "source_id": source_id,
            "source_listing_id": source_listing_id,
            "original_url": original_url,
            "scraped_at": scraped_at,
            "status": status,
            "ad_hash": ad_hash,
            "content_checksum": content_checksum,
            "raw_data": raw_json,
            "brand": p("brand"),
            "model": p("model"),
            "year": p("year"),
            "first_registration_date": p("first_registration_date"),
            "mileage_km": p("mileage_km"),
            "engine_type": p("engine_type"),
            "engine_volume_l": p("engine_volume_l"),
            "power_hp": p("power_hp"),
            "transmission": p("transmission"),
            "drive_type": p("drive_type"),
            "price_cny": p("price_cny"),
            "city": p("city"),
            "region": p("region"),
            "vin": p("vin"),
            "owners_count": p("owners_count"),
            "eco_standard": p("eco_standard"),
            "color": p("color"),
            "trim": p("trim"),
            "interior_material": p("interior_material"),
            "title_original": p("title_original"),
            "description_original": p("description_original"),
            "equipment_original": p("equipment_original"),
            "seller_comments_original": p("seller_comments_original"),
        },
    )
    row = res.first()
    if not row:
        raise RuntimeError("Failed to insert listing")
    listing_id = row[0]

    new_price = payload.get("price_cny")
    if new_price is not None:
        await insert_price_history(session, listing_id, float(new_price))

    return listing_id


async def upsert_image(
    session: AsyncSession,
    *,
    listing_id,
    position: int,
    source_url: str,
    local_path: str | None,
    checksum: str | None,
):
    await session.execute(
        text(
            "INSERT INTO listing_images (listing_id, position, source_url, local_path, checksum) "
            "VALUES (:lid, :pos, :surl, :lpath, :chk) "
            "ON CONFLICT (listing_id, position) DO UPDATE SET source_url=EXCLUDED.source_url, local_path=EXCLUDED.local_path, checksum=EXCLUDED.checksum"
        ),
        {"lid": listing_id, "pos": position, "surl": source_url, "lpath": local_path, "chk": checksum},
    )
