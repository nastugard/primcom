from __future__ import annotations

import asyncio
import datetime as dt
import json
import random
import re
from typing import Any

from playwright.async_api import async_playwright

from app.scrapers.base import BaseScraper, ScrapedListing
from app.scrapers.che168 import (
    _collect_dom_snapshot,
    _collect_image_urls,
    _extract_texts_from_dom,
    _filter_and_limit_image_urls,
    _setup_page,
)
from app.utils.hashing import sha256_text
from app.utils.name_translation import BRAND_MAP, MODEL_MAP, normalize_by_dict
from app.utils.numbers import parse_year


_DETAIL_ID_RE = re.compile(r"/usedcar/(\d{7,})(?:[/?#]|$)", re.I)
_ID_RE = re.compile(r"(\d{6,})")
_RE_IMAGE_URL = re.compile(r"\.(jpe?g|png|webp)(\?|$)", re.I)
_RE_WEBP = re.compile(r"(\.webp(\?|$)|[?&]format=webp\b|\bwebp\b)", re.I)
_RE_NOT_IMAGE_URL = re.compile(r"\.(css|js|svg)(\?|$)", re.I)
_RE_ZH = re.compile(r"[\u4e00-\u9fff]")
_RE_CAPTCHA = re.compile(r"(验证码|人机验证|安全验证|captcha)", re.I)
_RE_YEAR = re.compile(r"((?:19|20)\d{2})\s*款")
_RE_MILEAGE_WAN = re.compile(r"(\d+(?:\.\d+)?)\s*万\s*公里")
_RE_MILEAGE_KM = re.compile(r"(\d{2,6})\s*公里")
_KNOWN_BRANDS = [
    "Audi",
    "BMW",
    "Buick",
    "Cadillac",
    "Changan",
    "Ford",
    "Geely",
    "Honda",
    "Hyundai",
    "Jaguar",
    "Kia",
    "Land Rover",
    "Lexus",
    "Lincoln",
    "MINI",
    "Mazda",
    "Mercedes-Benz",
    "Nissan",
    "Porsche",
    "Skoda",
    "Tesla",
    "Toyota",
    "Volkswagen",
    "Volvo",
]


def _extract_links(anchors: list[dict[str, str]], limit: int) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[str] = set()

    for a in anchors:
        href = str(a.get("href") or "").strip()
        if href.startswith("/"):
            href = f"https://www.dongchedi.com{href}"
        if href.startswith("//"):
            href = "https:" + href
        if not href.startswith("http"):
            continue
        if "dongchedi.com" not in href:
            continue
        m_detail = _DETAIL_ID_RE.search(href)
        if not m_detail:
            continue

        listing_id = m_detail.group(1)
        if listing_id in seen:
            continue
        seen.add(listing_id)
        out.append((listing_id, href))
        if len(out) >= limit:
            break

    return out


def _extract_ids_from_json(data: Any) -> list[str]:
    out: list[str] = []

    def walk(x: Any):
        if isinstance(x, dict):
            for k, v in x.items():
                lk = str(k).lower()
                if lk in ("id", "carid", "seriesid", "usedcarid"):
                    if isinstance(v, int):
                        out.append(str(v))
                    elif isinstance(v, str) and v.isdigit() and len(v) >= 6:
                        out.append(v)
                walk(v)
            return
        if isinstance(x, list):
            for it in x:
                walk(it)

    walk(data)
    return out


def _extract_image_urls_from_raw(raw: dict[str, Any], *, limit: int) -> list[str]:
    urls: list[str] = []

    def add(u: str):
        x = str(u or "").strip()
        if not x.startswith("http"):
            return
        if _RE_NOT_IMAGE_URL.search(x):
            return
        if not (_RE_IMAGE_URL.search(x) or _RE_WEBP.search(x)):
            lx = x.lower()
            if "dongchedi.com" not in lx and "toutiaoimg.com" not in lx and "byteimg.com" not in lx and "cdn" not in lx and "img" not in lx:
                return
        urls.append(x)

    def walk(x: Any):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
            return
        if isinstance(x, list):
            for it in x:
                walk(it)
            return
        if isinstance(x, str):
            add(x)

    walk(raw.get("responses") or [])
    return _filter_and_limit_image_urls(urls, limit=limit)


