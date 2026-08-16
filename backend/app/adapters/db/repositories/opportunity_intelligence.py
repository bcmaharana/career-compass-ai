"""SQLAlchemy repository implementation for the Opportunity Intelligence
domain (Phase 6).

Mirrors the mapping-function pattern established in
app/adapters/db/repositories/resume_intelligence.py. `listings` is
stored as a plain JSON blob (list of dicts) — `JobListing.posted_at` is
serialized to an ISO string, same idiom as Resume.extracted_data storing
dates as strings.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.models import JobListingCacheModel
from app.domain.opportunity_intelligence.entities import JobListing, JobListingCacheEntry


def _listing_to_dict(listing: JobListing) -> dict[str, object]:
    return {
        "provider_id": listing.provider_id,
        "title": listing.title,
        "company": listing.company,
        "location": listing.location,
        "description": listing.description,
        "redirect_url": listing.redirect_url,
        "salary_min": listing.salary_min,
        "salary_max": listing.salary_max,
        "contract_type": listing.contract_type,
        "category": listing.category,
        "posted_at": listing.posted_at.isoformat() if listing.posted_at else None,
    }


def _dict_to_listing(data: dict[str, object]) -> JobListing:
    posted_at_raw = data.get("posted_at")
    salary_min = data.get("salary_min")
    salary_max = data.get("salary_max")
    contract_type = data.get("contract_type")
    company = data.get("company")
    location = data.get("location")
    category = data.get("category")
    return JobListing(
        provider_id=str(data.get("provider_id", "")),
        title=str(data.get("title", "")),
        company=company if isinstance(company, str) else None,
        location=location if isinstance(location, str) else None,
        description=str(data.get("description", "")),
        redirect_url=str(data.get("redirect_url", "")),
        salary_min=salary_min if isinstance(salary_min, int | float) else None,
        salary_max=salary_max if isinstance(salary_max, int | float) else None,
        contract_type=contract_type if isinstance(contract_type, str) else None,
        category=category if isinstance(category, str) else None,
        posted_at=datetime.fromisoformat(posted_at_raw) if isinstance(posted_at_raw, str) else None,
    )


def _cache_to_domain(model: JobListingCacheModel) -> JobListingCacheEntry:
    return JobListingCacheEntry(
        id=model.id,
        role_query=model.role_query,
        location_query=model.location_query,
        listings=[_dict_to_listing(item) for item in model.listings],
        fetched_at=model.fetched_at,
        source=model.source,
        max_days_old=model.max_days_old,
        distance_miles=model.distance_miles,
        employment_time=model.employment_time,
        employment_type=model.employment_type,
    )


class SqlAlchemyJobListingCacheRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_search(
        self,
        role_query: str,
        location_query: str,
        *,
        max_days_old: int = 0,
        distance_miles: int = 0,
        employment_time: str = "",
        employment_type: str = "",
    ) -> JobListingCacheEntry | None:
        result = await self._session.execute(
            select(JobListingCacheModel).where(
                JobListingCacheModel.role_query == role_query,
                JobListingCacheModel.location_query == location_query,
                JobListingCacheModel.max_days_old == max_days_old,
                JobListingCacheModel.distance_miles == distance_miles,
                JobListingCacheModel.employment_time == employment_time,
                JobListingCacheModel.employment_type == employment_type,
            )
        )
        model = result.scalar_one_or_none()
        return _cache_to_domain(model) if model else None

    async def upsert(self, entry: JobListingCacheEntry) -> JobListingCacheEntry:
        result = await self._session.execute(
            select(JobListingCacheModel).where(
                JobListingCacheModel.role_query == entry.role_query,
                JobListingCacheModel.location_query == entry.location_query,
                JobListingCacheModel.max_days_old == entry.max_days_old,
                JobListingCacheModel.distance_miles == entry.distance_miles,
                JobListingCacheModel.employment_time == entry.employment_time,
                JobListingCacheModel.employment_type == entry.employment_type,
            )
        )
        model = result.scalar_one_or_none()
        listings_json = [_listing_to_dict(listing) for listing in entry.listings]

        if model is None:
            model = JobListingCacheModel(
                id=entry.id or uuid4(),
                role_query=entry.role_query,
                location_query=entry.location_query,
                listings=listings_json,
                fetched_at=entry.fetched_at,
                source=entry.source,
                max_days_old=entry.max_days_old,
                distance_miles=entry.distance_miles,
                employment_time=entry.employment_time,
                employment_type=entry.employment_type,
            )
            self._session.add(model)
        else:
            model.listings = listings_json
            model.fetched_at = entry.fetched_at
            model.source = entry.source

        await self._session.flush()
        await self._session.refresh(model)
        return _cache_to_domain(model)
