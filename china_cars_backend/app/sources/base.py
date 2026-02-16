from __future__ import annotations

from typing import Protocol

from app.scrapers.base import ScrapedListing


class SourceAdapter(Protocol):
    source_code: str

    async def scrape(self, *, limit: int) -> list[ScrapedListing]:
        ...

    def detect_placeholder(self, listing: ScrapedListing) -> bool:
        ...
