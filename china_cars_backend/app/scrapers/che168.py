from __future__ import annotations

import asyncio
import datetime as dt
import json
import random
import re
from typing import Any

from playwright.async_api import Browser, Page, async_playwright

from app.scrapers.base import BaseScraper, ScrapedListing
from app.utils.hashing import sha256_text
from app.utils.numbers import parse_mileage_km, parse_year


_UAS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]


_RE_WEBP = re.compile(r"(\.webp(\?|$)|[?&]format=webp\b|\bwebp\b)", re.I)
_RE_IMAGE_URL = re.compile(r"\.(jpe?g|png|webp)(\?|$)", re.I)
_RE_NOT_IMAGE_URL = re.compile(r"\.(css|js|svg)(\?|$)", re.I)

_DEFAULT_MAX_IMAGES = 16


def _canonical_url(u: str) -> str:
    return u.split("#", 1)[0]


def _filter_and_limit_image_urls(urls: list[str], *, limit: int = _DEFAULT_MAX_IMAGES) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    ordered = sorted(urls, key=lambda s: (0 if isinstance(s, str) and "autoimg" in s else 1))
    for u in ordered:
        if not u:
            continue
        x = str(u).strip()
        if not x:
            continue
        if not x.startswith("http"):
            continue
        if _RE_NOT_IMAGE_URL.search(x):
            continue
        if "data:image" in x.lower():
            continue
        if any(bad in x.lower() for bad in ("/logo", "icon", "sprite", "loading")):
            continue
        if not (_RE_IMAGE_URL.search(x) or _RE_WEBP.search(x)):
            if "autoimg" not in x and "che168" not in x:
                continue
        canon = _canonical_url(x)
        if canon in seen:
            continue
        seen.add(canon)
        out.append(x)
        if len(out) >= limit:
            break
    return out


