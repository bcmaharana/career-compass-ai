"""Repository interfaces for the Opportunity Intelligence bounded
context. Application services depend only on this Protocol — see
app/domain/resume_intelligence/repositories.py for the established
pattern this follows.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.opportunity_intelligence.entities import JobListingCacheEntry


class JobListingCacheRepository(Protocol):
    async def get_by_search(
        self,
        role_query: str,
        location_query: str,
        *,
        max_days_old: int = 0,
        distance_miles: int = 0,
        employment_time: str = "",
        employment_type: str = "",
    ) -> JobListingCacheEntry | None: ...

    async def upsert(self, entry: JobListingCacheEntry) -> JobListingCacheEntry:
        """Insert a new cache row, or overwrite the existing one for the
        same (role_query, location_query, filters...) combination — a
        cache entry never accumulates history, only its most recent
        fetch matters."""
        ...
