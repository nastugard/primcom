from __future__ import annotations

import asyncio
import dataclasses
import logging
import os
import re
import shlex
import subprocess

from app.core import settings


logger = logging.getLogger(__name__)

_COUNTRY_GENITIVE = {"japan": "Японии", "china": "Китая", "korea": "Кореи"}
_TRANSLITERATION = str.maketrans(
    {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
)


@dataclasses.dataclass(frozen=True)
class SeoEligibility:
    eligible: bool
    url: str | None
    reason: str | None


@dataclasses.dataclass(frozen=True)
class SeoPublishResult:
    ok: bool
    reason: str | None = None


def seo_slug(value: object) -> str:
    text = str(value or "").strip().lower().translate(_TRANSLITERATION)
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:80]


def seo_model_url(*, market: str, brand: object, model: object) -> str | None:
    clean_market = str(market or "").strip().lower()
    make_slug = seo_slug(brand)
    model_slug = seo_slug(model)
    if clean_market not in _COUNTRY_GENITIVE or not make_slug or not model_slug:
        return None
    return f"/cars/{clean_market}/{make_slug}/{model_slug}/"


def evaluate_listing_for_seo(
    *,
    market: str,
    brand: object,
    model: object,
    year: object,
    price: object,
    images_count: int,
) -> SeoEligibility:
    missing: list[str] = []
    clean_market = str(market or "").strip().lower()
    make_slug = seo_slug(brand)
    model_slug = seo_slug(model)
    if clean_market not in _COUNTRY_GENITIVE:
        missing.append("страна")
    if not make_slug:
        missing.append("марка")
    if not model_slug:
        missing.append("модель")
    try:
        valid_year = 1980 <= int(year) <= 2100
    except (TypeError, ValueError):
        valid_year = False
    if not valid_year:
        missing.append("год")
    try:
        valid_price = float(price) > 0
    except (TypeError, ValueError):
        valid_price = False
    if not valid_price:
        missing.append("цена")
    if int(images_count or 0) <= 0:
        missing.append("фотография")

    url = seo_model_url(market=clean_market, brand=brand, model=model)
    if missing:
        return SeoEligibility(False, url, "Для SEO-страницы не хватает: " + ", ".join(missing) + ".")
    return SeoEligibility(True, url, None)


def _run_publish_command() -> SeoPublishResult:
    raw_command = str(settings.seo_publish_command or "").strip()
    if not raw_command:
        return SeoPublishResult(False, "Автопубликация SEO не настроена на сервере.")
    command = shlex.split(raw_command)
    if not command:
        return SeoPublishResult(False, "Команда SEO-публикации пуста.")
    process_env = os.environ.copy()
    if settings.primcom_site_root:
        process_env["PRIMCOM_SITE_ROOT"] = str(settings.primcom_site_root)
    try:
        completed = subprocess.run(
            command,
            cwd=str(settings.seo_publish_workdir or "."),
            env=process_env,
            capture_output=True,
            text=True,
            timeout=max(5, int(settings.seo_publish_timeout_seconds or 90)),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.exception("seo_publish_command_failed")
        return SeoPublishResult(False, f"SEO-сборка не запустилась: {exc.__class__.__name__}.")
    if completed.returncode != 0:
        logger.error(
            "seo_publish_failed returncode=%s stdout=%s stderr=%s",
            completed.returncode,
            completed.stdout[-1200:],
            completed.stderr[-1200:],
        )
        return SeoPublishResult(False, "SEO-сборка завершилась ошибкой; рабочие страницы не изменены.")
    logger.info("seo_publish_completed stdout=%s", completed.stdout[-1200:])
    return SeoPublishResult(True)


async def publish_catalog_seo() -> SeoPublishResult:
    return await asyncio.to_thread(_run_publish_command)
