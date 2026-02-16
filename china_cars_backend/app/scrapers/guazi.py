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
    _setup_page,
)
from app.utils.hashing import sha256_text
from app.utils.numbers import parse_mileage_km, parse_price_cny, parse_year
from app.utils.name_translation import BRAND_MAP, MODEL_MAP, has_chinese, normalize_by_dict


_DETAIL_RE = re.compile(
    r"(guazi\.com/.*/buy|guazi\.com/.*detail|/car-detail/c\d+\.html|/detail/|/products/[a-z0-9-]+\.html|\d+\.htm)",
    re.I,
)
_ID_RE = re.compile(r"(\d{9,})")
_EN_PRODUCT_RE = re.compile(r"/products/([a-z0-9-]+)\.html", re.I)
_RE_IMAGE_URL = re.compile(r"\.(jpe?g|png|webp)(\?|$)", re.I)
_RE_WEBP = re.compile(r"(\.webp(\?|$)|[?&]format=webp\b|\bwebp\b)", re.I)
_RE_NOT_IMAGE_URL = re.compile(r"\.(css|js|svg)(\?|$)", re.I)
_RE_MILEAGE = re.compile(r"(\d+(?:\.\d+)?)\s*万\s*公里")
_RE_MILEAGE_EN = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*km\b", re.I)
_RE_YEAR = re.compile(r"((?:19|20)\d{2})\s*款")
_RE_AGE = re.compile(r"(\d+)\s*年(?:\s*(\d+)\s*个?月)?")
_RE_PRICE = re.compile(r"(\d+(?:\.\d+)?)\s*万(?!\s*公里)")
_RE_MILEAGE_LABEL_EN = re.compile(r"mileage\s*\(km\)\s*[:：]?\s*(\d[\d,]*)", re.I)
_GZ_MAX_IMAGES = 10
_RE_EN_PRODUCT_LINK = re.compile(r"/products/[a-z0-9-]+\.html", re.I)
_RE_ENGINE_L = re.compile(r"(\d+(?:\.\d+)?)\s*(?:L|升)\b", re.I)
_RE_ENGINE_T = re.compile(r"(\d+(?:\.\d+)?)\s*T\b", re.I)
_RE_ENGINE_CC = re.compile(r"(\d{3,5})\s*(?:cc|CC|毫升|ml|mL)\b", re.I)
_RE_KW = re.compile(r"(\d+(?:\.\d+)?)\s*kW\b|千瓦", re.I)
_RE_KWH = re.compile(r"(\d+(?:\.\d+)?)\s*kWh\b|千瓦时", re.I)
_RE_ENGINE_MARKER = re.compile(r"(\d+(?:\.\d+)?\s*(?:L|T|升)|\d{3,5}\s*(?:cc|CC|毫升|ml|mL))")
_RE_ZH = re.compile(r"[\u4e00-\u9fff]")
_RE_ALLOWED_EN_RU = re.compile(r"[^0-9A-Za-zА-Яа-яЁё .,+()/_&-]+")
_PLACEHOLDER_PATTERNS = (
    "scan to open guazi",
    "used cars mini",
    "mini program",
    "qrcode",
    "qr code",
    "扫码",
    "小程序",
    "瓜子二手车小程序",
    "请扫码",
)

_MODEL_TOKEN_MAP: dict[str, str] = {
    "自动": "AT",
    "手动": "MT",
    "两驱": "2WD",
    "四驱": "4WD",
    "前驱": "FWD",
    "后驱": "RWD",
    "豪华版": "Luxury",
    "舒享版": "Comfort",
    "商务型": "Business",
    "经典型": "Classic",
    "旗舰型": "Flagship",
    "智惠型": "Smart",
    "智慧型": "Smart",
    "尊贵型": "Premium",
    "平行进口": "Import",
    "改款": "Facelift",
    "版": "Edition",
    "款": "",
    "国V": "China V",
    "国VI": "China VI",
    "中轴中顶": "Mid-Wheelbase Mid-Roof",
    "三排": "3-row",
    "标准版": "Standard",
}


