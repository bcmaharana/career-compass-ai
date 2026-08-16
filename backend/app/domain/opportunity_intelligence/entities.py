"""Opportunity Intelligence domain entities (Phase 6).

Plain dataclasses — no SQLAlchemy, no Pydantic, no FastAPI. Mirrors the
pattern established in app/domain/resume_intelligence/entities.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class JobListing:
    """A single job listing, as returned by a job listings provider
    (Adzuna today). Not its own DB row — a list of these is serialized
    into a JobListingCacheEntry's `listings` column."""

    provider_id: str
    title: str
    company: str | None
    location: str | None
    description: str
    redirect_url: str
    salary_min: float | None
    salary_max: float | None
    contract_type: str | None
    category: str | None
    posted_at: datetime | None


@dataclass(slots=True)
class JobListingCacheEntry:
    """Cached results for one (role_query, location_query, filters...)
    search.

    Global, not tenant-scoped — see
    app/adapters/db/models/opportunity_intelligence.py's module
    docstring for why: job listings for a given search are identical
    regardless of which tenant is asking, and per-tenant keys would
    just multiply cache misses against Adzuna's shared monthly quota.

    The filter fields below key the cache same as role/location —
    correctness requires it (a "last 3 days" search must never be
    served from a "no preference" cache entry), even though it means
    more distinct cache rows and more real Adzuna calls as people
    explore different Job Search Preference combinations. Each uses a
    concrete "no preference" sentinel (0 / "") rather than None, since
    Postgres treats every NULL as distinct for UNIQUE constraint
    purposes — a NULL-keyed column would silently defeat the whole
    point of the unique constraint this cache's lookup relies on.
    """

    id: UUID
    role_query: str  # normalized (lowercased/stripped) search term
    location_query: str  # normalized "city, state" or "" (no filter)
    listings: list[JobListing] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=lambda: datetime.min)
    source: str = "adzuna"
    max_days_old: int = 0  # 0 = no preference
    distance_miles: int = 0  # 0 = no preference
    employment_time: str = ""  # "full_time" | "part_time" | "" (no preference)
    employment_type: str = ""  # "contract" | "permanent" | "" (no preference)
