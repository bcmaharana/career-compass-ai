"""Unit tests for QuoteOfTheDayService."""

from __future__ import annotations

import pytest

from app.application.quotes.quote_of_the_day_service import QuoteOfTheDayService
from app.core.exceptions import CareerCompassError
from app.core.quote_provider_interface import Quote


class FakeQuoteProvider:
    def __init__(self, *, quote: Quote | None = None, error: Exception | None = None) -> None:
        self._quote = quote
        self._error = error

    async def get_quote_of_the_day(self) -> Quote:
        if self._error is not None:
            raise self._error
        assert self._quote is not None
        return self._quote


@pytest.mark.unit
class TestGetQuoteOfTheDay:
    async def test_returns_the_providers_quote_on_success(self) -> None:
        quote = Quote(content="Stay hungry, stay foolish.", author="Steve Jobs")
        service = QuoteOfTheDayService(FakeQuoteProvider(quote=quote))

        result = await service.get_quote_of_the_day()

        assert result == quote

    async def test_falls_back_to_a_local_quote_when_the_provider_fails(self) -> None:
        provider_error = CareerCompassError("boom", code="QUOTE_PROVIDER_ERROR")
        service = QuoteOfTheDayService(FakeQuoteProvider(error=provider_error))

        result = await service.get_quote_of_the_day()

        assert result.content
        assert isinstance(result.author, str) or result.author is None
