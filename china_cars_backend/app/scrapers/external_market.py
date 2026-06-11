from __future__ import annotations

import asyncio
import datetime as dt
import json
import random
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

from playwright.async_api import Page, async_playwright

from app.core import settings
from app.scrapers.base import BaseScraper, ScrapedListing
from app.utils.hashing import sha256_text


_DETAIL_RE = re.compile(r"/brands/.+?/c(\d+)(?:[/?#]|$)", re.I)
_BAD_IMAGE_HINT_RE = re.compile(
    r"(qrcode|qr[-_]?code|wechat|weixin|mini(?:[-_]?program)?|logo|icon|sprite|favicon|placeholder|avatar|loading|default)",
    re.I,
)
_VERIFICATION_RE = re.compile(r"(killbot|security verification|user verification|captcha|正在验证|验证码|人机验证)", re.I)
_SPACE_RE = re.compile(r"\s+")
_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
_MILEAGE_RE = re.compile(r"(\d[\d\s,.]*)(?:\s*)(?:км|km|公里)\b", re.I)
_ENGINE_L_RE = re.compile(r"(?<![A-Za-z0-9])([1-9](?:[.,]\d{1,2})?)\s*(?:л|l|литр|liter)", re.I)
_POWER_RE = re.compile(r"(\d{2,4})\s*(?:л\.с\.|лс|hp|ps|horsepower)", re.I)
_PRICE_CNY_RE = re.compile(r"(?:¥|￥|CNY|RMB|元)\s*([\d\s,.]+)|([\d\s,.]+)\s*(?:¥|￥|CNY|RMB|元)", re.I)
_PRICE_WAN_RE = re.compile(r"([\d]+(?:[.,]\d+)?)\s*万")

_MARKET_SOURCE_CODE = {
    "china": "guazi",
    "korea": "korea_manual",
}

_SPEC_LABELS = {
    "brand": ("марка", "brand", "бренд"),
    "model": ("модель", "model"),
    "year": ("год", "year", "выпуск"),
    "mileage_km": ("пробег", "mileage", "kilometrage"),
    "price": ("цена", "price", "стоимость"),
    "engine_type": ("топливо", "fuel", "двигатель", "engine"),
    "engine_volume_l": ("объем", "объём", "volume", "displacement"),
    "power_hp": ("мощность", "power", "л.с", "hp"),
    "transmission": ("кпп", "трансмиссия", "transmission", "gearbox"),
    "drive_type": ("привод", "drive"),
    "body_type": ("кузов", "body"),
    "color": ("цвет", "color"),
    "city": ("город", "city"),
    "region": ("регион", "region"),
    "trim": ("комплектация", "trim", "grade", "edition"),
}


class ExternalMarketBlockedError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExternalMarketConfig:
    market: str
    source_code: str
    base_url: str
    list_path: str
    max_pages: int
    max_images: int
    throttle_ms: int


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return None
    text = _SPACE_RE.sub(" ", str(value).replace("\xa0", " ")).strip()
    return text or None


def _to_int(value: Any) -> int | None:
    text = _clean_text(value)
    if not text:
        return None
    m = re.search(r"\d[\d\s,.]*", text)
    if not m:
        return None
    digits = re.sub(r"\D", "", m.group(0))
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _to_float(value: Any) -> float | None:
    text = _clean_text(value)
    if not text:
        return None
    m = re.search(r"\d+(?:[.,]\d+)?", text)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "."))
    except ValueError:
        return None


def _first_text(*values: Any) -> str | None:
    for value in values:
        text = _clean_text(value)
        if text:
            return text
    return None


def _pick_from_tree(obj: Any, keys: tuple[str, ...]) -> Any:
    if isinstance(obj, dict):
        lowered = {str(k).lower(): v for k, v in obj.items()}
        for key in keys:
            if key.lower() in lowered and lowered[key.lower()] not in (None, ""):
                return lowered[key.lower()]
        for value in obj.values():
            found = _pick_from_tree(value, keys)
            if found not in (None, ""):
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _pick_from_tree(item, keys)
            if found not in (None, ""):
                return found
    return None


def _url_without_tracking(url: str) -> str:
    parsed = urlparse(url)
    return parsed._replace(query="", fragment="").geturl()


