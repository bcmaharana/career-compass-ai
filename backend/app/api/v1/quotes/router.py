"""Quote-of-the-day API routes (UI enhancement brief Part 1.3).

Thin per backend-architecture.md. The quote is identical for every
caller on a given day — no tenant-scoped data involved — so this only
depends on get_current_identity (a valid session) rather than
get_tenant_scoped_session.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_identity, get_quote_of_the_day_service
from app.api.v1.quotes.schemas import QuoteOfTheDayResponse
from app.application.quotes.quote_of_the_day_service import QuoteOfTheDayService
from app.core.identity_provider_interface import IdentityClaims

router = APIRouter(tags=["quotes"])


@router.get("/quote-of-the-day", response_model=QuoteOfTheDayResponse)
async def get_quote_of_the_day(
    identity: IdentityClaims = Depends(get_current_identity),
    service: QuoteOfTheDayService = Depends(get_quote_of_the_day_service),
) -> QuoteOfTheDayResponse:
    quote = await service.get_quote_of_the_day()
    return QuoteOfTheDayResponse(content=quote.content, author=quote.author)
