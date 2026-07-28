"""Quote-of-the-day provider abstraction (UI enhancement brief Part 1.3).

An external quotes API is used for now, with a known future plan to
replace it with a custom/owned quote source (see the brief's "Open /
deferred items"). Application services and API routers depend only on
`QuoteProviderInterface` — swapping providers means writing a new
adapter against this interface, not touching callers, the same shape as
`IdentityProviderInterface` in this module's sibling file.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Quote:
    content: str
    author: str | None


class QuoteProviderInterface(Protocol):
    async def get_quote_of_the_day(self) -> Quote:
        """Return today's quote.

        Raises app.adapters.quotes.zen_quotes_provider.QuoteProviderError
        (or any other CareerCompassError) on failure — callers should not
        assume this never raises; see QuoteOfTheDayService for the
        fallback behavior that keeps the always-visible Header usable
        even when the upstream provider is unreachable.
        """
        ...