def _listing_id_from_url(url: str) -> str | None:
    m = _DETAIL_RE.search(urlparse(url).path)
    if not m:
        return None
    return m.group(1)


def _source_listing_id(market: str, url: str) -> str | None:
    external_id = _listing_id_from_url(url)
    if not external_id:
        return None
    return f"external_{market}_{external_id}"


def _page_url(base_url: str, path: str, page: int) -> str:
    full = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    sep = "&" if "?" in full else "?"
    return f"{full}{sep}page={int(page)}"


def _looks_blocked(title: str, body: str) -> bool:
    sample = f"{title}\n{body[:5000]}"
    return bool(_VERIFICATION_RE.search(sample))


def _filter_image_urls(urls: list[str], *, limit: int) -> list[str]:
    seen: set[str] = set()
    ranked: list[tuple[int, int, str]] = []
    for idx, raw in enumerate(urls):
        url = str(raw or "").strip()
        if not url.startswith("http"):
            continue
        low = url.lower()
        if low.startswith("data:image") or _BAD_IMAGE_HINT_RE.search(low):
            continue
        if not re.search(r"\.(jpe?g|png|webp)(\?|$)", low):
            continue
        canonical = _url_without_tracking(url)
        if canonical in seen:
            continue
        seen.add(canonical)
        score = 0
        if any(good in low for good in ("photo", "image", "upload", "album", "gallery", "large", "car")):
            score -= 2
        if re.search(r"\d{5,}", low):
            score -= 1
        ranked.append((score, idx, url))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in ranked[:limit]]


def _extract_price_cny(*texts: Any) -> float | None:
    joined = " ".join([str(t) for t in texts if t])
    m = _PRICE_CNY_RE.search(joined)
    if m:
        raw = m.group(1) or m.group(2) or ""
        value = _to_float(raw)
        if value is not None:
            return value
    m_wan = _PRICE_WAN_RE.search(joined)
    if m_wan and any(token in joined for token in ("万", "元", "￥", "¥")):
        value = _to_float(m_wan.group(1))
        if value is not None:
            return value * 10000
    return None


def _extract_mileage_km(*texts: Any) -> int | None:
    joined = " ".join([str(t) for t in texts if t])
    m = _MILEAGE_RE.search(joined)
    if not m:
        return None
    digits = re.sub(r"\D", "", m.group(1))
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _extract_year(*texts: Any) -> int | None:
    joined = " ".join([str(t) for t in texts if t])
    years = [int(x) for x in _YEAR_RE.findall(joined)]
    reasonable = [y for y in years if 1980 <= y <= dt.datetime.now().year + 1]
    return reasonable[0] if reasonable else None


def _extract_engine_volume_l(*texts: Any) -> float | None:
    joined = " ".join([str(t) for t in texts if t])
    m = _ENGINE_L_RE.search(joined)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def _extract_power_hp(*texts: Any) -> int | None:
    joined = " ".join([str(t) for t in texts if t])
    m = _POWER_RE.search(joined)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _extract_fuel(*texts: Any) -> str | None:
    joined = " ".join([str(t).lower() for t in texts if t])
    if any(x in joined for x in ("diesel", "дизель")):
        return "Дизель"
    if any(x in joined for x in ("hybrid", "гибрид")):
        return "Гибрид"
    if any(x in joined for x in ("electric", "электро", "ev")):
        return "Электро"
    if any(x in joined for x in ("gasoline", "petrol", "бензин")):
        return "Бензин"
    return None


def _extract_transmission(*texts: Any) -> str | None:
    joined = " ".join([str(t).lower() for t in texts if t])
    if any(x in joined for x in ("automatic", "автомат", "акпп", "at")):
        return "Автомат"
    if any(x in joined for x in ("manual", "механ", "мкпп", "mt")):
        return "Механика"
    if "cvt" in joined or "вариатор" in joined:
        return "Вариатор"
    if "robot" in joined or "робот" in joined:
        return "Робот"
    return None


def _extract_drive(*texts: Any) -> str | None:
    joined = " ".join([str(t).lower() for t in texts if t])
    if any(x in joined for x in ("4wd", "awd", "полный", "四驱")):
        return "Полный"
    if any(x in joined for x in ("front", "перед", "fwd", "前驱")):
        return "Передний"
    if any(x in joined for x in ("rear", "зад", "rwd", "后驱")):
        return "Задний"
    return None


