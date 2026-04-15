from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Awaitable, Callable

import httpx

from app.core.settings import settings
from app.services.import_calculator.types import ResolvedRates, RuleSet


RateFetcher = Callable[[str], Awaitable[tuple[Decimal | None, str]]]


async def _fetch_rate_from_api(base_currency: str) -> tuple[Decimal | None, str]:
    template = str(settings.exchange_rate_api_url_template or "").strip()
    if not template:
        return None, "config"

    url = template.format(base=base_currency)
    timeout = max(1000, int(settings.exchange_rate_api_timeout_ms)) / 1000
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.get(url)
            res.raise_for_status()
        payload = res.json()
        rates = payload.get("rates") or {}
        rub_rate = rates.get("RUB")
        if rub_rate is None:
            return None, "config"
        rate = Decimal(str(rub_rate))
        if rate <= 0:
            return None, "config"
        return rate, "api"
    except Exception:
        return None, "config"


async def resolve_exchange_rates(
    *,
    currency: str,
    rule_set: RuleSet,
    exchange_rate_override: Decimal | None = None,
    fetch_rate: RateFetcher | None = None,
) -> ResolvedRates:
    fetcher = fetch_rate or _fetch_rate_from_api
    requested_currency = str(currency).upper()

    if exchange_rate_override is not None:
        currency_rate = exchange_rate_override
        currency_source = "override"
        if requested_currency == "EUR":
            eur_rate = exchange_rate_override
            eur_source = "override"
        else:
            eur_fetched, eur_fetched_source = await fetcher("EUR")
            eur_rate = eur_fetched or rule_set.default_exchange_rates["EUR"]
            eur_source = eur_fetched_source if eur_fetched is not None else "config"
    else:
        if requested_currency == "EUR":
            fetched_rate, fetched_source = await fetcher("EUR")
            currency_rate = fetched_rate or rule_set.default_exchange_rates["EUR"]
            currency_source = fetched_source if fetched_rate is not None else "config"
            eur_rate = currency_rate
            eur_source = currency_source
        else:
            async_rate, async_eur = await asyncio.gather(
                fetcher(requested_currency),
                fetcher("EUR"),
            )
            req_rate, req_src = async_rate
            eur_rate_candidate, eur_src = async_eur
            currency_rate = req_rate or rule_set.default_exchange_rates[requested_currency]  # type: ignore[index]
            currency_source = req_src if req_rate is not None else "config"
            eur_rate = eur_rate_candidate or rule_set.default_exchange_rates["EUR"]
            eur_source = eur_src if eur_rate_candidate is not None else "config"

    return ResolvedRates(
        currency_to_rub=currency_rate,
        currency_source=currency_source,
        eur_to_rub=eur_rate,
        eur_source=eur_source,
    )
