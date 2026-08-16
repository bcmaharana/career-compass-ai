"""Port for an external job-listings provider (Adzuna today).

A separate file from repositories.py, mirroring how
app/domain/resume_intelligence/storage.py and
app/domain/resume_intelligence/text_extraction.py each get their own
domain-layer file for a non-persistence external port.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.opportunity_intelligence.entities import JobListing


class JobListingProvider(Protocol):
    async def search(
        self,
        *,
        what: str,
        where: str | None,
        results_per_page: int = 20,
        max_days_old: int | None = None,
        distance_miles: int | None = None,
        employment_time: str | None = None,
        employment_type: str | None = None,
    ) -> list[JobListing]: ...