def _filter_and_limit_guazi_image_urls(urls: list[str], *, limit: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        x = str(u or "").strip()
        if not x.startswith("http"):
            continue
        if _RE_NOT_IMAGE_URL.search(x):
            continue
        lx = x.lower()
        # Guazi часто отдаёт image URL без расширения, оставляем domain-based fallback.
        if not (_RE_IMAGE_URL.search(x) or _RE_WEBP.search(x)):
            if "guazi.com" not in lx and "cdn" not in lx and "img" not in lx:
                continue
        canon = x.split("#", 1)[0]
        if canon in seen:
            continue
        seen.add(canon)
        out.append(x)
        if len(out) >= limit:
            break
    return out


def _collect_guazi_dom(raw: dict[str, str]) -> dict[str, str | None]:
    title = str(raw.get("h1") or raw.get("title") or "").strip()
    price = str(raw.get("price") or "").strip()
    body = " ".join([str(v or "") for v in raw.values()])

    age = None
    m_age = _RE_AGE.search(body)
    if m_age:
        years = m_age.group(1)
        months = m_age.group(2) or "0"
        age = f"{years}年{months}个月"

    mileage = None
    m_mi_label = _RE_MILEAGE_LABEL_EN.search(body)
    if m_mi_label:
        mileage = f"{m_mi_label.group(1)} km"
    m_mi = _RE_MILEAGE.search(body)
    if not mileage and m_mi:
        mileage = f"{m_mi.group(1)}万公里"
    if not mileage:
        m_mi_en = _RE_MILEAGE_EN.search(body)
        if m_mi_en:
            mileage = f"{m_mi_en.group(1)} km"

    year = None
    m_y = _RE_YEAR.search(body)
    if m_y:
        year = f"{m_y.group(1)}款"

    if not price:
        m_p = _RE_PRICE.search(body)
        if m_p:
            price = f"{m_p.group(1)}万"
    if not price and "fob price" in body.lower():
        m_usd = re.search(r"fob\s*price\s*[:：]?\s*([$]?\s*\d[\d,]*(?:\.\d+)?)", body, flags=re.I)
        if m_usd:
            price = m_usd.group(1).strip()

    return {
        "title": title or None,
        "price": price or None,
        "mileage": mileage,
        "year": year,
        "age": age,
        "body": body or None,
    }


async def _collect_guazi_spec_items(page) -> list[dict[str, str]]:
    script = """
() => {
  const roots = Array.from(document.querySelectorAll(
    '.car-condition__functional-configuration .car-info-item, .car-condition_functional-configuration .car-info-item, .car-info .car-info-item, .vehicle-details-wrap .vehicle-details, .vehicie-details-wrap .vehicle-details'
  ));
  const out = [];
  for (const el of roots) {
    const lines = (el.innerText || '')
      .split(/\\n+/)
      .map(s => s.trim())
      .filter(Boolean);
    if (!lines.length) continue;
    let value = lines[0] || '';
    let label = lines.slice(1).join(' ') || '';
    // Иногда сначала лейбл, потом значение.
    if (/(续航|容量|类型|驱动|排量|发动机|燃料|能源|变速箱)/.test(value) && label) {
      const t = value;
      value = label;
      label = t;
    }
    out.push({ label, value, raw: lines.join(' | ') });
  }
  // Цена из отдельного виджета справа.
  const pVal = document.querySelector('.real-price .value');
  const pUnit = document.querySelector('.real-price .unit');
  if (pVal) {
    const v = (pVal.textContent || '').trim();
    const u = (pUnit && pUnit.textContent ? pUnit.textContent.trim() : '');
    out.push({ label: '价格', value: `${v}${u}`, raw: `${v}${u}` });
  }
  const fob = document.querySelector('.price-port .price');
  if (fob) {
    const txt = (fob.textContent || '').replace(/\\s+/g, ' ').trim();
    if (txt) {
      const clean = txt.replace(/\\s*Port\\s*:.*$/i, '').trim();
      out.push({ label: 'FOB Price', value: clean || txt, raw: txt });
    }
  }

  // Китайская карточка: сводная строка с оценкой/пробегом/возрастом и т.п.
  const condItems = Array.from(document.querySelectorAll('.car-condition-list .condition-item'));
  for (const el of condItems) {
    const txt = (el.textContent || '').replace(/\\s+/g, ' ').trim();
    if (!txt) continue;
    let label = 'condition';
    if (/万\\s*公里|km/i.test(txt)) label = '里程';
    else if (/年\\s*\\d*\\s*个?月|年/.test(txt)) label = '车龄';
    else if (/^[A-G]$/.test(txt)) label = '车况评级';
    else if (/^\\d+$/.test(txt)) label = '车况分';
    out.push({ label, value: txt, raw: txt });
  }

  const gridItems = Array.from(document.querySelectorAll('.vehicle-details-wrap .grid-layout .item, .vehicie-details-wrap .grid-layout .item'));
  for (const it of gridItems) {
    const k = ((it.querySelector('.label')?.textContent) || '').replace(/\\s+/g, ' ').trim();
    const v = ((it.querySelector('.value')?.textContent) || '').replace(/\\s+/g, ' ').trim();
    if (k && v) {
      out.push({ label: k, value: v, raw: `${k}: ${v}` });
    }
  }

  const detailsWrap = document.querySelector('.vehicle-details-wrap, .vehicie-details-wrap');
  if (detailsWrap) {
    const known = new Set([
      '1st Reg. Date','Mfg. Date','Model Year','Mileage(km)','Fuel Type','Engine','Transmission',
      'Steering','Location','Drive Train','Body Style','Seats','Doors','Exterior Color','Dimension(mm)','Curb Weight(kg)'
    ]);
    const lines = (detailsWrap.innerText || '')
      .split(/\\n+/)
      .map(s => s.replace(/\\s+/g, ' ').trim())
      .filter(Boolean);
    for (let i = 0; i < lines.length; i++) {
      const k = lines[i];
      if (!known.has(k)) continue;
      const v = lines[i + 1] || '';
      if (v) out.push({ label: k, value: v, raw: `${k}: ${v}` });
    }
  }

  // Доп. блоки характеристик (вкладки Specifications/Features).
  const extraRoots = Array.from(document.querySelectorAll('.base-info-wrap, .specifications-base-info-wrap, .features-wrap, .recomm-list, .vehicie-details-wrap'));
  for (const root of extraRoots) {
    const items = Array.from(root.querySelectorAll('.item, .list-item, li, .spec-item'));
    for (const it of items) {
      const k = (
        it.querySelector('.label, .name, .title, .key')?.textContent ||
        ''
      ).replace(/\\s+/g, ' ').trim();
      const v = (
        it.querySelector('.value, .desc, .text, .val')?.textContent ||
        ''
      ).replace(/\\s+/g, ' ').trim();
      if (k && v) out.push({ label: k, value: v, raw: `${k}: ${v}` });
    }
  }
  return out;
}
"""
    try:
        res = await page.evaluate(script)
        if isinstance(res, list):
            out: list[dict[str, str]] = []
            for it in res:
                if isinstance(it, dict):
                    out.append(
                        {
                            "label": str(it.get("label") or "").strip(),
                            "value": str(it.get("value") or "").strip(),
                            "raw": str(it.get("raw") or "").strip(),
                        }
                    )
            return out
    except Exception:
        pass
    return []


async def _collect_guazi_carousel_image_urls(page, *, limit: int) -> list[str]:
    script = """
() => {
  const out = [];
  const push = (u) => {
    if (!u || typeof u !== 'string') return;
    const s = u.trim();
    if (!/^https?:\\/\\//i.test(s)) return;
    out.push(s);
  };

  // Главная зона фото + вертикальные миниатюры.
  const roots = Array.from(document.querySelectorAll('.car-image-swiper-box, .swiper, .product-swiper-pagination-wrap, .vehicle-details'));
  for (const root of roots) {
    const imgs = Array.from(root.querySelectorAll('img'));
    for (const img of imgs) {
      push(img.currentSrc);
      push(img.src);
      push(img.getAttribute('data-src'));
      push(img.getAttribute('data-original'));
      push(img.getAttribute('data-lazy'));
      push(img.getAttribute('data-background'));
    }
    const slides = Array.from(root.querySelectorAll('.swiper-slide'));
    for (const el of slides) {
      push(el.getAttribute('data-src'));
      push(el.getAttribute('data-original'));
      push(el.getAttribute('data-url'));
      const style = (el.getAttribute('style') || '').trim();
      const m = style.match(/url\\((['"]?)(.*?)\\1\\)/i);
      if (m && m[2]) push(m[2]);
    }
  }

  const seen = new Set();
  const uniq = [];
  for (const u of out) {
    if (!u || seen.has(u)) continue;
    seen.add(u);
    uniq.push(u);
  }
  return uniq;
}
"""
    try:
        urls = await page.evaluate(script)
    except Exception:
        urls = []
    if not isinstance(urls, list):
        return []
    return _filter_and_limit_guazi_image_urls([str(x) for x in urls], limit=limit)


def _normalize_fuel(value: str | None) -> str | None:
    if not value:
        return None
    s = str(value).strip()
    ls = s.lower()

    # Явные EV-маркеры. Не используем голое "电动", т.к. оно часто про электропривод сидений/зеркал.
    if "纯电" in s or "电机" in s or "续航" in s or _RE_KW.search(s) or _RE_KWH.search(s) or "ev" in ls:
        return "Электро"
    if "插电" in s:
        return "Гибрид (PHEV)"
    if "增程" in s:
        return "Гибрид (EREV)"
    if "混动" in s or "混合" in s:
        return "Гибрид"
    if "汽油" in s:
        return "Бензин"
    if "柴油" in s:
        return "Дизель"
    if "gasoline" in ls or "petrol" in ls:
        return "Бензин"
    if "diesel" in ls:
        return "Дизель"
    if "hybrid" in ls:
        return "Гибрид"
    if "氢" in s:
        return "Водород"
    return None


def _infer_ice_fuel(value: str | None) -> str:
    s = str(value or "")
    if "柴油" in s:
        return "Дизель"
    if "汽油" in s:
        return "Бензин"
    return "Бензин/Дизель"


def _normalize_drive(value: str | None) -> str | None:
    if not value:
        return None
    s = str(value)
    if "四驱" in s or "四轮驱动" in s or "4WD" in s.upper() or "AWD" in s.upper():
        return "Полный"
    if "前驱" in s:
        return "Передний"
    if "后驱" in s:
        return "Задний"
    return None


def _parse_engine_volume_l(value: str | None) -> float | None:
    if not value:
        return None
    s = str(value)
    m_l = _RE_ENGINE_L.search(s)
    if m_l:
        try:
            v = float(m_l.group(1))
            if v < 0.6 or v > 10.0:
                return None
            return v
        except Exception:
            return None
    m_t = _RE_ENGINE_T.search(s)
    if m_t:
        try:
            v = float(m_t.group(1))
            if v < 0.6 or v > 10.0:
                return None
            return v
        except Exception:
            return None
    m_cc = _RE_ENGINE_CC.search(s)
    if m_cc:
        try:
            v = round(float(m_cc.group(1)) / 1000.0, 3)
            if v < 0.6 or v > 10.0:
                return None
            return v
        except Exception:
            return None
    return None


def _cleanup_en_ru_text(value: str | None) -> str | None:
    if not value:
        return None
    s = str(value)
    for zh, repl in _MODEL_TOKEN_MAP.items():
        s = s.replace(zh, f" {repl} ")
    s = _RE_ZH.sub(" ", s)
    s = _RE_ALLOWED_EN_RU.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip(" -_/")
    s = s.replace("( )", "").replace("  ", " ").strip()
    s = s.replace("Lynk Co", "Lynk & Co")
    return s or None


def _dedupe_prefix_words(text_value: str | None, prefixes: list[str]) -> str | None:
    if not text_value:
        return text_value
    s = str(text_value)
    for pref in prefixes:
        low = s.lower()
        p = pref.lower()
        if low.startswith(p + p):
            s = pref + s[len(pref) * 2 :]
        if low.startswith(p) and p in low[len(pref) + 1 :]:
            pos = low.find(p, len(pref) + 1)
            if pos != -1:
                s = s[:pos] + s[pos + len(pref) :]
    s = re.sub(r"\s+", " ", s).strip()
    if "T-ROCVolkswagen T-Roc" in s:
        s = s.replace("T-ROCVolkswagen T-Roc", "T-Roc")
    if s.startswith("V Import Vito"):
        s = s.replace("V Import Vito", "Vito Import", 1)
    return s or text_value


def _extract_tech_from_specs(spec_items: list[dict[str, str]], dom: dict[str, str | None]) -> dict[str, Any]:
    engine_type: str | None = None
    drive_type: str | None = None
    engine_volume_l: float | None = None
    price_text = dom.get("price")
    kw_marker = False
    all_text_parts: list[str] = []

    for it in spec_items:
        label = str(it.get("label") or "")
        value = str(it.get("value") or "")
        raw = str(it.get("raw") or "")
        combined = f"{label} {value} {raw}"
        all_text_parts.append(combined)
        if _RE_KW.search(combined) or _RE_KWH.search(combined):
            kw_marker = True

        if not price_text and (
            "价格" in combined
            or "万" in combined
            or "fob price" in combined.lower()
            or "$" in combined
        ):
            price_text = value or raw

        if engine_type is None and (
            "能源" in label
            or "燃料" in label
            or "动力" in label
            or "fuel" in label.lower()
        ):
            engine_type = _normalize_fuel(value or raw)
        if drive_type is None and (
            "驱动" in label
            or "驱动方式" in label
            or "drive" in label.lower()
        ):
            drive_type = _normalize_drive(value or raw)
        if engine_volume_l is None and (
            "排量" in label
            or "发动机" in label
            or "engine" in label.lower()
        ):
            engine_volume_l = _parse_engine_volume_l(value or raw)

    # fallback по общему тексту
    body = str(dom.get("body") or "")
    combined_all = " ".join(all_text_parts) + " " + body
    ls_all = combined_all.lower()
    if engine_type is None:
        engine_type = _normalize_fuel(combined_all)
    if drive_type is None:
        drive_type = _normalize_drive(body)
    if engine_volume_l is None:
        engine_volume_l = _parse_engine_volume_l(combined_all)

    is_ev_context = bool(
        ("纯电" in combined_all)
        or ("电动车" in combined_all)
        or ("续航" in combined_all)
        or ("ev" in ls_all)
        or _RE_KW.search(combined_all)
        or _RE_KWH.search(combined_all)
    )
    if is_ev_context:
        engine_type = "Электро"
        engine_volume_l = None

    # Правило консистентности:
    # 1) Если есть объем ДВС, тип топлива не может быть "Электро".
    # 2) Если есть kW/kWh и нет объема ДВС -> считаем "Электро".
    if engine_volume_l is not None and not is_ev_context:
        if engine_type == "Электро" or engine_type is None:
            engine_type = _infer_ice_fuel(combined_all)
    elif (kw_marker or is_ev_context) and engine_type is None:
        engine_type = "Электро"

    return {
        "engine_type": engine_type,
        "drive_type": drive_type,
        "engine_volume_l": engine_volume_l,
        "price_text": price_text,
    }


def _shift_year_month(now: dt.date, years: int, months: int) -> dt.date:
    total = now.year * 12 + now.month - 1
    total -= years * 12 + months
    y = total // 12
    m = total % 12 + 1
    return dt.date(y, m, 1)


def _parse_age_to_date(age_text: str | None) -> dt.date | None:
    if not age_text:
        return None
    m = _RE_AGE.search(str(age_text))
    if not m:
        return None
    years = int(m.group(1))
    months = int(m.group(2) or 0)
    return _shift_year_month(dt.date.today(), years, months)


def _parse_price_cny(price_text: str | None) -> float | None:
    return parse_price_cny(price_text)


def _extract_links(anchors: list[dict[str, str]], limit: int) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[str] = set()

    for a in anchors:
        href = str(a.get("href") or "").strip()
        if href.startswith("/"):
            href = f"https://www.guazi.com{href}"
        if href.startswith("//"):
            href = "https:" + href
        if not href.startswith("http"):
            continue
        if "guazi.com" not in href:
            continue
        if not _DETAIL_RE.search(href):
            continue

        m = _ID_RE.search(href)
        if m:
            listing_id = m.group(1)
        else:
            m_en = _EN_PRODUCT_RE.search(href)
            listing_id = m_en.group(1) if m_en else sha256_text(href)[:20]
        if listing_id.isdigit() and len(listing_id) < 12:
            continue
        if listing_id in seen:
            continue
        seen.add(listing_id)
        out.append((listing_id, href))
        if len(out) >= limit:
            break

    return out


def _extract_product_links_from_text(text: str, *, limit: int) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for m in _RE_EN_PRODUCT_LINK.finditer(text or ""):
        path = m.group(0)
        listing_id = path.split("/")[-1].replace(".html", "")
        if not listing_id or listing_id in seen:
            continue
        seen.add(listing_id)
        out.append((listing_id, f"https://en.guazi.com{path}"))
        if len(out) >= limit:
            break
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
            if "guazi.com" not in lx and "cdn" not in lx and "img" not in lx:
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
    return _filter_and_limit_guazi_image_urls(urls, limit=limit)


def _extract_brand_model_by_brand_dict(title_text: str) -> tuple[str | None, str | None]:
    title = str(title_text or "").strip()
    if not title:
        return None, None
    # Приоритет длинных ключей (например "小米汽车" раньше "小米")
    for zh_brand in sorted(BRAND_MAP.keys(), key=len, reverse=True):
        if not zh_brand:
            continue
        idx = title.find(zh_brand)
        if idx < 0:
            continue
        before = title[:idx].strip()
        after = title[idx + len(zh_brand) :].strip()
        # Если бренд найден внутри слова с латиницей, пропускаем.
        if before and re.search(r"[A-Za-z0-9]$", before):
            continue
        model = after or None
        return zh_brand, model
    return None, None


def _normalize_from_dom(dom: dict[str, str | None], *, spec_items: list[dict[str, str]] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    title = str(dom.get("title") or dom.get("h1") or "").strip()
    clean = re.sub(r"\s+", " ", title)
    clean = re.sub(r"[|｜丨].*$", "", clean).strip()

    # Пробуем вытащить пробег/год из всего доступного текста, не только title.
    mileage_src = str(dom.get("mileage") or "")
    year_src = str(dom.get("year") or "")
    if not mileage_src:
        for v in dom.values():
            s = str(v or "")
            if _RE_MILEAGE.search(s):
                mileage_src = s
                break
    if not year_src:
        for v in dom.values():
            s = str(v or "")
            if _RE_YEAR.search(s):
                year_src = s
                break

    # Обрезаем в названии служебные хвосты, чтобы не попадали в brand/model.
    clean_no_specs = re.sub(r"(\d+(?:\.\d+)?\s*万\s*公里)", "", clean)
    clean_no_specs = re.sub(r"((?:19|20)\d{2}\s*款)", "", clean_no_specs).strip()
    clean_no_specs = re.sub(r"^Used\s+", "", clean_no_specs, flags=re.I).strip()

    parts = [p for p in re.split(r"\s+", clean_no_specs) if p]
    brand_raw = parts[0] if parts else None
    model_raw = " ".join(parts[1:]) if len(parts) > 1 else None

    # Для китайского заголовка часто нет адекватного split по пробелам — используем словарь брендов.
    if has_chinese(clean_no_specs):
        b_guess, m_guess = _extract_brand_model_by_brand_dict(clean_no_specs)
        if b_guess:
            brand_raw = b_guess
            if m_guess:
                model_raw = m_guess

    # Случаи вида "BMW2系" / "Mercedes-BenzV级（平行进口）".
    if isinstance(brand_raw, str):
        m_compact = re.match(r"^([A-Za-z][A-Za-z0-9& .+\-]*?)([\u4e00-\u9fff].*)$", brand_raw)
        if m_compact:
            b_en = m_compact.group(1).strip()
            b_tail = m_compact.group(2).strip()
            brand_raw = b_en
            model_raw = f"{b_tail} {model_raw or ''}".strip()

    brand = normalize_by_dict(brand_raw, BRAND_MAP) if brand_raw else brand_raw
    model = normalize_by_dict(model_raw, MODEL_MAP) if model_raw else model_raw
    if isinstance(brand, str):
        known_prefixes = [
            "Mercedes-Benz",
            "Land Rover",
            "Xiaomi Auto",
            "Rolls-Royce",
            "Volkswagen",
            "Cadillac",
            "Porsche",
            "Toyota",
            "Nissan",
            "Honda",
            "Tesla",
            "Ford",
            "Buick",
            "Kia",
            "Mazda",
            "Changan",
            "Haval",
            "Geely",
            "JAC",
            "Lincoln",
            "Skoda",
            "BMW",
            "Audi",
        ]
        for pref in known_prefixes:
            if brand.startswith(pref) and len(brand) > len(pref):
                tail = brand[len(pref) :].strip()
                if tail:
                    brand = pref
                    model = f"{tail} {model or ''}".strip()
                break
    # Случаи после словаря: "BMW2系", "Mercedes-BenzV级（平行进口）"
    if isinstance(brand, str):
        m = re.match(r"^([A-Za-z][A-Za-z0-9& .+\-]{1,32}?)([\u4e00-\u9fff0-9].*)$", brand)
        if m:
            b_head = m.group(1).strip()
            b_tail = m.group(2).strip()
            brand = b_head
            model = f"{b_tail} {model or ''}".strip()
        # Точечная нормализация "Mercedes-BenzV..."
        m_mb = re.match(r"^(Mercedes-Benz)([A-Za-z])$", brand)
        if m_mb:
            brand = m_mb.group(1)
            model = f"{m_mb.group(2)} {model or ''}".strip()
    if isinstance(brand, str) and not has_chinese(brand):
        brand = _cleanup_en_ru_text(brand) or brand
    if isinstance(model, str) and not has_chinese(model):
        model = _cleanup_en_ru_text(model) or model
    brand = _dedupe_prefix_words(brand, ["Volkswagen", "Skoda", "Kia", "JAC", "Mazda", "BMW", "Mercedes-Benz"])
    model = _dedupe_prefix_words(model, ["Volkswagen", "Skoda", "Kia", "JAC", "Mazda", "BMW", "Mercedes-Benz"])
    if isinstance(model, str) and isinstance(brand, str):
        if model.lower().startswith(brand.lower() + " "):
            model = model[len(brand) :].strip()
    if isinstance(model, str):
        parts_model = model.split()
        if len(parts_model) >= 2:
            t0 = re.sub(r"[^A-Za-z0-9-]+", "", parts_model[0]).lower()
            t1 = re.sub(r"[^A-Za-z0-9-]+", "", parts_model[1]).lower()
            if t0 and t0 == t1:
                parts_model = [parts_model[0]] + parts_model[2:]
                model = " ".join(parts_model)
        if len(parts_model) >= 2 and parts_model[0].lower() == parts_model[1].lower():
            model = " ".join(parts_model[1:])
        prev = None
        while prev != model:
            prev = model
            model = re.sub(r"\b([A-Za-z0-9-]{2,})\b\s+\1\b", r"\1", model, flags=re.I)
        model = re.sub(r"^([A-Za-z0-9-]+)\s+\1\b", r"\1", model, flags=re.I)
        model = re.sub(r"\b(19|20)\d{2}\b", "", model).strip()
        model = re.sub(r"\s{2,}", " ", model).strip() or None

    tech = _extract_tech_from_specs(spec_items or [], dom)

    normalized: dict[str, Any] = {
        "brand": brand,
        "model": model,
        "year": parse_year(year_src or clean),
        "mileage_km": parse_mileage_km(mileage_src),
        "price_cny": _parse_price_cny(tech.get("price_text") or dom.get("price")),
        "engine_type": tech.get("engine_type"),
        "drive_type": tech.get("drive_type"),
        "engine_volume_l": tech.get("engine_volume_l"),
    }
    if isinstance(normalized.get("model"), str):
        mtxt = str(normalized["model"])
        prev = None
        while prev != mtxt:
            prev = mtxt
            mtxt = re.sub(r"\b([A-Za-z0-9-]{2,})\b\s+\1\b", r"\1", mtxt, flags=re.I)
        normalized["model"] = re.sub(r"\s{2,}", " ", mtxt).strip() or None
    if normalized.get("engine_volume_l") is None and _RE_ENGINE_MARKER.search(clean):
        normalized["engine_volume_l"] = _parse_engine_volume_l(clean)
    reg_date = _parse_age_to_date(dom.get("age"))
    if reg_date:
        normalized["first_registration_date"] = reg_date
        if not normalized.get("year"):
            normalized["year"] = reg_date.year
    return normalized, {}


def _is_placeholder_listing(*, normalized: dict[str, Any], dom: dict[str, str | None], spec_items: list[dict[str, str]] | None = None) -> bool:
    parts = [
        str(dom.get("title") or ""),
        str(dom.get("body") or ""),
        str(dom.get("body_text") or ""),
    ]
    if spec_items:
        for it in spec_items:
            parts.append(str(it.get("label") or ""))
            parts.append(str(it.get("value") or ""))
            parts.append(str(it.get("raw") or ""))
    haystack = " ".join(parts).lower()
    has_placeholder_pattern = any(p in haystack for p in _PLACEHOLDER_PATTERNS)

    brand = str(normalized.get("brand") or "").strip().lower()
    model = str(normalized.get("model") or "").strip().lower()
    year = normalized.get("year")
    mileage = normalized.get("mileage_km")
    price = normalized.get("price_cny")
    try:
        mileage_num = float(mileage) if mileage is not None else None
    except Exception:
        mileage_num = None
    try:
        price_num = float(price) if price is not None else None
    except Exception:
        price_num = None

    strong_data = bool(
        brand
        and model
        and (
            year is not None
            or (mileage_num is not None and mileage_num > 0)
            or (price_num is not None and price_num > 0)
        )
    )

    if ("scan to open" in brand or "scan to open" in model) or ("mini" in brand and "guazi" in brand):
        return True
    if has_placeholder_pattern and not strong_data:
        return True

    very_weak_card = (
        (not brand or not model)
        and (year is None)
        and (mileage_num is None or mileage_num <= 0)
        and (price_num is None or price_num <= 0)
    )
    return bool(very_weak_card)


class GuaziScraper(BaseScraper):
    source_code = "guazi"

    def __init__(self, *, max_images: int = 16) -> None:
        self.max_images = max(0, min(int(max_images), _GZ_MAX_IMAGES))

    async def scrape(self, limit: int) -> list[ScrapedListing]:
        if limit <= 0:
            return []

        start_url = "https://www.guazi.com/"
        scraped: list[ScrapedListing] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await _setup_page(browser)
            page.set_default_navigation_timeout(120_000)
            page.set_default_timeout(120_000)

            opened = False
            nav_errors: list[str] = []
            for attempt, wait_until in enumerate(("domcontentloaded", "commit", "load"), start=1):
                try:
                    await page.goto(start_url, wait_until=wait_until, timeout=95_000)
                    await asyncio.sleep(2.2 + 0.6 * attempt)
                    opened = True
                    break
                except Exception as exc:
                    nav_errors.append(f"attempt={attempt} wait_until={wait_until} err={exc}")
                    await asyncio.sleep(1.5 * attempt)
            if not opened:
                print({"stage": "list_open_failed", "source": self.source_code, "start_url": start_url, "errors": nav_errors})
                await page.context.close()
                await browser.close()
                return []

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
            seen_ids: set[str] = set()
            scan_limit = max(limit * 4, limit + 30)
            for _ in range(40):
                anchors = await page.evaluate(
                    """
() => Array.from(document.querySelectorAll("a")).map(a => ({ href: a.href || "" }))
"""
                )
                batch = _extract_links(anchors, limit=scan_limit)
                for iid, href in batch:
                    if iid in seen_ids:
                        continue
                    seen_ids.add(iid)
                    found.append((iid, href))
                    if len(found) >= scan_limit:
                        break
                if len(found) >= scan_limit:
                    break
                await page.mouse.wheel(0, 1800)
                await asyncio.sleep(1.0 + random.random() * 0.7)

            # Fallback: ссылки могут быть спрятаны в HTML/скриптах Next.js.
            if len(found) < scan_limit:
                try:
                    html = await page.content()
                    for iid, href in _extract_product_links_from_text(html, limit=scan_limit):
                        if iid in seen_ids:
                            continue
                        seen_ids.add(iid)
                        found.append((iid, href))
                        if len(found) >= scan_limit:
                            break
                except Exception:
                    pass

            if len(found) < scan_limit and list_json:
                seen = {x[0] for x in found}
                for js in list_json:
                    blob = json.dumps(js, ensure_ascii=False, default=str)
                    for m in _ID_RE.finditer(blob):
                        iid = m.group(1)
                        if iid in seen:
                            continue
                        seen.add(iid)
                        found.append((iid, f"https://www.guazi.com/car-detail/c{iid}.html"))
                        if len(found) >= scan_limit:
                            break
                    if len(found) >= scan_limit:
                        break
                    for m_en in re.finditer(r"/products/[a-z0-9-]+\.html", blob, flags=re.I):
                        p = m_en.group(0)
                        href = f"https://en.guazi.com{p}"
                        iid = p.split("/")[-1].replace(".html", "")
                        if iid in seen:
                            continue
                        seen.add(iid)
                        found.append((iid, href))
                        if len(found) >= scan_limit:
                            break
                    if len(found) >= scan_limit:
                        break

            if not found:
                print({"stage": "no_listing_links_found", "source": self.source_code, "start_url": start_url})

            page.remove_listener("response", on_list_response)

            for idx, (listing_id, detail_url) in enumerate(found, start=1):
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

                dom_snapshot = _collect_guazi_dom(_extract_texts_from_dom(await _collect_dom_snapshot(page)))
                try:
                    body_text = await page.evaluate("() => (document.body && document.body.innerText) ? document.body.innerText : ''")
                    if isinstance(body_text, str) and body_text.strip():
                        dom_snapshot["body_text"] = body_text
                        dom_snapshot = _collect_guazi_dom(dom_snapshot)
                except Exception:
                    pass
                spec_items = await _collect_guazi_spec_items(page)
                raw = {"detail_url": detail_url, "responses": response_jsons, "dom": dom_snapshot, "spec_items": spec_items}
                normalized, originals = _normalize_from_dom(dom_snapshot, spec_items=spec_items)
                if _is_placeholder_listing(normalized=normalized, dom=dom_snapshot, spec_items=spec_items):
                    continue

                image_urls = await _collect_guazi_carousel_image_urls(page, limit=self.max_images)
                if not image_urls:
                    image_urls = _extract_image_urls_from_raw(raw, limit=self.max_images)
                if not image_urls:
                    image_urls = await _collect_image_urls(page, limit=self.max_images)
                image_urls = _filter_and_limit_guazi_image_urls(image_urls, limit=self.max_images)

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

                if len(scraped) >= limit:
                    break
                await asyncio.sleep(1.0 + random.random() * 0.6)

            await page.context.close()
            await browser.close()

        return scraped
