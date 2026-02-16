from __future__ import annotations

import re
from dataclasses import dataclass

from app.scrapers.base import BaseScraper, ScrapedListing
from app.scrapers.che168 import Che168Scraper
from app.scrapers.dongchedi import DongchediScraper
from app.scrapers.guazi import GuaziScraper


_PLACEHOLDER_PATTERNS = (
    "scan to open",
    "used cars mini",
    "mini program",
    "qrcode",
    "qr code",
    "扫码",
    "小程序",
    "瓜子二手车小程序",
    "请扫码",
)


@dataclass
class LegacySourceAdapter:
    scraper: BaseScraper

    @property
    def source_code(self) -> str:
        return self.scraper.source_code

    async def scrape(self, *, limit: int) -> list[ScrapedListing]:
        return await self.scraper.scrape(limit=limit)

    def detect_placeholder(self, listing: ScrapedListing) -> bool:
        normalized = listing.normalized or {}
        raw_data = listing.raw_data or {}

        brand = str(normalized.get("brand") or "").strip().lower()
        model = str(normalized.get("model") or "").strip().lower()
        year = normalized.get("year")
        mileage = normalized.get("mileage_km")
        price = normalized.get("price_cny")

        text_parts = [
            str(brand),
            str(model),
            str(raw_data.get("dom") or ""),
            str(raw_data.get("spec_items") or ""),
            str(raw_data.get("responses") or "")[:1500],
        ]
        haystack = " ".join(text_parts).lower()
        if any(p in haystack for p in _PLACEHOLDER_PATTERNS):
            return True

        if "scan to open" in brand or "scan to open" in model:
            return True

        def _num(v):
            try:
                return float(v)
            except Exception:
                return None

        mileage_num = _num(mileage)
        price_num = _num(price)
        weak = (
            (not brand or not model)
            and (year is None)
            and (mileage_num is None or mileage_num <= 0)
            and (price_num is None or price_num <= 0)
        )
        return bool(weak)


def create_adapter(source: str, *, max_images: int) -> LegacySourceAdapter:
    code = str(source or "").strip().lower()
    if code == "che168":
        return LegacySourceAdapter(Che168Scraper(max_images=max_images))
    if code == "dongchedi":
        return LegacySourceAdapter(DongchediScraper(max_images=max_images))
    if code == "guazi":
        return LegacySourceAdapter(GuaziScraper(max_images=max_images))
    raise ValueError(f"Unsupported source: {source}")
