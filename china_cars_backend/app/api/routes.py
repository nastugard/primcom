from __future__ import annotations

import datetime as dt
import pathlib

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.repositories.catalog import list_recent_runs
from app.core import settings


router = APIRouter()


async def _get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


def _media_url(local_path: str | None) -> str | None:
    if not local_path:
        return None
    if not str(local_path).lower().endswith(".webp"):
        return None
    media_root = pathlib.Path(settings.media_dir).resolve()
    try:
        lp = pathlib.Path(local_path)
        rel = lp.resolve().relative_to(media_root) if lp.is_absolute() else lp
        fs_path = (media_root / rel).resolve()
        if fs_path.exists() and fs_path.is_file():
            return f"/media/{rel.as_posix()}"
    except Exception:
        return None
    return None


class ListingCardOut(BaseModel):
    id: str
    source: str
    source_listing_id: str
    brand: str | None = None
    model: str | None = None
    year: int | None = None
    first_registration_date: dt.date | None = None
    mileage_km: int | None = None
    price_cny: float | None = None
    engine_type: str | None = None
    drive_type: str | None = None
    engine_volume_l: float | None = None
    original_url: str
    scraped_at: dt.datetime
    images_count: int
    cover_image_url: str | None = None


class ListingListOut(BaseModel):
    total: int
    limit: int
    offset: int
    last_scraped_at: dt.datetime | None = None
    items: list[ListingCardOut]


class ListingDetailOut(BaseModel):
    id: str
    source: str
    source_listing_id: str
    brand: str | None = None
    model: str | None = None
    year: int | None = None
    first_registration_date: dt.date | None = None
    mileage_km: int | None = None
    price_cny: float | None = None
    engine_type: str | None = None
    drive_type: str | None = None
    engine_volume_l: float | None = None
    original_url: str
    scraped_at: dt.datetime
    make_id: int | None = None
    model_id: int | None = None
    generation_id: int | None = None
    trim_id: int | None = None
    images: list[str] = []


class FacetsOut(BaseModel):
    brands: list[str]
    models: list[str]
    years: list[int]
    mileages: list[int]


class ScrapeRunOut(BaseModel):
    id: str
    source: str
    started_at: dt.datetime
    finished_at: dt.datetime | None = None
    status: str
    fetched: int
    upserted: int
    skipped: int
    errors: list[str]


class ScrapeRunsOut(BaseModel):
    items: list[ScrapeRunOut]


@router.get("/", tags=["meta"])
async def root():
    return {"status": "ok", "docs": "/docs", "catalog": "/api/auto-iz-kitaya"}


@router.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}


@router.get("/api/china-cars", response_model=ListingListOut, tags=["catalog"])
@router.get("/api/auto-iz-kitaya", response_model=ListingListOut, tags=["catalog"])
async def list_china_cars(
    source: str = Query("all"),
    brand: str | None = Query(default=None),
    model: str | None = Query(default=None),
    year_from: int | None = Query(default=None, ge=1900, le=2100),
    year_to: int | None = Query(default=None, ge=1900, le=2100),
    mileage_from: int | None = Query(default=None, ge=0),
    mileage_to: int | None = Query(default=None, ge=0),
    price_from: float | None = Query(default=None, ge=0),
    price_to: float | None = Query(default=None, ge=0),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(_get_db),
) -> ListingListOut:
    where_parts = ["l.status != 'deleted'"]
    params: dict[str, object] = {}

    src = str(source or "all").strip().lower()
    if src != "all":
        where_parts.append("s.code = :source")
        params["source"] = src

    if brand:
        where_parts.append("l.brand ILIKE :brand")
        params["brand"] = f"%{brand}%"
    if model:
        where_parts.append("l.model ILIKE :model")
        params["model"] = f"%{model}%"
    if year_from is not None:
        where_parts.append("l.year >= :year_from")
        params["year_from"] = year_from
    if year_to is not None:
        where_parts.append("l.year <= :year_to")
        params["year_to"] = year_to
    if mileage_from is not None:
        where_parts.append("l.mileage_km >= :mileage_from")
        params["mileage_from"] = mileage_from
    if mileage_to is not None:
        where_parts.append("l.mileage_km <= :mileage_to")
        params["mileage_to"] = mileage_to
    if price_from is not None:
        where_parts.append("l.price_cny >= :price_from")
        params["price_from"] = price_from
    if price_to is not None:
        where_parts.append("l.price_cny <= :price_to")
        params["price_to"] = price_to

    where_sql = " AND ".join(where_parts)

    run_where = "TRUE"
    run_params: dict[str, object] = {}
    if src != "all":
        run_where = "source_code = :source"
        run_params["source"] = src

    # Backward compatibility: если scrape_runs ещё не создана, не валим весь каталог.
    try:
        last_res = await db.execute(
            text(
                "SELECT finished_at FROM scrape_runs "
                f"WHERE {run_where} AND status IN ('success','partial') "
                "ORDER BY finished_at DESC NULLS LAST LIMIT 1"
            ),
            run_params,
        )
        last_scraped_at = last_res.scalar()
    except Exception:
        last_scraped_at = None

    if last_scraped_at is None:
        try:
            fallback_res = await db.execute(
                text(
                    "SELECT MAX(l.scraped_at) "
                    "FROM listings l "
                    "JOIN listing_sources s ON s.id=l.source_id "
                    f"WHERE {where_sql}"
                ),
                params,
            )
            last_scraped_at = fallback_res.scalar()
        except Exception:
            last_scraped_at = None

    total_res = await db.execute(
        text(
            "SELECT COUNT(*) FROM listings l "
            "JOIN listing_sources s ON s.id=l.source_id "
            f"WHERE {where_sql}"
        ),
        params,
    )
    total = int(total_res.scalar() or 0)

    rows = await db.execute(
        text(
            "SELECT l.id, s.code, l.source_listing_id, l.brand, l.model, l.year, l.first_registration_date, l.mileage_km, "
            "l.price_cny, l.engine_type, l.drive_type, l.engine_volume_l, l.original_url, l.scraped_at, "
            "(SELECT COUNT(*) FROM listing_images li WHERE li.listing_id=l.id), "
            "(SELECT li.local_path FROM listing_images li WHERE li.listing_id=l.id ORDER BY li.position ASC LIMIT 1) "
            "FROM listings l JOIN listing_sources s ON s.id=l.source_id "
            f"WHERE {where_sql} ORDER BY l.scraped_at DESC LIMIT :limit OFFSET :offset"
        ),
        {**params, "limit": limit, "offset": offset},
    )

    items = []
    for r in rows.all():
        items.append(
            ListingCardOut(
                id=str(r[0]),
                source=str(r[1]),
                source_listing_id=str(r[2]),
                brand=r[3],
                model=r[4],
                year=r[5],
                first_registration_date=r[6],
                mileage_km=r[7],
                price_cny=float(r[8]) if r[8] is not None else None,
                engine_type=r[9],
                drive_type=r[10],
                engine_volume_l=float(r[11]) if r[11] is not None else None,
                original_url=r[12],
                scraped_at=r[13],
                images_count=int(r[14] or 0),
                cover_image_url=_media_url(r[15]),
            )
        )

    return ListingListOut(total=total, limit=limit, offset=offset, last_scraped_at=last_scraped_at, items=items)


