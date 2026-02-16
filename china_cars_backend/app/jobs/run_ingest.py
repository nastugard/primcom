from __future__ import annotations

import argparse
import asyncio

from app.core import settings
from app.db import SessionLocal
from app.services.ingest import run_ingestion


async def _run(args) -> None:
    sources = [s.strip().lower() for s in (args.sources or "").split(",") if s.strip()]
    if not sources:
        sources = settings.scraper_sources_list

    async with SessionLocal() as session:
        result = await run_ingestion(
            session,
            sources=sources,
            limit=int(args.limit),
            max_images=int(args.max_images),
            skip_existing=bool(args.skip_existing),
            throttle_ms=int(args.throttle_ms),
            download_images=not bool(args.skip_images),
        )
    print(result, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default=",".join(settings.scraper_sources_list))
    parser.add_argument("--limit", type=int, default=int(settings.daily_new_limit))
    parser.add_argument("--max-images", type=int, default=int(settings.che168_max_images))
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--no-skip-existing", action="store_true")
    parser.add_argument("--skip-images", action="store_true")
    parser.add_argument("--throttle-ms", type=int, default=int(settings.scraper_throttle_ms))
    args = parser.parse_args()

    if not args.skip_existing and not args.no_skip_existing:
        args.skip_existing = bool(settings.scraper_skip_existing)
    if args.no_skip_existing:
        args.skip_existing = False

    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
