"""Unit tests for JobSearchPreferenceService — fake UserRepository, no
database. Mirrors the fake-repository pattern established in
tests/unit/test_job_listing_service.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.application.opportunity_intelligence.job_search_preference_service import (
    JobSearchPreferenceService,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.identity.entities import User


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[uuid.UUID, User] = {}

    async def create(self, user: User) -> User:
        self.users[user.id] = user
        return user

    async def get_by_id(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> User | None:
        user = self.users.get(user_id)
        return user if user and user.tenant_id == tenant_id else None

    async def get_by_email(self, tenant_id: uuid.UUID, email: str) -> User | None:
        return None

    async def get_by_phone_e164(self, tenant_id: uuid.UUID, phone_e164: str) -> User | None:
        return None

    async def update(self, user: User) -> User:
        self.users[user.id] = user
        return user


def _make_user(tenant_id: uuid.UUID, user_id: uuid.UUID) -> User:
    return User(
        id=user_id,
        tenant_id=tenant_id,
        org_id=None,
        email="test@example.com",
        salutation=None,
        first_name="Test",
        last_name="User",
        hashed_password="x",
        status="active",
        mfa_enabled=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.mark.unit
class TestGet:
    async def test_returns_all_null_when_never_set(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        users_repo = FakeUserRepository()
        await users_repo.create(_make_user(tenant_id, user_id))
        service = JobSearchPreferenceService(users_repo)

        result = await service.get(tenant_id=tenant_id, user_id=user_id)

        assert result.location is None
        assert result.max_days_old is None
        assert result.distance_miles is None
        assert result.employment_time is None
        assert result.employment_type is None

    async def test_raises_when_user_missing(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        service = JobSearchPreferenceService(FakeUserRepository())

        with pytest.raises(NotFoundError):
            await service.get(tenant_id=tenant_id, user_id=user_id)


@pytest.mark.unit
class TestUpdate:
    async def test_saves_valid_preference(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        users_repo = FakeUserRepository()
        await users_repo.create(_make_user(tenant_id, user_id))
        service = JobSearchPreferenceService(users_repo)

        result = await service.update(
            tenant_id=tenant_id,
            user_id=user_id,
            location="Philadelphia, PA",
            max_days_old=7,
            distance_miles=50,
            employment_time="full_time",
            employment_type="permanent",
        )

        assert result.location == "Philadelphia, PA"
        assert result.max_days_old == 7
        assert result.distance_miles == 50
        assert result.employment_time == "full_time"
        assert result.employment_type == "permanent"
        assert users_repo.users[user_id].job_search_location == "Philadelphia, PA"

    async def test_blank_location_normalizes_to_none(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        users_repo = FakeUserRepository()
        await users_repo.create(_make_user(tenant_id, user_id))
        service = JobSearchPreferenceService(users_repo)

        result = await service.update(
            tenant_id=tenant_id,
            user_id=user_id,
            location="   ",
            max_days_old=None,
            distance_miles=None,
            employment_time=None,
            employment_type=None,
        )

        assert result.location is None

    async def test_rejects_invalid_max_days_old(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        users_repo = FakeUserRepository()
        await users_repo.create(_make_user(tenant_id, user_id))
        service = JobSearchPreferenceService(users_repo)

        with pytest.raises(ValidationError):
            await service.update(
                tenant_id=tenant_id,
                user_id=user_id,
                location=None,
                max_days_old=5,
                distance_miles=None,
                employment_time=None,
                employment_type=None,
            )

    async def test_rejects_invalid_distance_miles(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        users_repo = FakeUserRepository()
        await users_repo.create(_make_user(tenant_id, user_id))
        service = JobSearchPreferenceService(users_repo)

        with pytest.raises(ValidationError):
            await service.update(
                tenant_id=tenant_id,
                user_id=user_id,
                location=None,
                max_days_old=None,
                distance_miles=25,
                employment_time=None,
                employment_type=None,
            )

    async def test_rejects_invalid_employment_time(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        users_repo = FakeUserRepository()
        await users_repo.create(_make_user(tenant_id, user_id))
        service = JobSearchPreferenceService(users_repo)

        with pytest.raises(ValidationError):
            await service.update(
                tenant_id=tenant_id,
                user_id=user_id,
                location=None,
                max_days_old=None,
                distance_miles=None,
                employment_time="contractor",
                employment_type=None,
            )

    async def test_rejects_invalid_employment_type(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        users_repo = FakeUserRepository()
        await users_repo.create(_make_user(tenant_id, user_id))
        service = JobSearchPreferenceService(users_repo)

        with pytest.raises(ValidationError):
            await service.update(
                tenant_id=tenant_id,
                user_id=user_id,
                location=None,
                max_days_old=None,
                distance_miles=None,
                employment_time=None,
                employment_type="third_party",
            )

    async def test_can_clear_back_to_null(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        users_repo = FakeUserRepository()
        await users_repo.create(_make_user(tenant_id, user_id))
        service = JobSearchPreferenceService(users_repo)
        await service.update(
            tenant_id=tenant_id,
            user_id=user_id,
            location="Seattle, WA",
            max_days_old=7,
            distance_miles=50,
            employment_time="full_time",
            employment_type="permanent",
        )

        result = await service.update(
            tenant_id=tenant_id,
            user_id=user_id,
            location=None,
            max_days_old=None,
            distance_miles=None,
            employment_time=None,
            employment_type=None,
        )

        assert result.location is None
        assert result.max_days_old is None
        assert result.distance_miles is None
        assert result.employment_time is None
        assert result.employment_type is None

    async def test_raises_when_user_missing(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        service = JobSearchPreferenceService(FakeUserRepository())

        with pytest.raises(NotFoundError):
            await service.update(
                tenant_id=tenant_id,
                user_id=user_id,
                location=None,
                max_days_old=None,
                distance_miles=None,
                employment_time=None,
                employment_type=None,
            )
