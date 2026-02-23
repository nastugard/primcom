from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import time
import uuid
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.repositories.catalog import list_recent_runs
from app.core import settings
from app.utils.media import save_upload_image_bytes


router = APIRouter()
_lead_ip_hits: dict[str, list[float]] = {}


async def _get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


def _media_url(local_path: str | None) -> str | None:
    if not local_path:
        return None
    raw = str(local_path).strip()
    low = raw.lower()
    if not low.endswith((".webp", ".jpg", ".jpeg", ".png")):
        return None

    # 1) Обычный путь: относительно MEDIA_DIR
    # 2) Fallback: если в БД абсолютный путь с сегментом /data/media/,
    # возвращаем URL даже при несовпавшем MEDIA_DIR.
    media_root = pathlib.Path(settings.media_dir).resolve()
    candidates: list[str] = []
    try:
        lp = pathlib.Path(raw)
        if lp.is_absolute():
            try:
                rel = lp.resolve().relative_to(media_root).as_posix()
                candidates.append(rel)
            except Exception:
                pass
            marker = "/data/media/"
            posix = lp.as_posix()
            if marker in posix:
                candidates.append(posix.split(marker, 1)[1])
        else:
            posix = lp.as_posix().lstrip("./")
            marker = "data/media/"
            if marker in posix:
                candidates.append(posix.split(marker, 1)[1])
            candidates.append(posix)
    except Exception:
        return None

    for rel in candidates:
        r = str(rel or "").strip().lstrip("/")
        if not r or r.startswith(".."):
            continue
        return f"/media/{r}"
    return None


def _market_source_code(market: str) -> str:
    v = str(market or "").strip().lower()
    if v in {"korea", "auto-iz-korei", "korei"}:
        return "korea_manual"
    if v in {"japan", "auto-iz-yaponii", "yaponii"}:
        return "japan_manual"
    return v


async def _ensure_source(db: AsyncSession, *, code: str, name: str, base_url: str) -> int:
    await db.execute(
        text(
            "INSERT INTO listing_sources (code, name, base_url) "
            "VALUES (:code, :name, :base_url) ON CONFLICT (code) DO NOTHING"
        ),
        {"code": code, "name": name, "base_url": base_url},
    )
    row = (
        await db.execute(
            text("SELECT id FROM listing_sources WHERE code = :code"),
            {"code": code},
        )
    ).first()
    if not row:
        raise RuntimeError(f"Failed to resolve source id for {code}")
    return int(row[0])


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    s = str(value).strip().replace(" ", "")
    if not s:
        return None
    try:
        return int(float(s.replace(",", ".")))
    except Exception:
        return None


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    s = str(value).strip().replace(" ", "").replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _require_manager_key(x_manager_api_key: str | None) -> None:
    expected = (settings.manager_api_key or "").strip()
    provided = str(x_manager_api_key or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="MANAGER_API_KEY is not configured")
    if not provided or provided != expected:
        raise HTTPException(status_code=401, detail="Invalid manager API key")


def _parse_listing_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value).strip())
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid listing id format") from exc


def _manual_market_from_source_code(source_code: str) -> Literal["korea", "japan"]:
    code = str(source_code or "").strip().lower()
    if code == "japan_manual":
        return "japan"
    return "korea"


def _lead_client_ip(request: Request) -> str:
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    if request.client and request.client.host:
        return str(request.client.host)
    return "unknown"


def _lead_rate_limit_ok(ip: str) -> bool:
    now = time.time()
    window = 60.0
    limit = max(1, int(settings.lead_rate_limit_per_minute or 20))
    bucket = _lead_ip_hits.setdefault(ip, [])
    cutoff = now - window
    while bucket and bucket[0] < cutoff:
        bucket.pop(0)
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True


