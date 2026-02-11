from __future__ import annotations

import datetime as dt
import pathlib
import uuid

from fastapi import Depends, FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.settings import settings


async def _get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


def _media_url(local_path: str | None) -> str | None:
    if not local_path:
        return None
    if not str(local_path).lower().endswith(".webp"):
        return None
    media_root = pathlib.Path(settings.media_dir)
    media_root_resolved = media_root.resolve()
    try:
        lp = pathlib.Path(local_path)
        if lp.is_absolute():
            rel = lp.resolve().relative_to(media_root_resolved)
        else:
            # local_path часто сохраняется как "data/media/...."
            # а media_root тоже "data/media". В этом случае нужно
            # срезать общий префикс media_root, иначе relative_to падает.
            lp_parts = lp.parts
            mr_parts = media_root.parts
            if len(lp_parts) >= len(mr_parts) and lp_parts[: len(mr_parts)] == mr_parts:
                rel = pathlib.Path(*lp_parts[len(mr_parts) :])
            else:
                rel = lp
        fs_path = (media_root / rel).resolve()
        if not fs_path.exists() or not fs_path.is_file():
            return None
        return f"/media/{rel.as_posix()}"
    except Exception:
        s = str(local_path).replace("\\", "/")
        mr = str(media_root).replace("\\", "/").rstrip("/")
        if s.startswith(mr + "/"):
            rel_s = s[len(mr) + 1 :]
            fs_path = media_root / rel_s
            if not fs_path.exists() or not fs_path.is_file():
                return None
            return "/media/" + rel_s
        return None


class ImageOut(BaseModel):
    position: int
    source_url: str
    url: str | None = None
    width: int | None = None
    height: int | None = None
    checksum: str | None = None


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
    images: list[ImageOut]


class FacetsOut(BaseModel):
    brands: list[str]
    models: list[str]
    models_by_brand: dict[str, list[str]]
    years: list[int]
    mileages: list[int]
    year_min: int | None = None
    year_max: int | None = None
    mileage_min: int | None = None
    mileage_max: int | None = None


