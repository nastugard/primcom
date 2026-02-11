from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Any


@dataclasses.dataclass(frozen=True)
class ScrapedListing:
    source_code: str
    source_listing_id: str
    original_url: str
    scraped_at: dt.datetime
    status: str
    ad_hash: str
    content_checksum: str | None
    normalized: dict[str, Any]
    originals: dict[str, Any]
    raw_data: dict[str, Any]
    image_urls: list[str]


class BaseScraper:
    source_code: str

    async def scrape(self, limit: int) -> list[ScrapedListing]:
        raise NotImplementedError
