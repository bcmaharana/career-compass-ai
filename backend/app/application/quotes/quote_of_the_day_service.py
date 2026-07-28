"""Quote-of-the-day application service (UI enhancement brief Part 1.3).

The fixed Header (see the brief's Part 1.1) never hides, so it must
never render broken — this service's only real job beyond delegating to
the provider is making sure a transient upstream failure degrades to a
static local quote instead of surfacing an error into that
always-visible chrome.
"""

from __future__ import annotations

from app.core.exceptions import CareerCompassError
from app.core.logging import get_logger
from app.core.quote_provider_interface import Quote, QuoteProviderInterface

logger = get_logger(__name__)

_FALLBACK_QUOTE = Quote(
    content="The best way to predict the future is to create it.",
    author="Peter Drucker",
)


class QuoteOfTheDayService:
    def __init__(self, provider: QuoteProviderInterface) -> None:
        self._provider = provider

    async def get_quote_of_the_day(self) -> Quote:
        try:
            return await self._provider.get_quote_of_the_day()
        except CareerCompassError as exc:
            logger.warning("quote_provider_failed", error=str(exc), code=exc.code)
            return _FALLBACK_QUOTE
