"""Unit tests for PlatformAccountDeletionService — the counterpart to
PlatformHandoffService, on the delete side. Covers both resolution
branches: Enterprise (via Tenant.platform_org_id) and Personal (via
derive_personal_subdomain)."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime

from app.application.identity.platform_account_deletion import PlatformAccountDeletionService
from app.domain.identity.account_deletion import TenantDeletionArtifacts
from app.domain.identity.entities import Tenant, User
from app.domain.identity.personal_accounts import derive_personal_subdomain


class FakeTenantRepository:
    def __init__(self) -> None:
        self.tenants: dict[uuid.UUID, Tenant] = {}

    async def create(self, tenant: Tenant) -> Tenant:
        self.tenants[tenant.id] = replace(tenant)
        return replace(tenant)

    async def get_by_id(self, tenant_id: uuid.UUID) -> Tenant | None:
        tenant = self.tenants.get(tenant_id)
        return replace(tenant) if tenant else None

    async def get_by_subdomain(self, subdomain: str) -> Tenant | None:
        for tenant in self.tenants.values():
            if tenant.subdomain == subdomain:
                return replace(tenant)
        return None

    async def get_by_platform_org_id(self, platform_org_id: uuid.UUID) -> Tenant | None:
        for tenant in self.tenants.values():
            if tenant.platform_org_id == platform_org_id:
                return replace(tenant)
        return None


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[uuid.UUID, User] = {}

    async def get_by_email(self, tenant_id: uuid.UUID, email: str) -> User | None:
        for user in self.users.values():
            if user.tenant_id == tenant_id and user.email == email:
                return replace(user)
        return None


class FakeTenantContextBinder:
    def __init__(self) -> None:
        self.bound_tenant_ids: list[uuid.UUID] = []

    async def bind(self, tenant_id: uuid.UUID) -> None:
        self.bound_tenant_ids.append(tenant_id)


class FakeAccountDeletionRepository:
    def __init__(self) -> None:
        self.deleted_tenant_ids: list[uuid.UUID] = []

    async def delete_tenant(self, tenant_id: uuid.UUID) -> TenantDeletionArtifacts:
        self.deleted_tenant_ids.append(tenant_id)
        return TenantDeletionArtifacts(
            resume_file_keys=[],
            profile_photos=[],
            interview_topic_image_keys=[],
            tailored_resume_file_keys=[],
            showcase_block_image_urls=[],
            showcase_resume_file_keys=[],
        )


def _tenant(**overrides: object) -> Tenant:
    now = datetime.now(UTC)
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "name": "Acme",
        "subdomain": "acme",
        "plan_tier": "free",
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return Tenant(**defaults)  # type: ignore[arg-type]


def _user(**overrides: object) -> User:
    now = datetime.now(UTC)
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "org_id": None,
        "email": "jordan@example.com",
        "salutation": None,
        "first_name": "Jordan",
        "last_name": "Rivera",
        "hashed_password": "irrelevant",
        "status": "active",
        "mfa_enabled": False,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return User(**defaults)  # type: ignore[arg-type]


def _service() -> tuple[
    PlatformAccountDeletionService, FakeTenantRepository, FakeUserRepository,
    FakeAccountDeletionRepository, FakeTenantContextBinder,
]:
    tenants = FakeTenantRepository()
    users = FakeUserRepository()
    account_deletion = FakeAccountDeletionRepository()
    tenant_context = FakeTenantContextBinder()
    service = PlatformAccountDeletionService(tenants, users, account_deletion, tenant_context)  # type: ignore[arg-type]
    return service, tenants, users, account_deletion, tenant_context


async def test_enterprise_deletion_resolves_via_platform_org_id() -> None:
    service, tenants, _, account_deletion, tenant_context = _service()
    platform_org_id = uuid.uuid4()
    tenant = _tenant(subdomain="scaledbrain", platform_org_id=platform_org_id)
    tenants.tenants[tenant.id] = tenant

    await service.execute(
        platform_account_id=str(uuid.uuid4()),
        email="admin@scaledbrain.com",
        org_id=str(platform_org_id),
    )

    assert account_deletion.deleted_tenant_ids == [tenant.id]
    assert tenant_context.bound_tenant_ids == [tenant.id]


async def test_enterprise_deletion_is_a_noop_when_org_never_provisioned() -> None:
    service, _, _, account_deletion, _ = _service()

    await service.execute(
        platform_account_id=str(uuid.uuid4()), email="admin@example.com", org_id=str(uuid.uuid4())
    )

    assert account_deletion.deleted_tenant_ids == []


async def test_enterprise_deletion_does_not_fall_back_to_personal_subdomain() -> None:
    """An org_id that fails to resolve must not silently delete an
    unrelated Personal tenant that happens to share the same email."""
    service, tenants, users, account_deletion, _ = _service()
    personal_tenant = _tenant(subdomain=derive_personal_subdomain("admin@example.com"))
    tenants.tenants[personal_tenant.id] = personal_tenant
    users.users[uuid.uuid4()] = _user(tenant_id=personal_tenant.id, email="admin@example.com")

    await service.execute(
        platform_account_id=str(uuid.uuid4()), email="admin@example.com", org_id=str(uuid.uuid4())
    )

    assert account_deletion.deleted_tenant_ids == []


async def test_personal_deletion_resolves_via_derived_subdomain() -> None:
    service, tenants, users, account_deletion, tenant_context = _service()
    email = "jordan@example.com"
    tenant = _tenant(subdomain=derive_personal_subdomain(email))
    tenants.tenants[tenant.id] = tenant
    platform_account_id = uuid.uuid4()
    users.users[uuid.uuid4()] = _user(
        tenant_id=tenant.id, email=email, platform_account_id=platform_account_id
    )

    await service.execute(
        platform_account_id=str(platform_account_id), email=email, org_id=None
    )

    assert account_deletion.deleted_tenant_ids == [tenant.id]
    assert tenant_context.bound_tenant_ids == [tenant.id]


async def test_personal_deletion_is_a_noop_when_no_tenant_exists() -> None:
    service, _, _, account_deletion, _ = _service()

    await service.execute(
        platform_account_id=str(uuid.uuid4()), email="nobody@example.com", org_id=None
    )

    assert account_deletion.deleted_tenant_ids == []


async def test_personal_deletion_rejects_platform_account_id_mismatch() -> None:
    """A subdomain-hash collision with an unrelated, never-linked local
    account must never be deleted."""
    service, tenants, users, account_deletion, _ = _service()
    email = "jordan@example.com"
    tenant = _tenant(subdomain=derive_personal_subdomain(email))
    tenants.tenants[tenant.id] = tenant
    users.users[uuid.uuid4()] = _user(
        tenant_id=tenant.id, email=email, platform_account_id=uuid.uuid4()
    )

    await service.execute(
        platform_account_id=str(uuid.uuid4()), email=email, org_id=None
    )

    assert account_deletion.deleted_tenant_ids == []


async def test_personal_deletion_allows_a_not_yet_linked_local_account() -> None:
    """A real, pre-existing local account that predates any platform
    link (platform_account_id is None) is still deletable — matches
    _find_or_link_user's own "a plain email match is safe here" logic
    in PlatformHandoffService."""
    service, tenants, users, account_deletion, _ = _service()
    email = "jordan@example.com"
    tenant = _tenant(subdomain=derive_personal_subdomain(email))
    tenants.tenants[tenant.id] = tenant
    users.users[uuid.uuid4()] = _user(tenant_id=tenant.id, email=email, platform_account_id=None)

    await service.execute(platform_account_id=str(uuid.uuid4()), email=email, org_id=None)

    assert account_deletion.deleted_tenant_ids == [tenant.id]
