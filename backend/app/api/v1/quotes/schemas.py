"""Request/response schemas for the quote-of-the-day API."""

from __future__ import annotations

from pydantic import BaseModel


class QuoteOfTheDayResponse(BaseModel):
    content: str
    author: str | None
