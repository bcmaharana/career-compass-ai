"""ZenQuotes-backed quote-of-the-day provider (UI enhancement brief Part
1.3).

Fetched server-side, not from the browser: zenquotes.io does not return
CORS headers for direct client-side fetches (confirmed by hand before
choosing this shape), so a backend adapter sidesteps that entirely and
keeps the frontend ignorant of which provider is in play — swapping to a
custom/owned quote source later only touches this file plus the wiring
in app/api/dependencies.py, per QuoteProviderInterface.

Caches the day's quote in-process (keyed by UTC date) rather than
calling out on every request — zenquotes' free tier is aggressively
rate-limited (5 requests/30s per IP) and the value is identical for
everyone all day anyway, so there is nothing to gain from re-fetching.
The instance handed out by get_quote_provider() (app/api/dependencies.py)
is a process-wide singleton specifically so this cache survives across
requests rather than resetting on every call.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import httpx

from app.core.config import Settings
from app.core.exceptions import CareerCompassError
from app.core.quote_provider_interface import Quote


class QuoteProviderError(CareerCompassError):
    code = "QUOTE_PROVIDER_ERROR"


class ZenQuotesProvider:
    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.quote_provider_base_url
        self._cached_date: date | None = None
        self._cached_quote: Quote | None = None

    async def get_quote_of_the_day(self) -> Quote:
        today = datetime.now(UTC).date()
        if self._cached_date == today and self._cached_quote is not None:
            return self._cached_quote

        quote = await self._fetch()
        self._cached_date = today
        self._cached_quote = quote
        return quote

    async def _fetch(self) -> Quote:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/api/today")
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise QuoteProviderError(f"Failed to fetch quote of the day: {exc}") from exc

        if not payload:
            raise QuoteProviderError("Quote provider returned no quotes.")

        entry = payload[0]
        content = entry.get("q")
        if not content:
            raise QuoteProviderError("Quote provider response was missing quote content.")

        return Quote(content=content, author=entry.get("a") or None)
