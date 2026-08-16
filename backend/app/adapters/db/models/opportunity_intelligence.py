"""SQLAlchemy ORM model for the Opportunity Intelligence bounded context
(Phase 6).

`job_listing_cache` is global reference data, not tenant-owned — no
`tenant_id`, no RLS (same shape as CIKG's tables in
app/adapters/db/models/career_intelligence.py). Job listings for a
given (role, location) search are identical regardless of which tenant
is asking, and Adzuna's free tier is rate-limited (~1,000 calls/month)
with no job scheduler in this codebase to refresh it in the background —
per-tenant cache keys would just multiply cache misses against a shared
monthly cap for zero benefit, so results are cached once per search
term and reused across every tenant that asks the same question.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.adapters.db.base import Base


class JobListingCacheModel(Base):
    __tablename__ = "job_listing_cache"
    __table_args__ = (
        UniqueConstraint(
            "role_query",
            "location_query",
            "max_days_old",
            "distance_miles",
            "employment_time",
            "employment_type",
            name="uq_job_listing_cache_search",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    role_query: Mapped[str] = mapped_column(String(255), nullable=False)
    location_query: Mapped[str] = mapped_column(String(255), nullable=False)
    # list[JobListing] serialized to plain JSON — posted_at stored as an
    # ISO string inside the blob, same idiom as ResumeModel.extracted_data.
    listings: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="adzuna")
    # Job Search Preference filter dimensions — 0/"" sentinels for "no
    # preference" rather than NULL, since Postgres treats every NULL as
    # distinct for UNIQUE constraint purposes (see the domain entity's
    # docstring for why that would break this table's whole purpose).
    max_days_old: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    distance_miles: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    employment_time: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    employment_type: Mapped[str] = mapped_column(String(20), nullable=False, default="")
