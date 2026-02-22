from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import pathlib
import re
import shutil
import json

import httpx
from sqlalchemy import text

from openai import AsyncOpenAI

from app.db import SessionLocal
from app.scrapers.base import BaseScraper
from app.scrapers.che168 import Che168Scraper
from app.scrapers.dongchedi import DongchediScraper
from app.scrapers.guazi import GuaziScraper
from app.settings import settings
from app.storage.repository import get_listing_by_source, get_source_id, upsert_image, upsert_listing
from app.utils.media import download_image
from app.utils.name_translation import (
    BRAND_MAP,
    MODEL_MAP,
    has_chinese,
    load_cache,
    normalize_by_dict,
    save_cache,
)


_RE_HAS_ZH = re.compile(r"[\u4e00-\u9fff]")
_RE_HAS_LATIN = re.compile(r"[A-Za-z]")
_TRANSLATABLE_TEXT_FIELDS = (
    "trim",
    "color",
    "city",
    "engine_type",
    "drive_type",
    "transmission",
    "eco_standard",
    "interior_material",
)
_TRANSLATE_PROXY_RETRIES = 3
_TRANSLATE_PROXY_BATCH_CHUNK_SIZE = 20


def _safe_move_dir(src: pathlib.Path, dst: pathlib.Path) -> bool:
    try:
        if not src.exists() or not src.is_dir():
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return True
    except Exception:
        return False


def _as_str(v):
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return None
    s = str(v).strip()
    return s or None


