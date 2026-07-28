"""Unit tests for CareerProfileService.

Uses fake in-memory repositories satisfying the Protocol interfaces in
app/domain/career_profile/repositories.py — no database, following the
repository test pattern established in Phase 0/1
(tests/unit/test_repository_pattern_example.py).
"""

from __future__ import annotations

import uuid
from dataclasses import replace

import pytest

from app.application.career_profile.career_profile_service import CareerProfileService
from app.domain.career_profile.entities import CareerProfile, CareerProfileVersion


class FakeCareerProfileRepository:
    """Note: get_by_user_id/get_by_id return a *copy* of the stored
    profile, not the live object reference — matching the real
    SqlAlchemyCareerProfileRepository, which always constructs a fresh
    CareerProfile dataclass from the current DB row on every fetch (see
    _profile_to_domain in app/adapters/db/repositories/career_profile.py).
    Returning the live reference here caused a real, hard-to-spot test
    bug: two sequential calls to svc.update() would both mutate the
    *same* object, making a variable holding "the first update's result"
    silently reflect the second update too. This is exactly the kind of
    aliasing mismatch a fake repository can introduce that a real one
    can't — worth the explicit copy even though it's a few extra bytes
    per fetch.
    """

    def __init__(self) -> None:
        self.profiles: dict[uuid.UUID, CareerProfile] = {}

    async def create(self, profile: CareerProfile) -> CareerProfile:
        self.profiles[profile.id] = profile
        return replace(profile)

    async def get_by_user_id(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID
    ) -> CareerProfile | None:
        for profile in self.profiles.values():
            if profile.tenant_id == tenant_id and profile.user_id == user_id:
                return replace(profile)
        return None

    async def get_by_id(self, tenant_id: uuid.UUID, profile_id: uuid.UUID) -> CareerProfile | None:
        profile = self.profiles.get(profile_id)
        return replace(profile) if profile and profile.tenant_id == tenant_id else None

    async def update(self, profile: CareerProfile) -> CareerProfile:
        self.profiles[profile.id] = replace(profile)
        return replace(profile)


class FakeCareerProfileVersionRepository:
    def __init__(self) -> None:
        self.versions: list[CareerProfileVersion] = []

    async def create(self, version: CareerProfileVersion) -> CareerProfileVersion:
        self.versions.append(version)
        return version

    async def list_for_profile(
        self, career_profile_id: uuid.UUID, *, limit: int = 50
    ) -> list[CareerProfileVersion]:
        return [v for v in self.versions if v.career_profile_id == career_profile_id][:limit]


@pytest.fixture
def service() -> (
    tuple[CareerProfileService, FakeCareerProfileRepository, FakeCareerProfileVersionRepository]
):
    profiles = FakeCareerProfileRepository()
    versions = FakeCareerProfileVersionRepository()
    return CareerProfileService(profiles, versions), profiles, versions


@pytest.mark.unit
class TestGetOrCreate:
    async def test_creates_a_profile_on_first_access(self, service) -> None:
        svc, profiles, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        profile = await svc.get_or_create(tenant_id=tenant_id, user_id=user_id)

        assert profile.tenant_id == tenant_id
        assert profile.user_id == user_id
        assert profile.current_version == 1
        assert profile.headline is None
        assert len(profiles.profiles) == 1

    async def test_returns_the_same_profile_on_subsequent_access(self, service) -> None:
        svc, profiles, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        first = await svc.get_or_create(tenant_id=tenant_id, user_id=user_id)
        second = await svc.get_or_create(tenant_id=tenant_id, user_id=user_id)

        assert first.id == second.id
        assert len(profiles.profiles) == 1


@pytest.mark.unit
class TestUpdate:
    async def test_updates_headline_and_summary(self, service) -> None:
        svc, _, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        await svc.get_or_create(tenant_id=tenant_id, user_id=user_id)

        updated = await svc.update(
            tenant_id=tenant_id, user_id=user_id, headline="Senior Engineer", summary="10 years"
        )

        assert updated.headline == "Senior Engineer"
        assert updated.summary == "10 years"

    async def test_increments_version_on_update(self, service) -> None:
        svc, _, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        await svc.get_or_create(tenant_id=tenant_id, user_id=user_id)

        first_update = await svc.update(
            tenant_id=tenant_id, user_id=user_id, headline="v1", summary=None
        )
        second_update = await svc.update(
            tenant_id=tenant_id, user_id=user_id, headline="v2", summary=None
        )

        assert first_update.current_version == 2
        assert second_update.current_version == 3

    async def test_snapshots_prior_state_before_updating(self, service) -> None:
        svc, _, versions = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        await svc.get_or_create(tenant_id=tenant_id, user_id=user_id)

        await svc.update(tenant_id=tenant_id, user_id=user_id, headline="Original", summary=None)
        await svc.update(tenant_id=tenant_id, user_id=user_id, headline="Changed", summary=None)

        assert len(versions.versions) == 2
        # The second version snapshot should capture "Original" — the
        # state *before* it was changed to "Changed", not after.
        assert versions.versions[1].snapshot["headline"] == "Original"

    async def test_update_creates_profile_implicitly_if_none_exists(self, service) -> None:
        svc, profiles, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        updated = await svc.update(
            tenant_id=tenant_id, user_id=user_id, headline="First ever update", summary=None
        )

        assert updated.headline == "First ever update"
        assert len(profiles.profiles) == 1