def _title_brand_model(title: str | None) -> tuple[str | None, str | None]:
    text = _clean_text(title)
    if not text:
        return None, None
    words = text.split()
    if not words:
        return None, None
    brand = re.sub(r"[^0-9A-Za-zА-Яа-яЁё-]", "", words[0]).upper() or None
    model = " ".join(words[1:]).strip() or None
    return brand, model


def _spec_lookup(specs: dict[str, str], field: str) -> str | None:
    labels = _SPEC_LABELS.get(field, ())
    for label, value in specs.items():
        low = label.lower()
        if any(token in low for token in labels):
            return value
    return None


def _normalize_detail(*, title: str | None, specs: dict[str, str], json_data: list[Any], body_text: str) -> tuple[dict[str, Any], dict[str, Any]]:
    json_root: Any = json_data
    brand_from_title, model_from_title = _title_brand_model(title)
    brand = _first_text(
        _spec_lookup(specs, "brand"),
        _pick_from_tree(json_root, ("brand", "brandName", "make", "manufacturer")),
        brand_from_title,
    )
    model = _first_text(
        _spec_lookup(specs, "model"),
        _pick_from_tree(json_root, ("model", "modelName", "series", "seriesName", "name")),
        model_from_title,
    )
    price_text = _first_text(_spec_lookup(specs, "price"), _pick_from_tree(json_root, ("price", "priceText", "amount")))
    mileage_text = _first_text(_spec_lookup(specs, "mileage_km"), _pick_from_tree(json_root, ("mileage", "mileageText", "run", "odometer")))
    year_text = _first_text(_spec_lookup(specs, "year"), _pick_from_tree(json_root, ("year", "yearText", "registrationYear")))
    engine_text = _first_text(_spec_lookup(specs, "engine_type"), _pick_from_tree(json_root, ("fuel", "fuelType", "engine", "engineType")))
    volume_text = _first_text(_spec_lookup(specs, "engine_volume_l"), _pick_from_tree(json_root, ("engineVolume", "volume", "displacement")))
    power_text = _first_text(_spec_lookup(specs, "power_hp"), _pick_from_tree(json_root, ("power", "horsepower", "powerHp")))
    transmission_text = _first_text(_spec_lookup(specs, "transmission"), _pick_from_tree(json_root, ("transmission", "gearbox")))
    drive_text = _first_text(_spec_lookup(specs, "drive_type"), _pick_from_tree(json_root, ("drive", "driveType")))

    normalized = {
        "brand": brand,
        "model": model,
        "year": _to_int(year_text) or _extract_year(title, body_text),
        "mileage_km": _extract_mileage_km(mileage_text, body_text),
        "price_cny": _extract_price_cny(price_text, body_text),
        "engine_type": _extract_fuel(engine_text, body_text),
        "engine_volume_l": _to_float(volume_text) or _extract_engine_volume_l(volume_text, title, body_text),
        "power_hp": _to_int(power_text) or _extract_power_hp(power_text, body_text),
        "transmission": _first_text(_spec_lookup(specs, "transmission"), _extract_transmission(transmission_text, body_text)),
        "drive_type": _first_text(_spec_lookup(specs, "drive_type"), _extract_drive(drive_text, body_text)),
        "city": _first_text(_spec_lookup(specs, "city"), _pick_from_tree(json_root, ("city", "cityName"))),
        "region": _first_text(_spec_lookup(specs, "region"), _pick_from_tree(json_root, ("region", "regionName"))),
        "color": _first_text(_spec_lookup(specs, "color"), _pick_from_tree(json_root, ("color", "carColor"))),
        "trim": _first_text(_spec_lookup(specs, "trim"), _pick_from_tree(json_root, ("trim", "grade", "edition", "configuration"))),
    }
    normalized = {k: v for k, v in normalized.items() if v not in (None, "")}
    body_type = _spec_lookup(specs, "body_type")
    if body_type:
        normalized["body_type"] = body_type

    originals = {
        "title_original": title,
        "description_original": body_text[:4000] if body_text else None,
        "equipment_original": json.dumps(specs, ensure_ascii=False) if specs else None,
        "seller_comments_original": None,
    }
    return normalized, originals


