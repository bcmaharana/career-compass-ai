"""Settings > Job Search Preference (Phase 6 follow-up).

Self-service, same ownership pattern as UpdateUserProfileService/
ModelPreferenceService — a user only ever reads/writes their own
preference. Persisted directly on `User` (job_search_* fields), not a
separate table — same "plain field, None means default behavior"
pattern as `preferred_model_version_id`.

Valid values for each filter are exactly what was confirmed live
against the real Adzuna API before this feature was designed — no
guessing: max_days_old in {1, 3, 7} (Adzuna's "posted date" filter),
distance_miles in {10, 30, 50, 100} (Adzuna's `distance` radius param),
employment_time/employment_type are single-select (not multi-select)
because Adzuna's own full_time/part_time and contract/permanent flags
are mutually exclusive per facet — combining two values in the same
facet in one request is a hard 400 from Adzuna, not an OR filter.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.identity.entities import User
from app.domain.identity.repositories import UserRepository

VALID_MAX_DAYS_OLD = frozenset({1, 3, 7})
VALID_DISTANCE_MILES = frozenset({10, 30, 50, 100})
VALID_EMPLOYMENT_TIME = frozenset({"full_time", "part_time"})
VALID_EMPLOYMENT_TYPE = frozenset({"contract", "permanent"})


@dataclass(slots=True)
class JobSearchPreference:
    location: str | None
    max_days_old: int | None
    distance_miles: int | None
    employment_time: str | None
    employment_type: str | None


def _to_preference(user: User) -> JobSearchPreference:
    return JobSearchPreference(
        location=user.job_search_location,
        max_days_old=user.job_search_max_days_old,
        distance_miles=user.job_search_distance_miles,
        employment_time=user.job_search_employment_time,
        employment_type=user.job_search_employment_type,
    )


class JobSearchPreferenceService:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def get(self, *, tenant_id: UUID, user_id: UUID) -> JobSearchPreference:
        user = await self._get_user_or_raise(tenant_id, user_id)
        return _to_preference(user)

    async def update(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        location: str | None,
        max_days_old: int | None,
        distance_miles: int | None,
        employment_time: str | None,
        employment_type: str | None,
    ) -> JobSearchPreference:
        if max_days_old is not None and max_days_old not in VALID_MAX_DAYS_OLD:
            raise ValidationError(
                f"max_days_old must be one of {sorted(VALID_MAX_DAYS_OLD)} or null.",
                code="INVALID_MAX_DAYS_OLD",
            )
        if distance_miles is not None and distance_miles not in VALID_DISTANCE_MILES:
            raise ValidationError(
                f"distance_miles must be one of {sorted(VALID_DISTANCE_MILES)} or null.",
                code="INVALID_DISTANCE_MILES",
            )
        if employment_time is not None and employment_time not in VALID_EMPLOYMENT_TIME:
            raise ValidationError(
                f"employment_time must be one of {sorted(VALID_EMPLOYMENT_TIME)} or null.",
                code="INVALID_EMPLOYMENT_TIME",
            )
        if employment_type is not None and employment_type not in VALID_EMPLOYMENT_TYPE:
            raise ValidationError(
                f"employment_type must be one of {sorted(VALID_EMPLOYMENT_TYPE)} or null.",
                code="INVALID_EMPLOYMENT_TYPE",
            )

        user = await self._get_user_or_raise(tenant_id, user_id)
        trimmed_location = location.strip() if location else ""
        user.job_search_location = trimmed_location or None
        user.job_search_max_days_old = max_days_old
        user.job_search_distance_miles = distance_miles
        user.job_search_employment_time = employment_time
        user.job_search_employment_type = employment_type
        updated = await self._users.update(user)
        return _to_preference(updated)

    async def _get_user_or_raise(self, tenant_id: UUID, user_id: UUID) -> User:
        user = await self._users.get_by_id(tenant_id, user_id)
        if user is None:
            raise NotFoundError("User not found.", code="USER_NOT_FOUND")
        return user