def _extract_mileage_km(text_value: str | None) -> int | None:
    if not text_value:
        return None
    s = str(text_value).replace(",", "")
    m_wan = _RE_MILEAGE_WAN.search(s)
    if m_wan:
        try:
            return int(float(m_wan.group(1)) * 10000.0)
        except Exception:
            return None
    m_km = _RE_MILEAGE_KM.search(s)
    if m_km:
        try:
            return int(m_km.group(1))
        except Exception:
            return None
    return None


def _cleanup_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _split_brand_model(title: str) -> tuple[str | None, str | None]:
    t = _cleanup_spaces(title)
    if not t:
        return None, None

    # Отрезаем хвосты с пробегом/городом и т.п.
    t = re.split(r"[|｜丨]", t)[0].strip()
    m_year = _RE_YEAR.search(t)
    prefix = t[: m_year.start()].strip() if m_year else t
    suffix = t[m_year.start() :].strip() if m_year else ""

    # Явное совпадение по известным EN-брендам в начале строки.
    for b in _KNOWN_BRANDS:
        if prefix.lower().startswith(b.lower()):
            tail = prefix[len(b) :].strip()
            if tail:
                return b, _cleanup_spaces(f"{tail} {suffix}").strip()
            return b, _cleanup_spaces(suffix) or None

    # Склейка вида AudiS3 / JaguarXFL / Hyundaiix35
    m_compact = re.match(r"^([A-Z][a-z]+)([A-Za-z0-9].*)$", prefix)
    if m_compact:
        b = m_compact.group(1)
        tail = m_compact.group(2).strip()
        return b, _cleanup_spaces(f"{tail} {suffix}").strip()

    # Случай "Passat领驭" -> brand=Passat, model=领驭 + suffix
    m_mix = re.match(r"^([A-Za-z][A-Za-z0-9 .+\-]*)([\u4e00-\u9fff].*)$", prefix)
    if m_mix:
        b = m_mix.group(1).strip()
        tail = m_mix.group(2).strip()
        return b, _cleanup_spaces(f"{tail} {suffix}").strip()

    parts = [p for p in re.split(r"\s+", prefix) if p]
    if not parts:
        return None, None
    if len(parts) == 1:
        return parts[0], _cleanup_spaces(suffix) or None
    return parts[0], _cleanup_spaces(" ".join(parts[1:] + ([suffix] if suffix else []))) or None


def _normalize_from_dom(dom: dict[str, str | None]) -> tuple[dict[str, Any], dict[str, Any]]:
    title = str(dom.get("title") or dom.get("h1") or "").strip()
    body = " ".join([str(v or "") for v in dom.values()])
    brand_raw, model_raw = _split_brand_model(title)
    brand = normalize_by_dict(brand_raw, BRAND_MAP) if brand_raw else brand_raw
    model = normalize_by_dict(model_raw, MODEL_MAP) if model_raw else model_raw
    if isinstance(model, str):
        model = _cleanup_spaces(model)
        if isinstance(brand, str) and model.lower().startswith(brand.lower() + " "):
            model = model[len(brand) :].strip()
        if _RE_ZH.search(model):
            model = _cleanup_spaces(_RE_ZH.sub(" ", model)) or model

    normalized: dict[str, Any] = {
        "brand": brand,
        "model": model,
        "year": parse_year(dom.get("year") or title or body),
        "mileage_km": _extract_mileage_km(dom.get("mileage") or title or body),
    }
    return normalized, {}