def _as_int(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    s = str(v)
    m = re.search(r"\d+", s)
    if not m:
        return None
    try:
        return int(m.group(0))
    except Exception:
        return None


def _as_float(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return float(int(v))
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", ".")
    m = re.search(r"\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


def _enforce_engine_consistency(normalized: dict) -> None:
    """
    Бизнес-правило:
    если указан объём двигателя (ДВС), тип не может быть "Электро".
    """
    vol = _as_float(normalized.get("engine_volume_l"))
    et = _as_str(normalized.get("engine_type"))
    if vol is None or vol <= 0:
        if et is not None:
            normalized["engine_type"] = et
        return

    normalized["engine_volume_l"] = vol
    if et is None:
        normalized["engine_type"] = "Бензин/Дизель"
        return

    et_low = et.lower()
    if et_low in {"электро", "electric", "ev", "bev"}:
        normalized["engine_type"] = "Бензин/Дизель"
    else:
        normalized["engine_type"] = et


def _safe_remove_dir(path: pathlib.Path) -> bool:
    try:
        if not path.exists() or not path.is_dir():
            return False
        shutil.rmtree(path)
        return True
    except Exception:
        return False


async def _translate_to_english(client: AsyncOpenAI, text_value: str) -> str:
    resp = await client.chat.completions.create(
        model=settings.openai_translation_model,
        messages=[
            {
                "role": "system",
                "content": "Translate the given car brand or model name into English. Output only the translation without quotes.",
            },
            {"role": "user", "content": text_value},
        ],
    )
    out = ((resp.choices[0].message.content or "").strip() if resp.choices else "").strip()
    return out.strip('"\'').strip()


def _proxy_headers(token: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def _translate_proxy_single(text_value: str) -> str:
    url = str(settings.translation_proxy_url or "").strip()
    if not url:
        raise RuntimeError("translation proxy url is not configured")
    payload = {"text": text_value}
    base_timeout = max(1000, int(settings.translation_proxy_timeout_ms)) / 1000.0
    last_error: Exception | None = None

    for attempt in range(1, _TRANSLATE_PROXY_RETRIES + 1):
        timeout_s = base_timeout * (1.0 + 0.4 * (attempt - 1))
        timeout = httpx.Timeout(timeout=timeout_s, connect=min(12.0, timeout_s))
        try:
            async with httpx.AsyncClient(timeout=timeout) as http:
                resp = await http.post(url.rstrip("/") + "/translate", headers=_proxy_headers(settings.translation_proxy_token), json=payload)
                resp.raise_for_status()
                data = resp.json()
                out = str(data.get("translation") or "").strip()
                if not out:
                    raise RuntimeError("empty translation from proxy")
                return out
        except (
            httpx.ReadTimeout,
            httpx.ConnectTimeout,
            httpx.ReadError,
            httpx.ConnectError,
            httpx.RemoteProtocolError,
        ) as e:
            last_error = e
            if attempt >= _TRANSLATE_PROXY_RETRIES:
                raise
            await asyncio.sleep(0.8 * attempt)

    if last_error is not None:
        raise last_error
    raise RuntimeError("translation proxy single failed without details")


async def _translate_proxy_batch(values: list[str]) -> dict[str, str]:
    url = str(settings.translation_proxy_url or "").strip()
    if not url:
        return {}
    base_timeout = max(1000, int(settings.translation_proxy_timeout_ms)) / 1000.0
    payload = {"values": values}
    last_error: Exception | None = None
    data: dict[str, object] | None = None

    for attempt in range(1, _TRANSLATE_PROXY_RETRIES + 1):
        timeout_s = base_timeout * (1.0 + 0.5 * (attempt - 1))
        timeout = httpx.Timeout(timeout=timeout_s, connect=min(12.0, timeout_s))
        try:
            async with httpx.AsyncClient(timeout=timeout) as http:
                resp = await http.post(
                    url.rstrip("/") + "/translate-batch",
                    headers=_proxy_headers(settings.translation_proxy_token),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
            break
        except (
            httpx.ReadTimeout,
            httpx.ConnectTimeout,
            httpx.ReadError,
            httpx.ConnectError,
            httpx.RemoteProtocolError,
        ) as e:
            last_error = e
            if attempt >= _TRANSLATE_PROXY_RETRIES:
                raise
            await asyncio.sleep(0.9 * attempt)

    if data is None:
        if last_error is not None:
            raise last_error
        return {}

    out = data.get("translations")
    if not isinstance(out, dict):
        return {}
    result: dict[str, str] = {}
    for k, v in out.items():
        if isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip():
            result[k.strip()] = v.strip()
    return result


async def _translate_any(client: AsyncOpenAI | None, text_value: str) -> str:
    if settings.translation_proxy_url:
        return await _translate_proxy_single(text_value)
    if client is None:
        raise RuntimeError("translator is not configured")
    return await _translate_to_english(client, text_value)


async def _translate_batch_any(client: AsyncOpenAI | None, values: list[str]) -> dict[str, str]:
    if settings.translation_proxy_url:
        return await _translate_proxy_batch(values)
    if client is None:
        return {}
    return await _translate_batch_to_english(client, values)


def _dedupe_values(values: list[str]) -> list[str]:
    uniq: list[str] = []
    seen: set[str] = set()
    for value in values:
        s = str(value or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        uniq.append(s)
    return uniq


def _chunks(values: list[str], size: int) -> list[list[str]]:
    if size <= 0:
        return [values]
    return [values[i : i + size] for i in range(0, len(values), size)]


async def _translate_batch_resilient(client: AsyncOpenAI | None, values: list[str]) -> dict[str, str]:
    uniq = _dedupe_values(values)
    if not uniq:
        return {}

    out: dict[str, str] = {}
    for chunk_idx, chunk in enumerate(_chunks(uniq, _TRANSLATE_PROXY_BATCH_CHUNK_SIZE), start=1):
        chunk_result: dict[str, str] = {}
        try:
            chunk_result = await _translate_batch_any(client, chunk)
        except Exception as e:
            print(
                {
                    "stage": "warning",
                    "message": "batch translation chunk failed",
                    "chunk_index": chunk_idx,
                    "chunk_size": len(chunk),
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "error_repr": repr(e),
                },
                flush=True,
            )

        for k, v in chunk_result.items():
            s = str(v or "").strip()
            if s:
                out[k] = s

        missing = [value for value in chunk if value not in out]
        if not missing:
            continue

        for value in missing:
            try:
                one = await _translate_any(client, value)
            except Exception:
                continue
            one_s = str(one or "").strip()
            if one_s:
                out[value] = one_s

    return out


async def _translate_batch_to_english(client: AsyncOpenAI, values: list[str]) -> dict[str, str]:
    uniq = []
    seen = set()
    for v in values:
        s = str(v or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        uniq.append(s)
    if not uniq:
        return {}

    prompt = (
        "Translate the following car brand/model names from Chinese to English. "
        "Return ONLY strict JSON object where each key is original string and value is translation. "
        "No markdown, no comments.\n"
        + json.dumps(uniq, ensure_ascii=False)
    )
    resp = await client.chat.completions.create(
        model=settings.openai_translation_model,
        messages=[
            {"role": "system", "content": "You are a precise automotive translator."},
            {"role": "user", "content": prompt},
        ],
    )
    text_out = ((resp.choices[0].message.content or "").strip() if resp.choices else "").strip()
    if not text_out:
        return {}
    cleaned = text_out
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", cleaned).strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    try:
        obj = json.loads(cleaned)
    except Exception:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            obj = json.loads(cleaned[start : end + 1])
        except Exception:
            return {}
    if not isinstance(obj, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in obj.items():
        if isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip():
            out[k.strip()] = v.strip()
    return out


def _is_english_text(text_value: str | None) -> bool:
    if not text_value:
        return False
    s = str(text_value)
    return bool(_RE_HAS_LATIN.search(s)) and not bool(_RE_HAS_ZH.search(s))


async def _llm_normalize(client: AsyncOpenAI, *, raw_data: dict, original_url: str) -> dict:
    responses = raw_data.get("responses")
    if isinstance(responses, list):
        responses = responses[:3]
    else:
        responses = []
    payload = {
        "url": original_url,
        "dom": raw_data.get("dom") or {},
        "responses": responses,
    }
    resp = await client.chat.completions.create(
        model=settings.openai_normalize_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You extract structured used car listing data from Chinese sources. "
                    "Return ONLY valid JSON. "
                    "Fields: brand, model, year, mileage_km, price_cny, city, engine_type, engine_volume_l, power_hp, transmission, drive_type, vin, owners_count, eco_standard, color, trim, interior_material. "
                    "brand and model must be in English if possible. Missing values must be null."
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
        ],
        temperature=0,
    )
    text_out = ((resp.choices[0].message.content or "").strip() if resp.choices else "").strip()
    if not text_out:
        return {}
    cleaned = text_out.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", cleaned).strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[: -3].strip()
    try:
        obj = json.loads(cleaned)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        pass

    try:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            obj = json.loads(cleaned[start : end + 1])
            return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}
    return {}


def _create_scraper(source: str, *, max_images: int) -> BaseScraper:
    source_code = str(source or "").strip().lower()
    if source_code == "che168":
        return Che168Scraper(max_images=max_images)
    if source_code == "dongchedi":
        return DongchediScraper(max_images=max_images)
    if source_code == "guazi":
        return GuaziScraper(max_images=max_images)
    raise ValueError(f"Unsupported source: {source}")


async def run(
    source: str,
    limit: int,
    download_images: bool,
    *,
    dry_run: bool,
    max_images: int,
    skip_existing: bool,
    delete_old: int,
    move_deleted_media: bool,
    purge_deleted_media: bool,
    english_only: bool,
    translate_chinese: bool,
    clean_extra_fields: bool,
    llm_normalize: bool,
    throttle_ms: int,
) -> None:
    scraper = _create_scraper(source, max_images=max_images)
    translate_mode = "openai"
    if settings.translation_proxy_url:
        translate_mode = "proxy"
    print(
        {
            "stage": "scrape_start",
            "source": scraper.source_code,
            "limit": limit,
            "download_images": download_images,
            "translate_mode": translate_mode,
        },
        flush=True,
    )
    listings = await scraper.scrape(limit=limit)

    if dry_run:
        print(
            {
                "stage": "dry_run_result",
                "source": scraper.source_code,
                "count": len(listings),
                "sample_ids": [x.source_listing_id for x in listings[:5]],
                "sample_urls": [x.original_url for x in listings[:3]],
            },
            flush=True,
        )
        return

    if len(listings) != limit:
        print({"stage": "warning", "message": f"{scraper.source_code}: expected {limit} listings, got {len(listings)}"}, flush=True)

    media_root = pathlib.Path(settings.media_dir)
    media_to_delete_root = media_root / "_to_delete"
    translation_cache_path = str((pathlib.Path(settings.media_dir).parent / "translation_cache.json").resolve())
    throttle_s = max(0, int(throttle_ms)) / 1000.0

    client: AsyncOpenAI | None = None
    if (translate_chinese or llm_normalize) and settings.openai_api_key:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
    translator_ready = bool(settings.translation_proxy_url) or (client is not None)
    translate_cache: dict[str, str] = load_cache(translation_cache_path)
    cache_changed = False

    async with SessionLocal() as session:
        source_id = await get_source_id(session, scraper.source_code)

        if clean_extra_fields and not llm_normalize:
            await session.execute(
                text(
                    "UPDATE listings SET "
                    "power_hp=NULL, transmission=NULL, "
                    "city=NULL, region=NULL, vin=NULL, owners_count=NULL, eco_standard=NULL, color=NULL, trim=NULL, interior_material=NULL, "
                    "title_original=NULL, description_original=NULL, equipment_original=NULL, seller_comments_original=NULL "
                    "WHERE source_id=:sid"
                ),
                {"sid": source_id},
            )

        # Экономим токены: неизвестные китайские brand/model переводим одним батч-запросом.
        if translator_ready and translate_chinese:
            pending: list[str] = []
            for listing in listings:
                b0 = listing.normalized.get("brand")
                m0 = listing.normalized.get("model")
                b1 = normalize_by_dict(b0, BRAND_MAP)
                m1 = normalize_by_dict(m0, MODEL_MAP)
                if isinstance(b0, str) and isinstance(b1, str) and b1 != b0:
                    listing.normalized["brand"] = b1
                    translate_cache[b0] = b1
                    cache_changed = True
                if isinstance(m0, str) and isinstance(m1, str) and m1 != m0:
                    listing.normalized["model"] = m1
                    translate_cache[m0] = m1
                    cache_changed = True

                b = listing.normalized.get("brand")
                m = listing.normalized.get("model")
                if isinstance(b, str) and has_chinese(b) and b not in translate_cache:
                    pending.append(b)
                if isinstance(m, str) and has_chinese(m) and m not in translate_cache:
                    pending.append(m)
                for field_name in _TRANSLATABLE_TEXT_FIELDS:
                    vv = listing.normalized.get(field_name)
                    if isinstance(vv, str) and has_chinese(vv) and vv not in translate_cache:
                        pending.append(vv)
            if pending:
                pending_unique = len(set(str(x or "").strip() for x in pending if str(x or "").strip()))
                batch = await _translate_batch_resilient(client, pending)
                for k, v in batch.items():
                    if k not in translate_cache:
                        translate_cache[k] = v
                        cache_changed = True
                unresolved = max(0, pending_unique - len(batch))
                if unresolved > 0:
                    print(
                        {
                            "stage": "warning",
                            "message": "batch translation incomplete",
                            "pending_unique": pending_unique,
                            "resolved": len(batch),
                            "unresolved": unresolved,
                        },
                        flush=True,
                    )

        for i, listing in enumerate(listings, start=1):
            should_download_images = bool(download_images)
            if client is not None and llm_normalize:
                try:
                    llm = await _llm_normalize(client, raw_data=listing.raw_data, original_url=listing.original_url)
                    if isinstance(llm, dict):
                        mapping = {
                            "brand": _as_str,
                            "model": _as_str,
                            "year": _as_int,
                            "mileage_km": _as_int,
                            "price_cny": _as_float,
                            "city": _as_str,
                            "engine_type": _as_str,
                            "engine_volume_l": _as_float,
                            "power_hp": _as_int,
                            "transmission": _as_str,
                            "drive_type": _as_str,
                            "vin": _as_str,
                            "owners_count": _as_int,
                            "eco_standard": _as_str,
                            "color": _as_str,
                            "trim": _as_str,
                            "interior_material": _as_str,
                        }
                        for k, conv in mapping.items():
                            if k not in llm:
                                continue
                            val = conv(llm.get(k))
                            if val is not None:
                                listing.normalized[k] = val
                        listing.raw_data["llm"] = llm
                except Exception as e:
                    print(
                        {
                            "stage": "warning",
                            "message": "llm_normalize failed",
                            "source_listing_id": listing.source_listing_id,
                            "error": str(e),
                        },
                        flush=True,
                    )

            # Офлайн-нормализация словарём.
            b0 = listing.normalized.get("brand")
            m0 = listing.normalized.get("model")
            b1 = normalize_by_dict(b0, BRAND_MAP)
            m1 = normalize_by_dict(m0, MODEL_MAP)
            if isinstance(b0, str) and isinstance(b1, str) and b1 != b0:
                listing.normalized["brand"] = b1
                translate_cache[b0] = b1
                cache_changed = True
            if isinstance(m0, str) and isinstance(m1, str) and m1 != m0:
                listing.normalized["model"] = m1
                translate_cache[m0] = m1
                cache_changed = True

            if translate_chinese:
                b = listing.normalized.get("brand")
                m = listing.normalized.get("model")
                changed = False

                if isinstance(b, str) and has_chinese(b):
                    if b in translate_cache:
                        listing.normalized["brand"] = translate_cache[b]
                        changed = True
                    elif translator_ready:
                        try:
                            translate_cache[b] = await _translate_any(client, b)
                            cache_changed = True
                            listing.normalized["brand"] = translate_cache[b]
                            changed = True
                        except Exception as e:
                            print(
                                {
                                    "stage": "warning",
                                    "message": "translation failed (brand)",
                                    "source_listing_id": listing.source_listing_id,
                                    "error": str(e),
                                },
                                flush=True,
                            )
                            translate_cache[b] = b
                    else:
                        print(
                            {
                                "stage": "warning",
                                "message": "missing translation in cache (brand)",
                                "source_listing_id": listing.source_listing_id,
                                "value": b,
                            },
                            flush=True,
                        )

                if isinstance(m, str) and has_chinese(m):
                    if m in translate_cache:
                        listing.normalized["model"] = translate_cache[m]
                        changed = True
                    elif translator_ready:
                        try:
                            translate_cache[m] = await _translate_any(client, m)
                            cache_changed = True
                            listing.normalized["model"] = translate_cache[m]
                            changed = True
                        except Exception as e:
                            print(
                                {
                                    "stage": "warning",
                                    "message": "translation failed (model)",
                                    "source_listing_id": listing.source_listing_id,
                                    "error": str(e),
                                },
                                flush=True,
                            )
                            translate_cache[m] = m
                    else:
                        print(
                            {
                                "stage": "warning",
                                "message": "missing translation in cache (model)",
                                "source_listing_id": listing.source_listing_id,
                                "value": m,
                            },
                            flush=True,
                        )

                for field_name in _TRANSLATABLE_TEXT_FIELDS:
                    vv = listing.normalized.get(field_name)
                    if not (isinstance(vv, str) and has_chinese(vv)):
                        continue
                    if vv in translate_cache:
                        listing.normalized[field_name] = translate_cache[vv]
                        changed = True
                        continue
                    if translator_ready:
                        try:
                            translate_cache[vv] = await _translate_any(client, vv)
                            cache_changed = True
                            listing.normalized[field_name] = translate_cache[vv]
                            changed = True
                        except Exception as e:
                            print(
                                {
                                    "stage": "warning",
                                    "message": f"translation failed ({field_name})",
                                    "source_listing_id": listing.source_listing_id,
                                    "error": str(e),
                                },
                                flush=True,
                            )
                            translate_cache[vv] = vv
                    else:
                        print(
                            {
                                "stage": "warning",
                                "message": f"missing translation in cache ({field_name})",
                                "source_listing_id": listing.source_listing_id,
                                "value": vv,
                            },
                            flush=True,
                        )

                listing.raw_data["translated"] = bool(changed)

            # Временный режим: оставляем только бренды, выглядящие как английские.
            b2 = listing.normalized.get("brand")
            if english_only and not _is_english_text(b2):
                print(
                    {
                        "stage": "skip_non_english_brand",
                        "i": i,
                        "total": len(listings),
                        "source_listing_id": listing.source_listing_id,
                        "brand": b2,
                        "url": listing.original_url,
                    },
                    flush=True,
                )
                continue

            if skip_existing:
                existing = await get_listing_by_source(session, source_id, listing.source_listing_id)
                if existing:
                    if client is not None and translate_chinese and bool(listing.raw_data.get("translated")):
                        await session.execute(
                            text("UPDATE listings SET brand=:brand, model=:model, updated_at=NOW() WHERE id=:id"),
                            {
                                "id": existing["id"],
                                "brand": listing.normalized.get("brand"),
                                "model": listing.normalized.get("model"),
                            },
                        )

                    if download_images and listing.image_urls:
                        need_refresh = True
                        try:
                            res = await session.execute(
                                text(
                                    "SELECT local_path FROM listing_images WHERE listing_id=:lid ORDER BY position ASC LIMIT 1"
                                ),
                                {"lid": existing["id"]},
                            )
                            first_lp = res.scalar()
                            if first_lp:
                                p = pathlib.Path(str(first_lp))
                                if p.exists():
                                    need_refresh = False
                        except Exception:
                            need_refresh = True

                        if need_refresh:
                            await session.execute(
                                text("DELETE FROM listing_images WHERE listing_id=:lid"),
                                {"lid": existing["id"]},
                            )
                            kept: list[tuple[str, str | None, str | None]] = []
                            for pos, img_url in enumerate(listing.image_urls):
                                local_path = None
                                checksum = None
                                try:
                                    base = media_root / listing.source_code / listing.source_listing_id / f"{pos:03d}"
                                    local_path, checksum = await download_image(img_url, base)
                                except Exception as e:
                                    print(
                                        {
                                            "stage": "download_image_failed",
                                            "source_listing_id": listing.source_listing_id,
                                            "position": pos,
                                            "image_url": img_url,
                                            "error": str(e),
                                            "error_type": type(e).__name__,
                                            "error_repr": repr(e),
                                        },
                                        flush=True,
                                    )
                                    local_path, checksum = None, None
                                if throttle_s > 0:
                                    await asyncio.sleep(throttle_s)

                                if local_path and not local_path.lower().endswith(".webp"):
                                    local_path, checksum = None, None

                                if local_path:
                                    kept.append((img_url, local_path, checksum))

                            for new_pos, (img_url, local_path, checksum) in enumerate(kept):
                                await upsert_image(
                                    session,
                                    listing_id=existing["id"],
                                    position=new_pos,
                                    source_url=img_url,
                                    local_path=local_path,
                                    checksum=checksum,
                                )
                            if len(kept) != len(listing.image_urls):
                                print(
                                    {
                                        "stage": "download_images_partial",
                                        "source_listing_id": listing.source_listing_id,
                                        "listing_id": str(existing["id"]),
                                        "saved": len(kept),
                                        "expected": len(listing.image_urls),
                                    },
                                    flush=True,
                                )

                        should_download_images = False
                    else:
                        should_download_images = False

                    if not llm_normalize:
                        print(
                            {
                                "stage": "skip_existing",
                                "i": i,
                                "total": len(listings),
                                "source_listing_id": listing.source_listing_id,
                                "url": listing.original_url,
                            },
                            flush=True,
                        )
                        continue
            print(
                {
                    "stage": "upsert_listing",
                    "i": i,
                    "total": len(listings),
                    "source_listing_id": listing.source_listing_id,
                    "url": listing.original_url,
                },
                flush=True,
            )

            # Базовые поля каталога сохраняем всегда.
            # Остальные колонки в listings принудительно обнуляем, чтобы не тянуть за собой старые значения.
            keep_extra = (not clean_extra_fields) or llm_normalize
            normalized_db = {
                "brand": listing.normalized.get("brand"),
                "model": listing.normalized.get("model"),
                "year": listing.normalized.get("year"),
                "mileage_km": listing.normalized.get("mileage_km"),
                "first_registration_date": listing.normalized.get("first_registration_date"),
                "engine_type": listing.normalized.get("engine_type"),
                "engine_volume_l": listing.normalized.get("engine_volume_l"),
                "power_hp": listing.normalized.get("power_hp") if keep_extra else None,
                "transmission": listing.normalized.get("transmission") if keep_extra else None,
                "drive_type": listing.normalized.get("drive_type"),
                "price_cny": listing.normalized.get("price_cny"),
                "city": listing.normalized.get("city") if keep_extra else None,
                "region": listing.normalized.get("region") if keep_extra else None,
                "vin": listing.normalized.get("vin") if keep_extra else None,
                "owners_count": listing.normalized.get("owners_count") if keep_extra else None,
                "eco_standard": listing.normalized.get("eco_standard") if keep_extra else None,
                "color": listing.normalized.get("color") if keep_extra else None,
                "trim": listing.normalized.get("trim") if keep_extra else None,
                "interior_material": listing.normalized.get("interior_material") if keep_extra else None,
            }
            _enforce_engine_consistency(normalized_db)

            listing_id = await upsert_listing(
                session,
                source_id=source_id,
                source_listing_id=listing.source_listing_id,
                original_url=listing.original_url,
                scraped_at=listing.scraped_at,
                status=listing.status,
                ad_hash=listing.ad_hash,
                content_checksum=listing.content_checksum,
                normalized=normalized_db,
                originals=listing.originals,
                raw_data=listing.raw_data,
            )

            if should_download_images and listing.image_urls:
                await session.execute(
                    text("DELETE FROM listing_images WHERE listing_id=:lid"),
                    {"lid": listing_id},
                )
                kept: list[tuple[str, str | None, str | None]] = []
                for pos, img_url in enumerate(listing.image_urls):
                    if pos == 0:
                        print(
                            {
                                "stage": "download_images",
                                "listing_id": str(listing_id),
                                "count": len(listing.image_urls),
                            },
                            flush=True,
                        )
                    local_path = None
                    checksum = None
                    try:
                        base = media_root / listing.source_code / listing.source_listing_id / f"{pos:03d}"
                        local_path, checksum = await download_image(img_url, base)
                    except Exception as e:
                        print(
                            {
                                "stage": "download_image_failed",
                                "source_listing_id": listing.source_listing_id,
                                "position": pos,
                                "image_url": img_url,
                                "error": str(e),
                                "error_type": type(e).__name__,
                                "error_repr": repr(e),
                            },
                            flush=True,
                        )
                        local_path, checksum = None, None
                    if throttle_s > 0:
                        await asyncio.sleep(throttle_s)

                    if local_path and not local_path.lower().endswith(".webp"):
                        local_path, checksum = None, None

                    if local_path:
                        kept.append((img_url, local_path, checksum))

                for new_pos, (img_url, local_path, checksum) in enumerate(kept):
                    await upsert_image(
                        session,
                        listing_id=listing_id,
                        position=new_pos,
                        source_url=img_url,
                        local_path=local_path,
                        checksum=checksum,
                    )
                if len(kept) != len(listing.image_urls):
                    print(
                        {
                            "stage": "download_images_partial",
                            "source_listing_id": listing.source_listing_id,
                            "listing_id": str(listing_id),
                            "saved": len(kept),
                            "expected": len(listing.image_urls),
                        },
                        flush=True,
                    )

            elif should_download_images and not listing.image_urls:
                pass

            if throttle_s > 0:
                await asyncio.sleep(throttle_s)

        if delete_old > 0:
            res = await session.execute(
                text(
                    "SELECT id, source_listing_id FROM listings WHERE source_id=:sid ORDER BY scraped_at ASC LIMIT :lim"
                ),
                {"sid": source_id, "lim": int(delete_old)},
            )
            to_delete = [(r[0], r[1]) for r in res.all()]

            if to_delete:
                # Keep delete SQL compatible with asyncpg + SQLAlchemy text() binding.
                for listing_id, _ in to_delete:
                    await session.execute(
                        text("DELETE FROM listings WHERE id = :id"),
                        {"id": listing_id},
                    )

            if purge_deleted_media:
                for _, source_listing_id in to_delete:
                    src_dir = media_root / scraper.source_code / str(source_listing_id)
                    _safe_remove_dir(src_dir)
            elif move_deleted_media:
                for _, source_listing_id in to_delete:
                    src_dir = media_root / scraper.source_code / str(source_listing_id)
                    dst_dir = media_to_delete_root / scraper.source_code / str(source_listing_id)
                    _safe_move_dir(src_dir, dst_dir)

        await session.commit()

    if cache_changed:
        save_cache(translation_cache_path, translate_cache)

    print(
        {
            "source": scraper.source_code,
            "limit": limit,
            "download_images": download_images,
            "scraped_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="guazi", choices=["che168", "dongchedi", "guazi"])
    parser.add_argument("--limit", type=int, default=int(settings.initial_load_limit))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-images", type=int, default=int(settings.che168_max_images))
    parser.add_argument("--allow-non-english-brand", action="store_true")
    parser.add_argument("--translate-chinese", action="store_true")
    parser.add_argument("--llm-normalize", action="store_true")
    parser.add_argument("--no-clean-extra-fields", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--no-skip-existing", action="store_true")
    parser.add_argument("--delete-old", type=int, default=0)
    parser.add_argument("--move-deleted-media", action="store_true")
    parser.add_argument("--purge-deleted-media", action="store_true")
    parser.add_argument("--skip-images", action="store_true")
    parser.add_argument("--throttle-ms", type=int, default=0)
    args = parser.parse_args()

    skip_existing = True
    if bool(args.skip_existing):
        skip_existing = True
    if bool(args.no_skip_existing):
        skip_existing = False

    move_deleted_media = True
    purge_deleted_media = False
    if bool(args.purge_deleted_media):
        move_deleted_media = False
        purge_deleted_media = True
    if bool(args.move_deleted_media):
        move_deleted_media = True

    asyncio.run(
        run(
            source=str(args.source),
            limit=int(args.limit),
            download_images=not bool(args.skip_images),
            dry_run=bool(args.dry_run),
            max_images=int(args.max_images),
            skip_existing=skip_existing,
            delete_old=int(args.delete_old),
            move_deleted_media=move_deleted_media,
            purge_deleted_media=purge_deleted_media,
            english_only=not bool(args.allow_non_english_brand),
            translate_chinese=bool(args.translate_chinese),
            clean_extra_fields=not bool(args.no_clean_extra_fields),
            llm_normalize=bool(args.llm_normalize),
            throttle_ms=int(args.throttle_ms),
        )
    )


if __name__ == "__main__":
    main()