def _format_lead_text(data: dict[str, object]) -> str:
    name = str(data.get("name") or "").strip()
    phone = str(data.get("phone") or "").strip()
    comment = str(data.get("comment") or data.get("message") or "").strip()
    page_url = str(data.get("page_url") or "").strip()
    user_agent = str(data.get("user_agent") or "").strip()
    source = str(data.get("source") or "").strip()

    parts = ["НОВАЯ ЗАЯВКА"]
    if source:
        parts.append(f"Источник: {source}")
    if name:
        parts.append(f"Имя: {name}")
    if phone:
        parts.append(f"Телефон: {phone}")
    if comment:
        parts.append(f"Комментарий: {comment}")
    if page_url:
        parts.append(f"Страница: {page_url}")
    if user_agent:
        parts.append(f"UA: {user_agent}")
    return "\n".join(parts)


async def _send_lead_to_telegram(*, bot_token: str, chat_id: str, text_message: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text_message}
    async with httpx.AsyncClient(timeout=12.0) as client:
        res = await client.post(url, json=payload)
    if res.status_code >= 400:
        raise RuntimeError(f"Telegram sendMessage failed: HTTP {res.status_code} {res.text}")


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
    power_hp: int | None = None
    transmission: str | None = None
    trim: str | None = None
    body_type: str | None = None
    auction_grade: str | None = None
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
    power_hp: int | None = None
    transmission: str | None = None
    trim: str | None = None
    body_type: str | None = None
    auction_grade: str | None = None
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


class ManagerCreateOut(BaseModel):
    id: str
    source: str
    source_listing_id: str
    images_count: int


class ManagerDeleteOut(BaseModel):
    ok: bool
    id: str
    source_listing_id: str


class ManagerManualListingOut(BaseModel):
    id: str
    market: Literal["korea", "japan"]
    source: str
    source_listing_id: str
    brand: str | None = None
    model: str | None = None
    year: int | None = None
    mileage_km: int | None = None
    drive_type: str | None = None
    engine_volume_l: float | None = None
    power_hp: int | None = None
    body_type: str | None = None
    trim: str | None = None
    auction_grade: str | None = None
    price: float | None = None
    original_url: str
    scraped_at: dt.datetime
    images_count: int


class ManagerManualListOut(BaseModel):
    items: list[ManagerManualListingOut]


class LeadIn(BaseModel):
    name: str | None = None
    phone: str | None = None
    comment: str | None = None
    message: str | None = None
    source: str | None = None
    page_url: str | None = None
    user_agent: str | None = None
    chat_id: int | str | None = None


class LeadOut(BaseModel):
    ok: bool


@router.get("/", tags=["meta"])
async def root():
    return {"status": "ok", "docs": "/docs", "catalog": "/api/auto-iz-kitaya"}


@router.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}


