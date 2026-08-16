"""Unit tests for JobListingService — fake repositories/provider, no
database, no real Adzuna calls. Mirrors the fake-repository pattern
established in tests/unit/test_target_role_service.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.adapters.job_listings.adzuna_provider import AdzunaJobProviderError
from app.application.career_profile.target_role_service import TargetRoleService
from app.application.opportunity_intelligence.job_listing_service import (
    JobListingService,
    _query_candidates,
)
from app.domain.career_profile.entities import TargetRole
from app.domain.identity.entities import User
from app.domain.opportunity_intelligence.entities import JobListing, JobListingCacheEntry


class FakeTargetRoleRepository:
    def __init__(self) -> None:
        self.target_roles: dict[uuid.UUID, TargetRole] = {}

    async def create(self, target_role: TargetRole) -> TargetRole:
        self.target_roles[target_role.id] = target_role
        return target_role

    async def get_by_id(self, tenant_id: uuid.UUID, target_role_id: uuid.UUID) -> TargetRole | None:
        role = self.target_roles.get(target_role_id)
        return role if role and role.tenant_id == tenant_id else None

    async def list_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[TargetRole]:
        return [
            r for r in self.target_roles.values() if r.tenant_id == tenant_id and r.user_id == user_id
        ]

    async def update(self, target_role: TargetRole) -> TargetRole:
        self.target_roles[target_role.id] = target_role
        return target_role

    async def soft_delete(self, tenant_id: uuid.UUID, target_role_id: uuid.UUID) -> None:
        self.target_roles.pop(target_role_id, None)


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


class FakeJobListingCacheRepository:
    def __init__(self) -> None:
        self.entries: dict[tuple[str, str, int, int, str, str], JobListingCacheEntry] = {}

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
        return self.entries.get(
            (role_query, location_query, max_days_old, distance_miles, employment_time, employment_type)
        )

    async def upsert(self, entry: JobListingCacheEntry) -> JobListingCacheEntry:
        self.entries[
            (
                entry.role_query,
                entry.location_query,
                entry.max_days_old,
                entry.distance_miles,
                entry.employment_time,
                entry.employment_type,
            )
        ] = entry
        return entry


class FakeJobListingProvider:
    def __init__(
        self,
        listings: list[JobListing] | None = None,
        fail: bool = False,
        listings_by_query: dict[str, list[JobListing]] | None = None,
    ) -> None:
        self._listings = listings or []
        self._fail = fail
        self._listings_by_query = listings_by_query
        self.call_count = 0
        self.calls_what: list[str] = []

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
    ) -> list[JobListing]:
        self.call_count += 1
        self.calls_what.append(what)
        if self._fail:
            raise AdzunaJobProviderError("simulated failure")
        if self._listings_by_query is not None:
            return self._listings_by_query.get(what, [])
        return self._listings


def _make_target_role(tenant_id: uuid.UUID, user_id: uuid.UUID, role_name: str = "Staff Engineer") -> TargetRole:
    return TargetRole(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        role_name=role_name,
        tag="SE",
        created_at=datetime.now(UTC),
    )


def _make_user(tenant_id: uuid.UUID, user_id: uuid.UUID, city: str | None = None, state: str | None = None) -> User:
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
        city=city,
        state=state,
    )


@pytest.mark.unit
class TestGetForTargetRole:
    async def test_fetches_and_caches_fresh_listings(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_roles_repo = FakeTargetRoleRepository()
        users_repo = FakeUserRepository()
        cache = FakeJobListingCacheRepository()
        listing = JobListing(
            provider_id="1",
            title="Staff Engineer",
            company="Acme",
            location="Remote",
            description="desc",
            redirect_url="https://example.com",
            salary_min=100000.0,
            salary_max=150000.0,
            contract_type=None,
            category="IT Jobs",
            posted_at=None,
        )
        provider = FakeJobListingProvider(listings=[listing])
        target_role = await target_roles_repo.create(_make_target_role(tenant_id, user_id))
        await users_repo.create(_make_user(tenant_id, user_id, city="Seattle", state="WA"))

        service = JobListingService(cache, provider, TargetRoleService(target_roles_repo), users_repo)
        result = await service.get_for_target_role(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id
        )

        assert result.listings == [listing]
        assert provider.call_count == 1
        assert cache.entries[("staff engineer", "seattle, wa", 0, 0, "", "")].listings == [listing]

    async def test_serves_from_cache_within_ttl(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_roles_repo = FakeTargetRoleRepository()
        users_repo = FakeUserRepository()
        cache = FakeJobListingCacheRepository()
        provider = FakeJobListingProvider(listings=[])
        target_role = await target_roles_repo.create(_make_target_role(tenant_id, user_id))
        await users_repo.create(_make_user(tenant_id, user_id))

        service = JobListingService(cache, provider, TargetRoleService(target_roles_repo), users_repo)
        await service.get_for_target_role(tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id)
        await service.get_for_target_role(tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id)

        # The default target role ("Staff Engineer") tries a relaxed
        # fallback candidate ("Engineer") on the first, cache-missing
        # call since the fake always returns empty listings — see
        # _query_candidates. The second call is a real cache hit and
        # makes no provider calls at all.
        assert provider.call_count == 2

    async def test_refetches_after_ttl_expires(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_roles_repo = FakeTargetRoleRepository()
        users_repo = FakeUserRepository()
        cache = FakeJobListingCacheRepository()
        provider = FakeJobListingProvider(listings=[])
        target_role = await target_roles_repo.create(_make_target_role(tenant_id, user_id))
        await users_repo.create(_make_user(tenant_id, user_id))
        # Seed a stale cache entry directly.
        stale = JobListingCacheEntry(
            id=uuid.uuid4(),
            role_query="staff engineer",
            location_query="",
            listings=[],
            fetched_at=datetime.now(UTC) - timedelta(hours=25),
        )
        await cache.upsert(stale)

        service = JobListingService(cache, provider, TargetRoleService(target_roles_repo), users_repo)
        await service.get_for_target_role(tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id)

        # Same relaxed-fallback reasoning as test_serves_from_cache_within_ttl.
        assert provider.call_count == 2

    async def test_serves_stale_cache_on_provider_failure(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_roles_repo = FakeTargetRoleRepository()
        users_repo = FakeUserRepository()
        cache = FakeJobListingCacheRepository()
        listing = JobListing(
            provider_id="1",
            title="Old listing",
            company=None,
            location=None,
            description="",
            redirect_url="",
            salary_min=None,
            salary_max=None,
            contract_type=None,
            category=None,
            posted_at=None,
        )
        provider = FakeJobListingProvider(fail=True)
        target_role = await target_roles_repo.create(_make_target_role(tenant_id, user_id))
        await users_repo.create(_make_user(tenant_id, user_id))
        stale = JobListingCacheEntry(
            id=uuid.uuid4(),
            role_query="staff engineer",
            location_query="",
            listings=[listing],
            fetched_at=datetime.now(UTC) - timedelta(hours=25),
        )
        await cache.upsert(stale)

        service = JobListingService(cache, provider, TargetRoleService(target_roles_repo), users_repo)
        result = await service.get_for_target_role(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id
        )

        assert result.listings == [listing]

    async def test_raises_when_no_cache_and_provider_fails(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_roles_repo = FakeTargetRoleRepository()
        users_repo = FakeUserRepository()
        cache = FakeJobListingCacheRepository()
        provider = FakeJobListingProvider(fail=True)
        target_role = await target_roles_repo.create(_make_target_role(tenant_id, user_id))
        await users_repo.create(_make_user(tenant_id, user_id))

        service = JobListingService(cache, provider, TargetRoleService(target_roles_repo), users_repo)

        with pytest.raises(AdzunaJobProviderError):
            await service.get_for_target_role(
                tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id
            )


@pytest.mark.unit
class TestQueryCandidates:
    def test_returns_only_the_literal_title_when_nothing_to_relax(self) -> None:
        assert _query_candidates("Release Train Engineer") == ["Release Train Engineer"]

    def test_strips_seniority_qualifier(self) -> None:
        assert _query_candidates("Senior Agile Coach") == ["Senior Agile Coach", "Agile Coach"]

    def test_strips_scope_and_of_qualifiers(self) -> None:
        assert _query_candidates("Director of Agile Transformation") == [
            "Director of Agile Transformation",
            "Agile Transformation",
        ]

    def test_splits_on_slash_then_strips_qualifiers(self) -> None:
        assert _query_candidates("Delivery Lead / Program Delivery Manager") == [
            "Delivery Lead / Program Delivery Manager",
            "Delivery Lead",
            "Delivery",
        ]


@pytest.mark.unit
class TestRelaxedQueryFallback:
    async def test_falls_back_to_relaxed_query_when_exact_title_has_no_results(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_roles_repo = FakeTargetRoleRepository()
        users_repo = FakeUserRepository()
        cache = FakeJobListingCacheRepository()
        fallback_listing = JobListing(
            provider_id="2",
            title="Agile Coach",
            company="Acme",
            location="Philadelphia, PA",
            description="",
            redirect_url="https://example.com/2",
            salary_min=None,
            salary_max=None,
            contract_type=None,
            category=None,
            posted_at=None,
        )
        provider = FakeJobListingProvider(listings_by_query={"Agile Coach": [fallback_listing]})
        target_role = await target_roles_repo.create(
            _make_target_role(tenant_id, user_id, role_name="Enterprise Agile Coach")
        )
        await users_repo.create(_make_user(tenant_id, user_id, city="Philadelphia", state="PA"))

        service = JobListingService(cache, provider, TargetRoleService(target_roles_repo), users_repo)
        result = await service.get_for_target_role(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id
        )

        assert result.listings == [fallback_listing]
        assert provider.calls_what == ["Enterprise Agile Coach", "Agile Coach"]

    async def test_stops_at_first_candidate_with_results(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_roles_repo = FakeTargetRoleRepository()
        users_repo = FakeUserRepository()
        cache = FakeJobListingCacheRepository()
        listing = JobListing(
            provider_id="1",
            title="Release Train Engineer",
            company="Acme",
            location="Philadelphia, PA",
            description="",
            redirect_url="https://example.com/1",
            salary_min=None,
            salary_max=None,
            contract_type=None,
            category=None,
            posted_at=None,
        )
        provider = FakeJobListingProvider(listings=[listing])
        target_role = await target_roles_repo.create(
            _make_target_role(tenant_id, user_id, role_name="Release Train Engineer")
        )
        await users_repo.create(_make_user(tenant_id, user_id, city="Philadelphia", state="PA"))

        service = JobListingService(cache, provider, TargetRoleService(target_roles_repo), users_repo)
        result = await service.get_for_target_role(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id
        )

        assert result.listings == [listing]
        assert provider.calls_what == ["Release Train Engineer"]

    async def test_all_candidates_empty_caches_empty_result(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_roles_repo = FakeTargetRoleRepository()
        users_repo = FakeUserRepository()
        cache = FakeJobListingCacheRepository()
        provider = FakeJobListingProvider(listings_by_query={})
        target_role = await target_roles_repo.create(
            _make_target_role(tenant_id, user_id, role_name="Enterprise Agile Coach")
        )
        await users_repo.create(_make_user(tenant_id, user_id, city="Nowhere", state="ZZ"))

        service = JobListingService(cache, provider, TargetRoleService(target_roles_repo), users_repo)
        result = await service.get_for_target_role(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id
        )

        assert result.listings == []
        assert provider.calls_what == ["Enterprise Agile Coach", "Agile Coach"]