class ExternalMarketScraper(BaseScraper):
    def __init__(self, *, market: str, max_pages: int, max_images: int, throttle_ms: int = 1000) -> None:
        market_value = str(market or "").strip().lower()
        if market_value not in _MARKET_SOURCE_CODE:
            raise ValueError(f"Unsupported market: {market}")
        base_url = str(settings.external_market_base_url or "").strip().rstrip("/")
        if not base_url:
            raise RuntimeError("EXTERNAL_MARKET_BASE_URL is not configured")
        list_path = settings.external_market_china_path if market_value == "china" else settings.external_market_korea_path
        self.config = ExternalMarketConfig(
            market=market_value,
            source_code=_MARKET_SOURCE_CODE[market_value],
            base_url=base_url,
            list_path=str(list_path or "").strip() or "/",
            max_pages=max(1, int(max_pages)),
            max_images=max(1, int(max_images)),
            throttle_ms=max(0, int(throttle_ms)),
        )
        self.source_code = self.config.source_code

    async def scrape(self, limit: int) -> list[ScrapedListing]:
        target = max(1, int(limit))
        pages = list(range(1, self.config.max_pages + 1))
        random.shuffle(pages)
        listings: list[ScrapedListing] = []
        seen_urls: set[str] = set()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                page.set_default_navigation_timeout(90_000)
                page.set_default_timeout(60_000)

                for page_no in pages:
                    list_url = _page_url(self.config.base_url, self.config.list_path, page_no)
                    print({"stage": "external_market_page_selected", "market": self.config.market, "page": page_no}, flush=True)
                    detail_urls = await self._collect_detail_urls(page, list_url)
                    random.shuffle(detail_urls)
                    for detail_url in detail_urls:
                        clean_url = _url_without_tracking(detail_url)
                        if clean_url in seen_urls:
                            continue
                        seen_urls.add(clean_url)
                        source_listing_id = _source_listing_id(self.config.market, clean_url)
                        if not source_listing_id:
                            continue
                        listing = await self._scrape_detail(page, clean_url, source_listing_id)
                        if listing is None:
                            continue
                        listings.append(listing)
                        if len(listings) >= target:
                            return listings
                        if self.config.throttle_ms > 0:
                            await asyncio.sleep(self.config.throttle_ms / 1000.0)
            finally:
                await browser.close()
        return listings

    async def _goto_checked(self, page: Page, url: str) -> tuple[str, str]:
        await page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        await page.wait_for_timeout(900)
        title = await page.title()
        body = await page.locator("body").inner_text(timeout=10_000)
        if _looks_blocked(title, body):
            raise ExternalMarketBlockedError(f"external market verification page detected at {url}")
        return title, body

    async def _collect_detail_urls(self, page: Page, list_url: str) -> list[str]:
        await self._goto_checked(page, list_url)
        hrefs = await page.evaluate(
            """
() => Array.from(document.querySelectorAll('a[href]'))
  .map(a => new URL(a.getAttribute('href'), location.href).href)
"""
        )
        urls: list[str] = []
        seen: set[str] = set()
        for href in hrefs if isinstance(hrefs, list) else []:
            url = _url_without_tracking(str(href))
            if not _DETAIL_RE.search(urlparse(url).path):
                continue
            if url in seen:
                continue
            seen.add(url)
            urls.append(url)
        print(
            {
                "stage": "external_market_links_found",
                "market": self.config.market,
                "count": len(urls),
            },
            flush=True,
        )
        return urls

    async def _scrape_detail(self, page: Page, url: str, source_listing_id: str) -> ScrapedListing | None:
        title, body_text = await self._goto_checked(page, url)
        detail = await self._collect_detail_payload(page)
        title = _first_text(detail.get("h1"), detail.get("og_title"), title)
        specs = detail.get("specs") if isinstance(detail.get("specs"), dict) else {}
        json_data = detail.get("json_data") if isinstance(detail.get("json_data"), list) else []
        normalized, originals = _normalize_detail(
            title=title,
            specs={str(k): str(v) for k, v in specs.items()},
            json_data=json_data,
            body_text=body_text,
        )
        image_urls = _filter_image_urls([str(x) for x in detail.get("image_urls", [])], limit=self.config.max_images)
        if not image_urls:
            print(
                {
                    "stage": "external_market_skip_no_images",
                    "market": self.config.market,
                    "source_listing_id": source_listing_id,
                },
                flush=True,
            )
            return None

        now = dt.datetime.now(dt.timezone.utc)
        raw_data = {
            "origin": "external_market",
            "market": self.config.market,
            "private_source_url": url,
            "raw_specs": specs,
            "image_count_found": len(image_urls),
            "json_blocks": json_data[:3],
        }
        checksum_payload = json.dumps({"url": url, "normalized": normalized, "images": image_urls}, ensure_ascii=False, default=str)
        return ScrapedListing(
            source_code=self.config.source_code,
            source_listing_id=source_listing_id,
            original_url=url,
            scraped_at=now,
            status="active",
            ad_hash=sha256_text(f"external_market|{self.config.market}|{source_listing_id}"),
            content_checksum=sha256_text(checksum_payload),
            normalized=normalized,
            originals=originals,
            raw_data=raw_data,
            image_urls=image_urls,
        )

    async def _collect_detail_payload(self, page: Page) -> dict[str, Any]:
        return await page.evaluate(
            r"""
() => {
  const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  const abs = (value) => {
    try { return new URL(value, location.href).href; } catch { return null; }
  };
  const h1 = clean((document.querySelector('h1') || {}).textContent || '');
  const ogTitle = clean((document.querySelector('meta[property="og:title"]') || {}).content || '');
  const imageUrls = [];
  for (const img of Array.from(document.querySelectorAll('img'))) {
    for (const attr of ['src', 'currentSrc', 'data-src', 'data-original', 'data-lazy', 'data-url']) {
      const value = attr === 'currentSrc' ? img.currentSrc : img.getAttribute(attr);
      const url = value ? abs(value) : null;
      if (url) imageUrls.push(url);
    }
  }
  for (const source of Array.from(document.querySelectorAll('source[srcset], img[srcset]'))) {
    const srcset = source.getAttribute('srcset') || '';
    for (const part of srcset.split(',')) {
      const url = abs(part.trim().split(/\s+/)[0]);
      if (url) imageUrls.push(url);
    }
  }
  for (const meta of Array.from(document.querySelectorAll('meta[property="og:image"], meta[name="twitter:image"]'))) {
    const url = abs(meta.getAttribute('content') || '');
    if (url) imageUrls.push(url);
  }
  const html = document.documentElement.innerHTML || '';
  const re = /https?:\/\/[^\s'"<>]+?\.(?:jpe?g|png|webp)(?:\?[^\s'"<>]*)?/ig;
  for (const match of html.matchAll(re)) imageUrls.push(match[0]);

  const specs = {};
  const addSpec = (label, value) => {
    label = clean(label);
    value = clean(value);
    if (!label || !value || label === value || label.length > 80 || value.length > 300) return;
    if (!(label in specs)) specs[label] = value;
  };
  for (const tr of Array.from(document.querySelectorAll('tr'))) {
    const cells = Array.from(tr.querySelectorAll('th,td')).map(el => clean(el.textContent));
    if (cells.length >= 2) addSpec(cells[0], cells.slice(1).join(' '));
  }
  for (const dl of Array.from(document.querySelectorAll('dl'))) {
    const dts = Array.from(dl.querySelectorAll('dt'));
    const dds = Array.from(dl.querySelectorAll('dd'));
    for (let i = 0; i < Math.min(dts.length, dds.length); i++) addSpec(dts[i].textContent, dds[i].textContent);
  }
  for (const el of Array.from(document.querySelectorAll('li, .spec, .spec-item, .param, .param-item, .characteristic, .info-item'))) {
    const txt = clean(el.textContent);
    const m = txt.match(/^([^:：]{2,40})[:：]\s*(.{1,240})$/);
    if (m) addSpec(m[1], m[2]);
  }

  const jsonData = [];
  for (const script of Array.from(document.querySelectorAll('script[type="application/ld+json"], script#__NEXT_DATA__, script#__NUXT_DATA__'))) {
    const text = script.textContent || '';
    if (text.length > 200000) continue;
    try { jsonData.push(JSON.parse(text)); } catch {}
  }
  return { h1, og_title: ogTitle, image_urls: Array.from(new Set(imageUrls)), specs, json_data: jsonData };
}
"""
        )