@router.post("/api/lead", response_model=LeadOut, tags=["lead"])
async def create_lead(
    payload: LeadIn,
    request: Request,
    x_primcom_token: str | None = Header(default=None),
) -> LeadOut:
    expected_token = (settings.lead_api_token or os.getenv("LEAD_API_TOKEN") or "").strip()
    provided_token = str(x_primcom_token or "").strip()
    if expected_token and provided_token != expected_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    ip = _lead_client_ip(request)
    if not _lead_rate_limit_ok(ip):
        raise HTTPException(status_code=429, detail="Too many requests")

    data = payload.model_dump()
    phone = str(data.get("phone") or "").strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Телефон обязателен")

    bot_token = (
        settings.telegram_bot_token
        or os.getenv("TELEGRAM_BOT_TOKEN")
        or os.getenv("BOT_TOKEN")
        or ""
    ).strip()
    group_id = (
        settings.telegram_group_id
        or os.getenv("TELEGRAM_GROUP_ID")
        or os.getenv("GROUP_ID")
        or ""
    ).strip()
    if not bot_token or not group_id:
        raise HTTPException(status_code=503, detail="Lead notifications are not configured")

    text_message = _format_lead_text(data)
    try:
        await _send_lead_to_telegram(
            bot_token=bot_token,
            chat_id=group_id,
            text_message=text_message,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return LeadOut(ok=True)


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
    where_parts = [
        "l.status != 'deleted'",
        "EXISTS (SELECT 1 FROM listing_images li WHERE li.listing_id=l.id AND li.local_path IS NOT NULL AND BTRIM(li.local_path) <> '' AND LOWER(BTRIM(li.local_path)) ~ '\\.(webp|jpe?g|png)$')",
    ]
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
            "l.price_cny, l.engine_type, l.drive_type, l.engine_volume_l, l.power_hp, l.transmission, l.trim, "
            "COALESCE(l.raw_data->>'body_type', NULL), "
            "COALESCE(l.raw_data->>'auction_grade', NULL), "
            "l.original_url, l.scraped_at, "
            "(SELECT COUNT(*) FROM listing_images li WHERE li.listing_id=l.id AND li.local_path IS NOT NULL AND BTRIM(li.local_path) <> '' AND LOWER(BTRIM(li.local_path)) ~ '\\.(webp|jpe?g|png)$'), "
            "(SELECT li.local_path FROM listing_images li WHERE li.listing_id=l.id AND li.local_path IS NOT NULL AND BTRIM(li.local_path) <> '' AND LOWER(BTRIM(li.local_path)) ~ '\\.(webp|jpe?g|png)$' ORDER BY li.position ASC LIMIT 1) "
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
                power_hp=int(r[12]) if r[12] is not None else None,
                transmission=r[13],
                trim=r[14],
                body_type=r[15],
                auction_grade=r[16],
                original_url=r[17],
                scraped_at=r[18],
                images_count=int(r[19] or 0),
                cover_image_url=_media_url(r[20]),
            )
        )

    if last_scraped_at is None and items:
        last_scraped_at = items[0].scraped_at

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
                "l.price_cny, l.engine_type, l.drive_type, l.engine_volume_l, l.power_hp, l.transmission, l.trim, "
                "COALESCE(l.raw_data->>'body_type', NULL), "
                "COALESCE(l.raw_data->>'auction_grade', NULL), "
                "l.original_url, l.scraped_at, "
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
        power_hp=int(row[12]) if row[12] is not None else None,
        transmission=row[13],
        trim=row[14],
        body_type=row[15],
        auction_grade=row[16],
        original_url=row[17],
        scraped_at=row[18],
        make_id=row[19],
        model_id=row[20],
        generation_id=row[21],
        trim_id=row[22],
        images=images,
    )


