"""Job listings orchestration (Phase 6).

Request-time-driven check-then-fetch against job_listing_cache — no job
scheduler exists in this codebase (same "live computation, no batch
job" precedent as CIKG's knowledge_quality_score), so a 24h TTL is
checked on every request rather than refreshed in the background. On a
fresh-fetch failure, stale cache is served rather than erroring, if any
exists — better than nothing, and honest (fetched_at is always surfaced
to the caller).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.adapters.job_listings.adzuna_provider import AdzunaJobProviderError
from app.application.career_profile.target_role_service import TargetRoleService
from app.domain.identity.repositories import UserRepository
from app.domain.opportunity_intelligence.entities import JobListing, JobListingCacheEntry
from app.domain.opportunity_intelligence.job_provider import JobListingProvider
from app.domain.opportunity_intelligence.repositories import JobListingCacheRepository

_CACHE_TTL = timedelta(hours=24)

# Adzuna's `what` param ANDs every word together — a fine default for a
# common title ("Software Engineer") but returns zero results for
# compound/qualifier-heavy free text a user (or the CIKG catalog) might
# use as a target role name ("Enterprise Agile Coach", "Delivery Lead /
# Program Delivery Manager") since the *exact* combination rarely
# appears verbatim in a real posting. Confirmed live against the real
# Adzuna API: the literal role name returns 0 for several real target
# roles; `what_or` (Adzuna's OR semantics) returns thousands of mostly
# irrelevant results; `what_phrase` (exact phrase) fails identically to
# plain `what` for a multi-word title. So the fix is a text-only query
# relaxation, not an Adzuna param change — strip seniority/scope
# qualifier words, keeping the core noun phrase, which live testing
# confirmed returns real, relevant results ("Senior Agile Coach" ->
# "Agile Coach", 14 results; "Director of Agile Transformation" ->
# "Agile Transformation", 23 results).
_QUALIFIER_WORDS = frozenset(
    {
        "senior",
        "sr",
        "junior",
        "jr",
        "lead",
        "staff",
        "principal",
        "enterprise",
        "global",
        "chief",
        "associate",
        "assistant",
        "director",
        "head",
        "vp",
        "vice",
        "president",
        "of",
        "the",
    }
)


@dataclass(slots=True)
class JobListingsResult:
    target_role_id: UUID
    role_query: str
    location_query: str
    fetched_at: datetime
    listings: list[JobListing]


def _normalize(value: str) -> str:
    return value.strip().lower()


def _strip_qualifiers(text: str) -> str | None:
    """Drop qualifier words, keeping the core noun phrase. Returns None
    if nothing was actually stripped, so the caller can skip a
    redundant retry."""
    words = text.split()
    kept = [w for w in words if w.strip(",/").lower() not in _QUALIFIER_WORDS]
    if not kept or len(kept) == len(words):
        return None
    return " ".join(kept)


def _query_candidates(role_name: str) -> list[str]:
    """Ordered search terms to try against the provider, from most to
    least literal, stopping at the first that returns real results — see
    _QUALIFIER_WORDS' comment for why this exists."""
    candidates = [role_name]

    working = role_name
    if "/" in working:
        first_segment = working.split("/", 1)[0].strip()
        if first_segment and first_segment != working:
            candidates.append(first_segment)
            working = first_segment

    stripped = _strip_qualifiers(working)
    if stripped:
        candidates.append(stripped)

    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in candidates:
        key = candidate.lower()
        if key not in seen:
            seen.add(key)
            ordered.append(candidate)
    return ordered


class JobListingService:
    def __init__(
        self,
        cache: JobListingCacheRepository,
        provider: JobListingProvider,
        target_roles: TargetRoleService,
        users: UserRepository,
    ) -> None:
        self._cache = cache
        self._provider = provider
        self._target_roles = target_roles
        self._users = users

    async def get_for_target_role(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID
    ) -> JobListingsResult:
        target_role = await self._target_roles.get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        user = await self._users.get_by_id(tenant_id, user_id)

        # Settings > Job Search Preference's location override takes
        # priority; falling back to profile city/state (the original
        # behavior before that preference existed) when unset.
        preferred_location = user.job_search_location if user else None
        profile_location = (
            f"{user.city}, {user.state}" if user and user.city and user.state else None
        )
        location = preferred_location or profile_location

        max_days_old = user.job_search_max_days_old if user else None
        distance_miles = user.job_search_distance_miles if user else None
        employment_time = user.job_search_employment_time if user else None
        employment_type = user.job_search_employment_type if user else None

        role_query = _normalize(target_role.role_name)
        location_query = _normalize(location or "")

        cached = await self._cache.get_by_search(
            role_query,
            location_query,
            max_days_old=max_days_old or 0,
            distance_miles=distance_miles or 0,
            employment_time=employment_time or "",
            employment_type=employment_type or "",
        )
        if cached and (datetime.now(UTC) - cached.fetched_at) < _CACHE_TTL:
            return _result(cached, target_role_id)

        try:
            listings: list[JobListing] = []
            for candidate in _query_candidates(target_role.role_name):
                listings = await self._provider.search(
                    what=candidate,
                    where=location,
                    max_days_old=max_days_old,
                    distance_miles=distance_miles,
                    employment_time=employment_time,
                    employment_type=employment_type,
                )
                if listings:
                    break
            entry = JobListingCacheEntry(
                id=cached.id if cached else uuid4(),
                role_query=role_query,
                location_query=location_query,
                listings=listings,
                fetched_at=datetime.now(UTC),
                max_days_old=max_days_old or 0,
                distance_miles=distance_miles or 0,
                employment_time=employment_time or "",
                employment_type=employment_type or "",
            )
            saved = await self._cache.upsert(entry)
            return _result(saved, target_role_id)
        except AdzunaJobProviderError:
            if cached:
                return _result(cached, target_role_id)
            raise


def _result(entry: JobListingCacheEntry, target_role_id: UUID) -> JobListingsResult:
    return JobListingsResult(
        target_role_id=target_role_id,
        role_query=entry.role_query,
        location_query=entry.location_query,
        fetched_at=entry.fetched_at,
        listings=entry.listings,
    )