def create_app() -> FastAPI:
    app = FastAPI(title="Primcom China Cars API", version="0.1.0")

    app.mount(
        "/media",
        StaticFiles(directory=settings.media_dir, check_dir=False),
        name="media",
    )

    cors_origins = settings.cors_origins_list
    if cors_origins:
        allow_origins = list(cors_origins)
        if "null" not in allow_origins:
            allow_origins.append("null")
    else:
        allow_origins = ["*"]
    allow_credentials = False
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=allow_credentials,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root():
        return {"status": "ok", "docs": "/docs", "catalog": "/api/auto-iz-kitaya"}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/china-cars", response_model=ListingListOut)
    @app.get("/api/auto-iz-kitaya", response_model=ListingListOut)
    async def list_china_cars(
        source: str = Query("all"),
        brand: str | None = Query(default=None),
        model: str | None = Query(default=None),
        year_from: int | None = Query(default=None, ge=1900, le=2100),
        year_to: int | None = Query(default=None, ge=1900, le=2100),
        mileage_from: int | None = Query(default=None, ge=0),
        mileage_to: int | None = Query(default=None, ge=0),
        limit: int = Query(default=24, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        db: AsyncSession = Depends(_get_db),
    ) -> ListingListOut:
        where_parts: list[str] = ["l.status != 'deleted'"]
        params: dict[str, object] = {}

        src = str(source or "guazi").strip().lower()
        if src == "all":
            src = "guazi"
        if src != "guazi":
            return ListingListOut(total=0, limit=limit, offset=offset, last_scraped_at=None, items=[])
        where_parts.append("s.code = :source")
        params["source"] = "guazi"

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

        where_sql = " AND ".join(where_parts)

        last_res = await db.execute(
            text(
                "SELECT MAX(l.scraped_at) AS last_scraped_at "
                "FROM listings l "
                "JOIN listing_sources s ON s.id = l.source_id "
                f"WHERE {where_sql}"
            ),
            params,
        )
        last_scraped_at = last_res.scalar()

        total_res = await db.execute(
            text(
                "SELECT COUNT(*) AS total "
                "FROM listings l "
                "JOIN listing_sources s ON s.id = l.source_id "
                f"WHERE {where_sql}"
            ),
            params,
        )
        total_row = total_res.first()
        total = int((total_row[0] if total_row else 0) or 0)

        items_res = await db.execute(
            text(
                "SELECT "
                "  l.id, s.code AS source, l.source_listing_id, l.brand, l.model, l.year, l.first_registration_date, l.mileage_km, l.price_cny, l.engine_type, l.drive_type, l.engine_volume_l, l.original_url, l.scraped_at, "
                "  (SELECT COUNT(*) FROM listing_images li WHERE li.listing_id = l.id) AS images_count, "
                "  (SELECT li.local_path FROM listing_images li WHERE li.listing_id = l.id ORDER BY li.position ASC LIMIT 1) AS cover_local_path "
                "FROM listings l "
                "JOIN listing_sources s ON s.id = l.source_id "
                f"WHERE {where_sql} "
                "ORDER BY l.scraped_at DESC "
                "LIMIT :limit OFFSET :offset"
            ),
            {**params, "limit": limit, "offset": offset},
        )

        items: list[ListingCardOut] = []
        for r in items_res.all():
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

    @app.get("/api/china-cars/facets", response_model=FacetsOut)
    @app.get("/api/auto-iz-kitaya/facets", response_model=FacetsOut)
    async def list_china_cars_facets(
        source: str = Query("all"),
        db: AsyncSession = Depends(_get_db),
    ) -> FacetsOut:
        where_parts: list[str] = ["l.status != 'deleted'"]
        params: dict[str, object] = {}

        src = str(source or "guazi").strip().lower()
        if src == "all":
            src = "guazi"
        if src != "guazi":
            return FacetsOut(
                brands=[],
                models=[],
                models_by_brand={},
                years=[],
                mileages=[],
                year_min=None,
                year_max=None,
                mileage_min=None,
                mileage_max=None,
            )
        where_parts.append("s.code = :source")
        params["source"] = "guazi"
        where_sql = " AND ".join(where_parts)

        brands_res = await db.execute(
            text(
                "SELECT DISTINCT l.brand "
                "FROM listings l "
                "JOIN listing_sources s ON s.id = l.source_id "
                f"WHERE {where_sql} AND l.brand IS NOT NULL AND btrim(l.brand) <> '' "
                "ORDER BY l.brand ASC"
            ),
            params,
        )
        brands = [str(r[0]) for r in brands_res.all() if r and r[0]]

        models_res = await db.execute(
            text(
                "SELECT DISTINCT l.model "
                "FROM listings l "
                "JOIN listing_sources s ON s.id = l.source_id "
                f"WHERE {where_sql} AND l.model IS NOT NULL AND btrim(l.model) <> '' "
                "ORDER BY l.model ASC"
            ),
            params,
        )
        models = [str(r[0]) for r in models_res.all() if r and r[0]]

        pairs_res = await db.execute(
            text(
                "SELECT DISTINCT l.brand, l.model "
                "FROM listings l "
                "JOIN listing_sources s ON s.id = l.source_id "
                f"WHERE {where_sql} "
                "AND l.brand IS NOT NULL AND btrim(l.brand) <> '' "
                "AND l.model IS NOT NULL AND btrim(l.model) <> '' "
                "ORDER BY l.brand ASC, l.model ASC"
            ),
            params,
        )
        models_by_brand: dict[str, list[str]] = {}
        for b, m in pairs_res.all():
            bs = str(b)
            ms = str(m)
            models_by_brand.setdefault(bs, []).append(ms)

        years_res = await db.execute(
            text(
                "SELECT DISTINCT l.year "
                "FROM listings l "
                "JOIN listing_sources s ON s.id = l.source_id "
                f"WHERE {where_sql} AND l.year IS NOT NULL "
                "ORDER BY l.year ASC"
            ),
            params,
        )
        years = [int(r[0]) for r in years_res.all() if r and r[0] is not None]

        mileage_res = await db.execute(
            text(
                "SELECT DISTINCT l.mileage_km "
                "FROM listings l "
                "JOIN listing_sources s ON s.id = l.source_id "
                f"WHERE {where_sql} AND l.mileage_km IS NOT NULL "
                "ORDER BY l.mileage_km ASC"
            ),
            params,
        )
        mileages = [int(r[0]) for r in mileage_res.all() if r and r[0] is not None]

        return FacetsOut(
            brands=brands,
            models=models,
            models_by_brand=models_by_brand,
            years=years,
            mileages=mileages,
            year_min=years[0] if years else None,
            year_max=years[-1] if years else None,
            mileage_min=mileages[0] if mileages else None,
            mileage_max=mileages[-1] if mileages else None,
        )

    @app.get("/api/china-cars/{listing_id}", response_model=ListingDetailOut)
    @app.get("/api/auto-iz-kitaya/{listing_id}", response_model=ListingDetailOut)
    async def get_china_car(
        listing_id: uuid.UUID = Path(...),
        db: AsyncSession = Depends(_get_db),
    ) -> ListingDetailOut:
        listing_res = await db.execute(
            text(
                "SELECT l.id, s.code AS source, l.source_listing_id, l.brand, l.model, l.year, l.first_registration_date, l.mileage_km, l.price_cny, l.engine_type, l.drive_type, l.engine_volume_l, l.original_url, l.scraped_at "
                "FROM listings l "
                "JOIN listing_sources s ON s.id = l.source_id "
                "WHERE l.id = :id AND l.status != 'deleted'"
            ),
            {"id": str(listing_id)},
        )
        row = listing_res.first()
        if not row:
            raise HTTPException(status_code=404, detail="Listing not found")

        images_res = await db.execute(
            text(
                "SELECT position, source_url, local_path, width, height, checksum "
                "FROM listing_images "
                "WHERE listing_id = :id "
                "ORDER BY position ASC"
            ),
            {"id": str(listing_id)},
        )
        images: list[ImageOut] = []
        for ir in images_res.all():
            url = _media_url(ir[2])
            if not url:
                continue
            images.append(
                ImageOut(
                    position=int(ir[0]),
                    source_url=ir[1],
                    url=url,
                    width=ir[3],
                    height=ir[4],
                    checksum=ir[5],
                )
            )

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
            images=images,
        )

    return app


app = create_app()