class DongchediScraper(BaseScraper):
    source_code = "dongchedi"

    def __init__(self, *, max_images: int = 16) -> None:
        self.max_images = max(0, int(max_images))

    async def scrape(self, limit: int) -> list[ScrapedListing]:
        if limit <= 0:
            return []

        start_url = "https://www.dongchedi.com/usedcar/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x"
        scraped: list[ScrapedListing] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await _setup_page(browser)

            await page.goto(start_url, wait_until="domcontentloaded")
            await asyncio.sleep(2.2)

            list_json: list[dict[str, Any]] = []

            async def on_list_response(resp):
                try:
                    ct = (resp.headers.get("content-type") or "").lower()
                    if "application/json" not in ct:
                        return
                    js = await resp.json()
                    if isinstance(js, dict):
                        list_json.append(js)
                except Exception:
                    return

            page.on("response", on_list_response)

            found: list[tuple[str, str]] = []
            for _ in range(40):
                anchors = await page.evaluate(
                    """
() => Array.from(document.querySelectorAll("a")).map(a => ({ href: a.href || "" }))
"""
                )
                found = _extract_links(anchors, limit=limit)
                if len(found) >= limit:
                    break
                await page.mouse.wheel(0, 1800)
                await asyncio.sleep(1.0 + random.random() * 0.7)

            if len(found) < limit and list_json:
                ids: list[str] = []
                for js in list_json:
                    ids.extend(_extract_ids_from_json(js))
                seen = {x[0] for x in found}
                for iid in ids:
                    if iid in seen:
                        continue
                    seen.add(iid)
                    found.append((iid, f"https://www.dongchedi.com/usedcar/{iid}"))
                    if len(found) >= limit:
                        break

            page.remove_listener("response", on_list_response)

            for idx, (listing_id, detail_url) in enumerate(found[:limit], start=1):
                response_jsons: list[dict[str, Any]] = []

                async def on_detail_response(resp):
                    try:
                        ct = (resp.headers.get("content-type") or "").lower()
                        if "application/json" not in ct:
                            return
                        js = await resp.json()
                        if isinstance(js, dict):
                            response_jsons.append(js)
                    except Exception:
                        return

                page.on("response", on_detail_response)
                try:
                    await page.goto(detail_url, wait_until="domcontentloaded")
                    await asyncio.sleep(1.8)
                finally:
                    page.remove_listener("response", on_detail_response)

                dom_snapshot = _extract_texts_from_dom(await _collect_dom_snapshot(page))
                title_probe = str(dom_snapshot.get("title") or dom_snapshot.get("h1") or "")
                if _RE_CAPTCHA.search(title_probe):
                    continue
                raw = {"detail_url": detail_url, "responses": response_jsons, "dom": dom_snapshot}
                normalized, originals = _normalize_from_dom(dom_snapshot)

                image_urls = _extract_image_urls_from_raw(raw, limit=self.max_images)
                if not image_urls:
                    image_urls = await _collect_image_urls(page, limit=self.max_images)
                image_urls = _filter_and_limit_image_urls(image_urls, limit=self.max_images)

                content_checksum = sha256_text(
                    json.dumps(
                        {"normalized": normalized, "originals": originals},
                        ensure_ascii=False,
                        sort_keys=True,
                        default=str,
                    )
                )

                scraped.append(
                    ScrapedListing(
                        source_code=self.source_code,
                        source_listing_id=str(listing_id),
                        original_url=detail_url,
                        scraped_at=dt.datetime.now(dt.timezone.utc),
                        status="active",
                        ad_hash=sha256_text(f"{self.source_code}:{listing_id}"),
                        content_checksum=content_checksum,
                        normalized=normalized,
                        originals=originals,
                        raw_data=raw,
                        image_urls=image_urls,
                    )
                )

                if idx >= limit:
                    break
                await asyncio.sleep(1.0 + random.random() * 0.6)

            await page.context.close()
            await browser.close()

        return scraped