@router.get("/api/auto-iz-korei", response_model=ListingListOut, tags=["catalog"])
async def list_korea_cars(
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
    return await list_china_cars(
        source="korea_manual",
        brand=brand,
        model=model,
        year_from=year_from,
        year_to=year_to,
        mileage_from=mileage_from,
        mileage_to=mileage_to,
        price_from=price_from,
        price_to=price_to,
        limit=limit,
        offset=offset,
        db=db,
    )


@router.get("/api/auto-iz-yaponii", response_model=ListingListOut, tags=["catalog"])
async def list_japan_cars(
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
    return await list_china_cars(
        source="japan_manual",
        brand=brand,
        model=model,
        year_from=year_from,
        year_to=year_to,
        mileage_from=mileage_from,
        mileage_to=mileage_to,
        price_from=price_from,
        price_to=price_to,
        limit=limit,
        offset=offset,
        db=db,
    )


@router.get("/api/auto-iz-korei/facets", response_model=FacetsOut, tags=["catalog"])
async def get_korea_facets(db: AsyncSession = Depends(_get_db)) -> FacetsOut:
    return await get_facets(source="korea_manual", db=db)


@router.get("/api/auto-iz-yaponii/facets", response_model=FacetsOut, tags=["catalog"])
async def get_japan_facets(db: AsyncSession = Depends(_get_db)) -> FacetsOut:
    return await get_facets(source="japan_manual", db=db)


def _manager_row_to_out(row: tuple[object, ...]) -> ManagerManualListingOut:
    market = _manual_market_from_source_code(str(row[1] or ""))
    return ManagerManualListingOut(
        id=str(row[0]),
        market=market,
        source=str(row[1]),
        source_listing_id=str(row[2]),
        brand=row[3],
        model=row[4],
        year=int(row[5]) if row[5] is not None else None,
        mileage_km=int(row[6]) if row[6] is not None else None,
        drive_type=row[7],
        engine_volume_l=float(row[8]) if row[8] is not None else None,
        power_hp=int(row[9]) if row[9] is not None else None,
        body_type=row[10],
        trim=row[11],
        auction_grade=row[12],
        price=float(row[13]) if row[13] is not None else None,
        original_url=str(row[14] or ""),
        scraped_at=row[15],
        images_count=int(row[16] or 0),
    )


@router.get("/api/manager/manual-listings", response_model=ManagerManualListOut, tags=["manager"])
async def list_manager_manual_listings(
    market: Literal["all", "korea", "japan"] = Query(default="all"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    x_manager_api_key: str | None = Header(default=None),
    db: AsyncSession = Depends(_get_db),
) -> ManagerManualListOut:
    _require_manager_key(x_manager_api_key)

    where = ["s.code IN ('korea_manual','japan_manual')", "l.status!='deleted'"]
    params: dict[str, object] = {"limit": int(limit), "offset": int(offset)}
    if market != "all":
        source_code = "korea_manual" if market == "korea" else "japan_manual"
        where.append("s.code=:source_code")
        params["source_code"] = source_code

    rows = (
        await db.execute(
            text(
                "SELECT l.id, s.code, l.source_listing_id, "
                "l.brand, l.model, l.year, l.mileage_km, l.drive_type, l.engine_volume_l, l.power_hp, "
                "COALESCE(l.raw_data->>'body_type', NULL), l.trim, COALESCE(l.raw_data->>'auction_grade', NULL), "
                "l.price_cny, l.original_url, l.scraped_at, "
                "(SELECT COUNT(*) FROM listing_images li WHERE li.listing_id=l.id) "
                "FROM listings l "
                "JOIN listing_sources s ON s.id=l.source_id "
                f"WHERE {' AND '.join(where)} "
                "ORDER BY l.scraped_at DESC "
                "LIMIT :limit OFFSET :offset"
            ),
            params,
        )
    ).all()
    return ManagerManualListOut(items=[_manager_row_to_out(r) for r in rows])


@router.get("/api/manager/manual-listing/{listing_id}", response_model=ManagerManualListingOut, tags=["manager"])
async def get_manager_manual_listing(
    listing_id: str,
    x_manager_api_key: str | None = Header(default=None),
    db: AsyncSession = Depends(_get_db),
) -> ManagerManualListingOut:
    _require_manager_key(x_manager_api_key)
    listing_uuid = _parse_listing_uuid(listing_id)
    row = (
        await db.execute(
            text(
                "SELECT l.id, s.code, l.source_listing_id, "
                "l.brand, l.model, l.year, l.mileage_km, l.drive_type, l.engine_volume_l, l.power_hp, "
                "COALESCE(l.raw_data->>'body_type', NULL), l.trim, COALESCE(l.raw_data->>'auction_grade', NULL), "
                "l.price_cny, l.original_url, l.scraped_at, "
                "(SELECT COUNT(*) FROM listing_images li WHERE li.listing_id=l.id) "
                "FROM listings l "
                "JOIN listing_sources s ON s.id=l.source_id "
                "WHERE l.id=:id AND s.code IN ('korea_manual','japan_manual') AND l.status!='deleted'"
            ),
            {"id": str(listing_uuid)},
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Manual listing not found")
    return _manager_row_to_out(row)


@router.post("/api/manager/manual-listing", response_model=ManagerCreateOut, tags=["manager"])
async def create_manual_listing(
    market: Literal["korea", "japan"] | None = Form(default=None),
    brand: str = Form(...),
    model: str = Form(...),
    year: str | None = Form(default=None),
    drive_type: str | None = Form(default=None),
    engine_volume_l: str | None = Form(default=None),
    power_hp: str | None = Form(default=None),
    body_type: str | None = Form(default=None),
    transmission: str | None = Form(default=None),
    trim: str | None = Form(default=None),
    price: str | None = Form(default=None),
    original_url: str | None = Form(default=None),
    mileage_km: str | None = Form(default=None),
    engine_type: str | None = Form(default=None),
    auction_grade: str | None = Form(default=None),
    listing_id: str | None = Form(default=None),
    replace_photos: bool = Form(default=True),
    photos: list[UploadFile] = File(default=[]),
    x_manager_api_key: str | None = Header(default=None),
    db: AsyncSession = Depends(_get_db),
) -> ManagerCreateOut:
    _require_manager_key(x_manager_api_key)

    listing_uuid: uuid.UUID | None = None
    existing_source_id: int | None = None
    existing_source_code: str | None = None
    existing_source_listing_id: str | None = None
    existing_original_url: str | None = None
    existing_raw_data_obj: dict[str, object] = {}
    if listing_id:
        listing_uuid = _parse_listing_uuid(listing_id)
        existing_row = (
            await db.execute(
                text(
                    "SELECT l.id, l.source_id, s.code, l.source_listing_id, l.original_url, l.raw_data "
                    "FROM listings l "
                    "JOIN listing_sources s ON s.id=l.source_id "
                    "WHERE l.id=:id AND s.code IN ('korea_manual','japan_manual')"
                ),
                {"id": str(listing_uuid)},
            )
        ).first()
        if not existing_row:
            raise HTTPException(status_code=404, detail="Manual listing for edit not found")
        existing_source_id = int(existing_row[1])
        existing_source_code = str(existing_row[2])
        existing_source_listing_id = str(existing_row[3])
        existing_original_url = str(existing_row[4] or "") or None
        raw_existing = existing_row[5]
        if isinstance(raw_existing, dict):
            existing_raw_data_obj = dict(raw_existing)
        elif isinstance(raw_existing, str):
            try:
                parsed = json.loads(raw_existing)
                if isinstance(parsed, dict):
                    existing_raw_data_obj = parsed
            except Exception:
                existing_raw_data_obj = {}

    resolved_market: Literal["korea", "japan"]
    if listing_uuid:
        resolved_market = _manual_market_from_source_code(str(existing_source_code or ""))
        if market is not None and str(market) != resolved_market:
            raise HTTPException(status_code=400, detail="Market cannot be changed for existing listing")
    else:
        if market is None:
            raise HTTPException(status_code=400, detail="market is required")
        resolved_market = market

    source_code = _market_source_code(resolved_market)
    source_id: int
    source_listing_id: str
    if listing_uuid:
        source_id = int(existing_source_id or 0)
        source_listing_id = str(existing_source_listing_id or "")
    else:
        source_name = "Korea Manual" if source_code == "korea_manual" else "Japan Manual"
        source_id = await _ensure_source(
            db,
            code=source_code,
            name=source_name,
            base_url="https://primcom.ru",
        )
        source_listing_id = f"mgr-{resolved_market}-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"

    now = dt.datetime.now(dt.timezone.utc)
    original_link = str(original_url or "").strip()
    if not original_link:
        if listing_uuid and existing_original_url:
            original_link = existing_original_url
        else:
            original_link = f"https://primcom.ru/pages/auto-iz-{'korei' if resolved_market == 'korea' else 'yaponii'}.html"

    ad_hash = hashlib.sha256(f"{source_code}:{source_listing_id}".encode("utf-8")).hexdigest()
    payload_sig = "|".join(
        [
            str(brand or ""),
            str(model or ""),
            str(year or ""),
            str(price or ""),
            str(engine_type or ""),
            str(engine_volume_l or ""),
            str(power_hp or ""),
            str(drive_type or ""),
            str(body_type or ""),
            str(trim or ""),
            str(transmission or ""),
            str(mileage_km or ""),
            str(auction_grade or ""),
        ]
    )
    content_checksum = hashlib.sha256(payload_sig.encode("utf-8")).hexdigest()

    normalized = {
        "brand": str(brand).strip(),
        "model": str(model).strip(),
        "year": _to_int(year),
        "first_registration_date": None,
        "mileage_km": _to_int(mileage_km),
        "engine_type": str(engine_type).strip() if engine_type else None,
        "engine_volume_l": _to_float(engine_volume_l),
        "power_hp": _to_int(power_hp),
        "transmission": str(transmission).strip() if transmission else None,
        "drive_type": str(drive_type).strip() if drive_type else None,
        "price_cny": _to_float(price),
        "city": None,
        "region": None,
        "vin": None,
        "owners_count": None,
        "eco_standard": None,
        "color": None,
        "trim": str(trim).strip() if str(trim or "").strip() else None,
        "interior_material": None,
    }
    auction_grade_clean = str(auction_grade or "").strip() or None
    if resolved_market != "japan":
        auction_grade_clean = None
    raw_data = {
        **existing_raw_data_obj,
        "manual": True,
        "market": resolved_market,
        "body_type": str(body_type).strip() if body_type else None,
        "auction_grade": auction_grade_clean,
        "price_input": str(price).strip() if price else None,
        "updated_at": now.isoformat(),
    }
    if not listing_uuid:
        raw_data["uploaded_at"] = now.isoformat()
    elif "uploaded_at" not in raw_data:
        raw_data["uploaded_at"] = now.isoformat()
    originals = {
        "title_original": None,
        "description_original": None,
        "equipment_original": None,
        "seller_comments_original": None,
    }

    if listing_uuid:
        row = (
            await db.execute(
                text(
                    "UPDATE listings SET "
                    "source_id=:source_id, original_url=:original_url, scraped_at=:scraped_at, updated_at=NOW(), status='active', "
                    "ad_hash=:ad_hash, content_checksum=:content_checksum, "
                    "brand=:brand, model=:model, year=:year, first_registration_date=:first_registration_date, mileage_km=:mileage_km, "
                    "engine_type=:engine_type, engine_volume_l=:engine_volume_l, power_hp=:power_hp, transmission=:transmission, drive_type=:drive_type, "
                    "price_cny=:price_cny, city=:city, region=:region, vin=:vin, owners_count=:owners_count, eco_standard=:eco_standard, "
                    "color=:color, trim=:trim, interior_material=:interior_material, "
                    "title_original=:title_original, description_original=:description_original, equipment_original=:equipment_original, seller_comments_original=:seller_comments_original, "
                    "raw_data=(:raw_data)::jsonb "
                    "WHERE id=:listing_id "
                    "RETURNING id"
                ),
                {
                    "listing_id": str(listing_uuid),
                    "source_id": source_id,
                    "original_url": original_link,
                    "scraped_at": now,
                    "ad_hash": ad_hash,
                    "content_checksum": content_checksum,
                    "raw_data": json.dumps(raw_data, ensure_ascii=False),
                    **normalized,
                    **originals,
                },
            )
        ).first()
    else:
        row = (
            await db.execute(
                text(
                    "INSERT INTO listings (source_id, source_listing_id, original_url, scraped_at, status, ad_hash, content_checksum, "
                    "brand, model, year, first_registration_date, mileage_km, engine_type, engine_volume_l, power_hp, transmission, drive_type, "
                    "price_cny, city, region, vin, owners_count, eco_standard, color, trim, interior_material, "
                    "title_original, description_original, equipment_original, seller_comments_original, raw_data) "
                    "VALUES (:source_id, :source_listing_id, :original_url, :scraped_at, 'active', :ad_hash, :content_checksum, "
                    ":brand, :model, :year, :first_registration_date, :mileage_km, :engine_type, :engine_volume_l, :power_hp, :transmission, :drive_type, "
                    ":price_cny, :city, :region, :vin, :owners_count, :eco_standard, :color, :trim, :interior_material, "
                    ":title_original, :description_original, :equipment_original, :seller_comments_original, (:raw_data)::jsonb) "
                    "RETURNING id"
                ),
                {
                    "source_id": source_id,
                    "source_listing_id": source_listing_id,
                    "original_url": original_link,
                    "scraped_at": now,
                    "ad_hash": ad_hash,
                    "content_checksum": content_checksum,
                    "raw_data": json.dumps(raw_data, ensure_ascii=False),
                    **normalized,
                    **originals,
                },
            )
        ).first()

    if not row:
        raise HTTPException(status_code=500, detail="Failed to save listing")
    listing_id = row[0]

    if listing_uuid and photos and not bool(replace_photos):
        raise HTTPException(status_code=400, detail="Set replace_photos=1 to upload new photos in edit mode")

    should_replace_images = bool(replace_photos) or not bool(listing_uuid)
    media_root = pathlib.Path(settings.media_dir)
    image_count: int
    if should_replace_images:
        if not photos:
            raise HTTPException(status_code=400, detail="At least one photo is required")
        await db.execute(text("DELETE FROM listing_images WHERE listing_id=:id"), {"id": listing_id})
        inserted = 0
        for idx, photo in enumerate(photos[:20]):
            data = await photo.read()
            if not data:
                continue
            dest = media_root / source_code / source_listing_id / f"{idx:03d}"
            local_path, checksum = await save_upload_image_bytes(data, dest)
            await db.execute(
                text(
                    "INSERT INTO listing_images (listing_id, position, source_url, local_path, checksum) "
                    "VALUES (:listing_id, :position, :source_url, :local_path, :checksum)"
                ),
                {
                    "listing_id": listing_id,
                    "position": inserted,
                    "source_url": f"telegram://{photo.filename or 'photo'}",
                    "local_path": local_path,
                    "checksum": checksum,
                },
            )
            inserted += 1
        if inserted <= 0:
            raise HTTPException(status_code=400, detail="At least one valid photo is required")
        image_count = inserted
    else:
        image_count = int(
            (
                await db.execute(
                    text("SELECT COUNT(*) FROM listing_images WHERE listing_id=:id"),
                    {"id": listing_id},
                )
            ).scalar()
            or 0
        )

    await db.commit()

    return ManagerCreateOut(
        id=str(listing_id),
        source=source_code,
        source_listing_id=source_listing_id,
        images_count=image_count,
    )


@router.delete("/api/manager/manual-listing/{listing_id}", response_model=ManagerDeleteOut, tags=["manager"])
async def delete_manager_manual_listing(
    listing_id: str,
    x_manager_api_key: str | None = Header(default=None),
    db: AsyncSession = Depends(_get_db),
) -> ManagerDeleteOut:
    _require_manager_key(x_manager_api_key)
    listing_uuid = _parse_listing_uuid(listing_id)
    row = (
        await db.execute(
            text(
                "UPDATE listings l SET status='deleted', updated_at=NOW() "
                "FROM listing_sources s "
                "WHERE l.source_id=s.id "
                "  AND l.id=:id "
                "  AND l.status!='deleted' "
                "  AND s.code IN ('korea_manual','japan_manual') "
                "RETURNING l.id, l.source_listing_id"
            ),
            {"id": str(listing_uuid)},
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Manual listing not found")
    await db.commit()
    return ManagerDeleteOut(ok=True, id=str(row[0]), source_listing_id=str(row[1]))


@router.get("/api/scrape-runs", response_model=ScrapeRunsOut, tags=["ops"])
async def get_scrape_runs(
    source: str = Query("all"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(_get_db),
) -> ScrapeRunsOut:
    rows = await list_recent_runs(db, limit=limit, source=source)
    return ScrapeRunsOut(items=[ScrapeRunOut(**x) for x in rows])