def _to_str(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        try:
            return json.dumps(v, ensure_ascii=False, default=str)
        except Exception:
            return str(v)
    s = str(v).strip()
    return s or None


def _to_int(v: Any) -> int | None:
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
    except ValueError:
        return None


def _pick_first(d: Any, keys: list[str]) -> Any:
    if isinstance(d, dict):
        for k in keys:
            if k in d and d[k] not in (None, ""):
                return d[k]
        for v in d.values():
            r = _pick_first(v, keys)
            if r not in (None, ""):
                return r
    elif isinstance(d, list):
        for it in d:
            r = _pick_first(it, keys)
            if r not in (None, ""):
                return r
    return None


def _extract_texts_from_dom(snapshot: dict[str, str]) -> dict[str, str | None]:
    title = snapshot.get("h1") or snapshot.get("title")
    price = snapshot.get("price")
    mileage = snapshot.get("mileage")
    year = snapshot.get("year")
    city = snapshot.get("city")
    return {
        "title": title,
        "price": price,
        "mileage": mileage,
        "year": year,
        "city": city,
    }


def _normalize_from_raw(raw: dict[str, Any], dom: dict[str, str | None]) -> tuple[dict[str, Any], dict[str, Any]]:
    mileage_text = dom.get("mileage") or _pick_first(raw, ["mileage", "mileageText", "miles", "kilometer", "kilometerText", "runKm"]) 
    year_text = dom.get("year") or _pick_first(raw, ["year", "regYear", "carYear", "licenseYear"]) 

    title = dom.get("title")
    brand = _pick_first(
        raw,
        [
            "brandSpell",
            "brandEn",
            "brandEN",
            "brandEnglish",
            "brandNameEn",
            "brandNameEN",
            "brandEName",
            "brandEnName",
            "brandEngName",
            "brandName",
            "brand",
            "brandname",
        ],
    )
    model = _pick_first(
        raw,
        [
            "seriesSpell",
            "seriesEn",
            "seriesEN",
            "seriesEnglish",
            "seriesNameEn",
            "modelSpell",
            "modelEn",
            "modelEN",
            "modelEnglish",
            "modelNameEn",
            "seriesName",
            "modelName",
            "series",
            "model",
            "specName",
        ],
    )

    year_src = str(year_text) if year_text else (str(title) if title else None)
    mileage_src = str(mileage_text) if mileage_text else (str(title) if title else None)

    normalized: dict[str, Any] = {
        "brand": _to_str(brand),
        "model": _to_str(model),
        "year": parse_year(year_src) if year_src else None,
        "mileage_km": parse_mileage_km(mileage_src) if mileage_src else None,
    }

    originals: dict[str, Any] = {}

    return normalized, originals


def _extract_listing_links(anchors: list[dict[str, str]]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[str] = set()

    for a in anchors:
        href = a.get("href") or ""
        if not href:
            continue
        if "cardetail/index" not in href:
            continue
        m = re.search(r"[?&]infoid=(\d+)", href)
        if not m:
            continue
        infoid = m.group(1)
        if infoid in seen:
            continue
        seen.add(infoid)
        out.append((infoid, href))

    return out


def _extract_infoids_from_json(data: Any) -> list[str]:
    out: list[str] = []

    def walk(x: Any):
        if isinstance(x, dict):
            for k, v in x.items():
                lk = str(k).lower()
                if lk in ("infoid", "info_id", "infoidstr"):
                    if isinstance(v, int):
                        out.append(str(v))
                    elif isinstance(v, str) and v.isdigit():
                        out.append(v)
                walk(v)
            return
        if isinstance(x, list):
            for it in x:
                walk(it)

    walk(data)

    seen: set[str] = set()
    uniq: list[str] = []
    for v in out:
        if v in seen:
            continue
        seen.add(v)
        uniq.append(v)
    return uniq


async def _collect_dom_snapshot(page: Page) -> dict[str, str]:
    script = """
() => {
  const text = (el) => (el && el.textContent ? el.textContent.trim() : '');
  const pick = (selectors) => {
    for (const s of selectors) {
      const el = document.querySelector(s);
      const t = text(el);
      if (t) return t;
    }
    return '';
  };
  const bodyText = (document.body && document.body.innerText ? document.body.innerText : '');

  const yearFromText = (() => {
    const m = bodyText.match(/(19\d{2}|20\d{2})\s*款/);
    if (m && m[1]) return `${m[1]}款`;
    return '';
  })();

  const mileageFromText = (() => {
    const m = bodyText.match(/(\d+(?:\.\d+)?)\s*万\s*公里/);
    if (m && m[1]) return `${m[1]}万公里`;
    return '';
  })();
  return {
    title: document.title || '',
    h1: pick(['h1', '[class*=title]', '[data-testid*=title]']),
    price: pick(['[class*=price]', '[data-testid*=price]']),
    mileage: mileageFromText || pick(['[class*=mileage]', '[class*=kilometer]', '[class*=km]']),
    year: yearFromText || pick(['[class*=year]', '[data-testid*=year]']),
    city: pick(['[class*=city]', '[data-testid*=city]']),
  };
}
"""
    return await page.evaluate(script)


async def _collect_image_urls(page: Page, *, limit: int) -> list[str]:
    script = """
() => {
  const urls = [];
  const push = (u) => {
    if (!u) return;
    if (typeof u !== 'string') return;
    if (!/^https?:\/\//i.test(u)) return;
    urls.push(u);
  };

  const imgs = Array.from(document.querySelectorAll('img'));
  for (const img of imgs) {
    const w = Number(img.naturalWidth || 0);
    const h = Number(img.naturalHeight || 0);
    if (w > 0 && h > 0 && (w * h) < 60000) continue;
    push(img.currentSrc);
    push(img.src);
    push(img.getAttribute('data-src'));
    push(img.getAttribute('data-original'));
  }

  const nodes = Array.from(document.querySelectorAll('[style]'));
  for (const el of nodes) {
    const s = (el.getAttribute('style') || '').trim();
    const m = s.match(/url\((['"]?)(.*?)\1\)/i);
    if (m && m[2]) push(m[2]);
  }

  const seen = new Set();
  const out = [];
  for (const u of urls) {
    const x = u.trim();
    if (!x) continue;
    if (seen.has(x)) continue;
    seen.add(x);
    out.push(x);
  }
  return out;
}
"""
    urls: list[str] = await page.evaluate(script)
    return _filter_and_limit_image_urls(urls, limit=limit)


def _extract_image_urls_from_raw(raw: dict[str, Any], *, limit: int) -> list[str]:
    preferred_keys = {
        "imgList",
        "imageList",
        "images",
        "picList",
        "photoList",
        "photos",
    }

    urls: list[str] = []

    def add(u: str):
        if not u:
            return
        x = str(u).strip()
        if not x.startswith("http"):
            return
        if not (_RE_IMAGE_URL.search(x) or _RE_WEBP.search(x)):
            if "autoimg" not in x and "che168" not in x:
                return
        urls.append(x)

    url_keys = ["url", "imgUrl", "imageUrl", "bigUrl", "originalUrl", "src", "path"]

    def walk(x: Any):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in preferred_keys and isinstance(v, list):
                    for it in v:
                        if isinstance(it, str):
                            add(it)
                            continue
                        if isinstance(it, dict):
                            for uk in url_keys:
                                u = it.get(uk)
                                if isinstance(u, str) and u:
                                    add(u)
                                    break
                            continue
                        walk(it)
                else:
                    walk(v)
            return
        if isinstance(x, list):
            for it in x:
                walk(it)

    walk(raw.get("responses") or [])
    return _filter_and_limit_image_urls(urls, limit=limit)


async def _setup_page(browser: Browser) -> Page:
    ctx = await browser.new_context(
        user_agent=random.choice(_UAS),
        locale="zh-CN",
        viewport={"width": 390, "height": 844},
    )

    await ctx.route(
        "**/*",
        lambda route: route.abort()
        if route.request.resource_type in ("font", "media")
        else route.continue_(),
    )

    page = await ctx.new_page()
    page.set_default_timeout(45_000)
    return page


class Che168Scraper(BaseScraper):
    source_code = "che168"

    def __init__(self, *, max_images: int = _DEFAULT_MAX_IMAGES) -> None:
        self.max_images = max(0, int(max_images))

    async def scrape(self, limit: int) -> list[ScrapedListing]:
        if limit <= 0:
            return []

        start_url = "https://m.che168.com/china/list/"
        scraped: list[ScrapedListing] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await _setup_page(browser)

            await page.goto(start_url, wait_until="domcontentloaded")
            await asyncio.sleep(2.0)

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

            try:
                await page.wait_for_function(
                    """
() => Array.from(document.querySelectorAll('a')).some(a => (a.href || '').includes('infoid='))
""",
                    timeout=30_000,
                )
            except Exception:
                pass

            found: list[tuple[str, str]] = []
            for _ in range(40):
                anchors = await page.evaluate(
                    """
() => Array.from(document.querySelectorAll('a')).map(a => ({href: a.href || ''}))
"""
                )
                found = _extract_listing_links(anchors)
                if len(found) >= limit:
                    break
                await page.mouse.wheel(0, 1800)
                await asyncio.sleep(1.2)

            if len(found) < limit and list_json:
                infoids: list[str] = []
                for js in list_json:
                    infoids.extend(_extract_infoids_from_json(js))

                seen = {x[0] for x in found}
                for iid in infoids:
                    if iid in seen:
                        continue
                    seen.add(iid)
                    found.append((iid, f"https://m.che168.com/cardetail/index?infoid={iid}"))
                    if len(found) >= limit:
                        break

            page.remove_listener("response", on_list_response)

            found = found[:limit]

            for idx, (infoid, href) in enumerate(found, start=1):
                detail_url = href if href.startswith("http") else f"https://m.che168.com/cardetail/index?infoid={infoid}"

                response_jsons: list[dict[str, Any]] = []

                async def on_response(resp):
                    try:
                        ct = (resp.headers.get("content-type") or "").lower()
                        if "application/json" not in ct:
                            return
                        js = await resp.json()
                        if isinstance(js, dict):
                            response_jsons.append(js)
                    except Exception:
                        return

                page.on("response", on_response)
                try:
                    await page.goto(detail_url, wait_until="domcontentloaded")
                    await asyncio.sleep(2.0)
                finally:
                    page.remove_listener("response", on_response)

                dom_snapshot = _extract_texts_from_dom(await _collect_dom_snapshot(page))

                raw: dict[str, Any] = {
                    "detail_url": detail_url,
                    "responses": response_jsons,
                    "dom": dom_snapshot,
                }

                normalized, originals = _normalize_from_raw(raw, dom_snapshot)
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
                        source_listing_id=str(infoid),
                        original_url=detail_url,
                        scraped_at=dt.datetime.now(dt.timezone.utc),
                        status="active",
                        ad_hash=sha256_text(f"{self.source_code}:{infoid}"),
                        content_checksum=content_checksum,
                        normalized=normalized,
                        originals=originals,
                        raw_data=raw,
                        image_urls=image_urls,
                    )
                )

                await asyncio.sleep(1.0 + random.random() * 0.8)

                if idx >= limit:
                    break

            await page.context.close()
            await browser.close()

        return scraped