@router.get("/api/auto-iz-kitaya/facets", response_model=FacetsOut, tags=["catalog"])
async def get_facets(
    source: str = Query("all"),
    db: AsyncSession = Depends(_get_db),
) -> FacetsOut:
    where = "l.status != 'deleted'"
    params: dict[str, object] = {}
    src = str(source or "all").strip().lower()
    if src != "all":
        where += " AND s.code=:source"
        params["source"] = src

    brands = [r[0] for r in (await db.execute(text("SELECT DISTINCT l.brand FROM listings l JOIN listing_sources s ON s.id=l.source_id WHERE " + where + " AND l.brand IS NOT NULL ORDER BY l.brand"), params)).all()]
    models = [r[0] for r in (await db.execute(text("SELECT DISTINCT l.model FROM listings l JOIN listing_sources s ON s.id=l.source_id WHERE " + where + " AND l.model IS NOT NULL ORDER BY l.model"), params)).all()]
    years = [int(r[0]) for r in (await db.execute(text("SELECT DISTINCT l.year FROM listings l JOIN listing_sources s ON s.id=l.source_id WHERE " + where + " AND l.year IS NOT NULL ORDER BY l.year"), params)).all()]
    mileages = [int(r[0]) for r in (await db.execute(text("SELECT DISTINCT l.mileage_km FROM listings l JOIN listing_sources s ON s.id=l.source_id WHERE " + where + " AND l.mileage_km IS NOT NULL ORDER BY l.mileage_km"), params)).all()]

    return FacetsOut(brands=brands, models=models, years=years, mileages=mileages)


@router.get("/api/auto-iz-kitaya/{listing_id}", response_model=ListingDetailOut, tags=["catalog"])
async def get_listing_detail(listing_id: str, db: AsyncSession = Depends(_get_db)) -> ListingDetailOut:
    row = (
        await db.execute(
            text(
                "SELECT l.id, s.code, l.source_listing_id, l.brand, l.model, l.year, l.first_registration_date, l.mileage_km, "
                "l.price_cny, l.engine_type, l.drive_type, l.engine_volume_l, l.original_url, l.scraped_at, "
                "m.make_id, m.model_id, m.generation_id, m.trim_id "
                "FROM listings l "
                "JOIN listing_sources s ON s.id=l.source_id "
                "LEFT JOIN listing_vehicle_map m ON m.listing_id=l.id "
                "WHERE l.id=:id"
            ),
            {"id": listing_id},
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Listing not found")
    images_res = await db.execute(
        text("SELECT local_path FROM listing_images WHERE listing_id=:id ORDER BY position ASC"),
        {"id": listing_id},
    )
    images = []
    for (local_path,) in images_res.all():
        u = _media_url(local_path)
        if u:
            images.append(u)

    return ListingDetailOut(
        id=str(row[0]),
        source=str(row[1]),
        source_listing_id=str(row[2]),
        brand=row[3],
        model=row[4],
        year=row[5],
        first_registration_date=row[6],
        mileage_km=row[7],
        price_cny=float(row[8]) if row[8] is not None else None,
        engine_type=row[9],
        drive_type=row[10],
        engine_volume_l=float(row[11]) if row[11] is not None else None,
        original_url=row[12],
        scraped_at=row[13],
        make_id=row[14],
        model_id=row[15],
        generation_id=row[16],
        trim_id=row[17],
        images=images,
    )


@router.get("/api/scrape-runs", response_model=ScrapeRunsOut, tags=["ops"])
async def get_scrape_runs(
    source: str = Query("all"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(_get_db),
) -> ScrapeRunsOut:
    rows = await list_recent_runs(db, limit=limit, source=source)
    return ScrapeRunsOut(items=[ScrapeRunOut(**x) for x in rows])
