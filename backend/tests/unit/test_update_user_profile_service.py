"""Unit tests for UpdateUserProfileService."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.application.identity.update_user_profile import UpdateUserProfileService
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.identity.entities import Role, Tenant, User
from app.domain.platform_admin.entities import PlatformAdminGrant


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[uuid.UUID, User] = {}

    async def create(self, user: User) -> User:
        self.users[user.id] = replace(user)
        return replace(user)

    async def get_by_id(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> User | None:
        user = self.users.get(user_id)
        return replace(user) if user and user.tenant_id == tenant_id else None

    async def get_by_email(self, tenant_id: uuid.UUID, email: str) -> User | None:
        for user in self.users.values():
            if user.tenant_id == tenant_id and user.email == email:
                return replace(user)
        return None

    async def get_by_phone_e164(self, tenant_id: uuid.UUID, phone_e164: str) -> User | None:
        for user in self.users.values():
            if user.tenant_id == tenant_id and user.phone_number_e164 == phone_e164:
                return replace(user)
        return None

    async def update(self, user: User) -> User:
        self.users[user.id] = replace(user)
        return replace(user)


class FakeRoleRepository:
    async def get_by_name(self, name: str, *, tenant_id: uuid.UUID | None = None) -> Role | None:
        return None

    async def list_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[Role]:
        return []

    async def assign_to_user(self, assignment: object) -> object:
        return assignment


class FakeTenantRepository:
    """Empty by default — get_by_id returns None for any unregistered
    tenant_id, which UpdateUserProfileService treats the same as "not a
    Personal tenant" (skips personal_phone_logins entirely). Existing
    tests never register a tenant here, so they're unaffected; only the
    phone-login-specific tests below register one.
    """

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


class FakePersonalPhoneLoginRepository:
    def __init__(self) -> None:
        # phone_e164 -> (tenant_id, user_id)
        self.rows: dict[str, tuple[uuid.UUID, uuid.UUID]] = {}

    async def upsert(self, *, phone_e164: str, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
        existing = self.rows.get(phone_e164)
        if existing is not None and existing[1] != user_id:
            raise ConflictError(
                "This phone number is already registered to a different account.",
                code="PHONE_NUMBER_ALREADY_REGISTERED",
            )
        for number, (_, existing_user_id) in list(self.rows.items()):
            if existing_user_id == user_id:
                del self.rows[number]
        self.rows[phone_e164] = (tenant_id, user_id)

    async def get_tenant_id(self, phone_e164: str) -> uuid.UUID | None:
        row = self.rows.get(phone_e164)
        return row[0] if row else None

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        for number, (_, existing_user_id) in list(self.rows.items()):
            if existing_user_id == user_id:
                del self.rows[number]


class FakePlatformAdminRepository:
    """Mirrors the real repository's upsert-by-(tenant_id, user_id)
    shape closely enough to exercise UpdateUserProfileService's
    full_name-refresh step — see that service's docstring comment for
    why this exists (platform_admins.full_name is a snapshot that would
    otherwise go stale on a salutation/name change)."""

    def __init__(self) -> None:
        self.grants: dict[tuple[uuid.UUID, uuid.UUID], PlatformAdminGrant] = {}

    async def get_for_user(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID
    ) -> PlatformAdminGrant | None:
        grant = self.grants.get((tenant_id, user_id))
        return replace(grant) if grant else None

    async def get_by_id(self, grant_id: uuid.UUID) -> PlatformAdminGrant | None:
        for grant in self.grants.values():
            if grant.id == grant_id:
                return replace(grant)
        return None

    async def list_all(self) -> list[PlatformAdminGrant]:
        return [replace(g) for g in self.grants.values()]

    async def count_with_permission(self, permission_code: str) -> int:
        return sum(1 for g in self.grants.values() if permission_code in g.permission_codes)

    async def upsert(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        email: str,
        full_name: str,
        subdomain: str,
        permission_codes: frozenset[str],
        granted_by_user_id: uuid.UUID,
    ) -> PlatformAdminGrant:
        existing = self.grants.get((tenant_id, user_id))
        grant = PlatformAdminGrant(
            id=existing.id if existing else uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            email=email,
            full_name=full_name,
            subdomain=subdomain,
            permission_codes=permission_codes,
            granted_at=existing.granted_at if existing else datetime.now(UTC),
            granted_by_user_id=granted_by_user_id,
        )
        self.grants[(tenant_id, user_id)] = grant
        return replace(grant)

    async def delete(self, grant_id: uuid.UUID) -> None:
        self.grants = {k: v for k, v in self.grants.items() if v.id != grant_id}


def _make_tenant(*, tenant_id: uuid.UUID, subdomain: str) -> Tenant:
    now = datetime.now(UTC)
    return Tenant(
        id=tenant_id,
        name="Test Tenant",
        subdomain=subdomain,
        plan_tier="free",
        status="active",
        created_at=now,
        updated_at=now,
    )


def _make_user(*, tenant_id: uuid.UUID, user_id: uuid.UUID) -> User:
    now = datetime.now(UTC)
    return User(
        id=user_id,
        tenant_id=tenant_id,
        org_id=None,
        email="jordan@example.com",
        salutation="Dr.",
        first_name="First",
        last_name="Last",
        hashed_password="hashed",
        status="active",
        mfa_enabled=False,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def service() -> tuple[UpdateUserProfileService, FakeUserRepository]:
    users = FakeUserRepository()
    svc = UpdateUserProfileService(
        users,
        FakeRoleRepository(),
        FakeTenantRepository(),
        FakePersonalPhoneLoginRepository(),
        FakePlatformAdminRepository(),
    )
    return svc, users


@pytest.mark.unit
class TestUpdateUserProfile:
    async def test_updates_name_and_salutation(self, service) -> None:
        svc, users = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        await users.create(_make_user(tenant_id=tenant_id, user_id=user_id))

        result = await svc.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            salutation="Ms.",
            first_name="Jordan",
            last_name="Rivera",
            phone_number=None,
            country=None,
            language=None,
            address_line1=None,
            address_line2=None,
            city=None,
            state=None,
            postal_code=None,
            visa_status=None,
            linkedin_url=None,
            other_professional_url=None,
        )

        assert result.first_name == "Jordan"
        assert result.last_name == "Rivera"
        assert result.salutation == "Ms."
        assert result.full_name == "Ms. Jordan Rivera"

    async def test_blank_salutation_is_stored_as_none(self, service) -> None:
        svc, users = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        await users.create(_make_user(tenant_id=tenant_id, user_id=user_id))

        result = await svc.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            salutation="   ",
            first_name="Jordan",
            last_name="Rivera",
            phone_number=None,
            country=None,
            language=None,
            address_line1=None,
            address_line2=None,
            city=None,
            state=None,
            postal_code=None,
            visa_status=None,
            linkedin_url=None,
            other_professional_url=None,
        )

        assert result.salutation is None
        assert result.full_name == "Jordan Rivera"

    async def test_trims_whitespace(self, service) -> None:
        svc, users = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        await users.create(_make_user(tenant_id=tenant_id, user_id=user_id))

        result = await svc.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            salutation=None,
            first_name="  Jordan  ",
            last_name="  Rivera  ",
            phone_number=None,
            country=None,
            language=None,
            address_line1=None,
            address_line2=None,
            city=None,
            state=None,
            postal_code=None,
            visa_status=None,
            linkedin_url=None,
            other_professional_url=None,
        )

        assert result.first_name == "Jordan"
        assert result.last_name == "Rivera"

    async def test_rejects_blank_first_name(self, service) -> None:
        svc, users = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        await users.create(_make_user(tenant_id=tenant_id, user_id=user_id))

        with pytest.raises(ValidationError) as exc_info:
            await svc.execute(
                tenant_id=tenant_id,
                user_id=user_id,
                salutation=None,
                first_name="   ",
                last_name="Rivera",
                phone_number=None,
                country=None,
                language=None,
                address_line1=None,
                address_line2=None,
                city=None,
                state=None,
                postal_code=None,
                visa_status=None,
                linkedin_url=None,
                other_professional_url=None,
            )

        assert exc_info.value.code == "NAME_REQUIRED"

    async def test_rejects_blank_last_name(self, service) -> None:
        svc, users = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        await users.create(_make_user(tenant_id=tenant_id, user_id=user_id))

        with pytest.raises(ValidationError) as exc_info:
            await svc.execute(
                tenant_id=tenant_id,
                user_id=user_id,
                salutation=None,
                first_name="Jordan",
                last_name="",
                phone_number=None,
                country=None,
                language=None,
                address_line1=None,
                address_line2=None,
                city=None,
                state=None,
                postal_code=None,
                visa_status=None,
                linkedin_url=None,
                other_professional_url=None,
            )

        assert exc_info.value.code == "NAME_REQUIRED"

    async def test_raises_not_found_for_unknown_user(self, service) -> None:
        svc, _ = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()

        with pytest.raises(NotFoundError) as exc_info:
            await svc.execute(
                tenant_id=tenant_id,
                user_id=user_id,
                salutation=None,
                first_name="Jordan",
                last_name="Rivera",
                phone_number=None,
                country=None,
                language=None,
                address_line1=None,
                address_line2=None,
                city=None,
                state=None,
                postal_code=None,
                visa_status=None,
                linkedin_url=None,
                other_professional_url=None,
            )

        assert exc_info.value.code == "USER_NOT_FOUND"

    async def test_a_user_cannot_update_another_tenants_user(self, service) -> None:
        svc, users = service
        tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
        user_id = uuid.uuid4()
        await users.create(_make_user(tenant_id=tenant_a, user_id=user_id))

        with pytest.raises(NotFoundError):
            await svc.execute(
                tenant_id=tenant_b,
                user_id=user_id,
                salutation=None,
                first_name="Hijacked",
                last_name="Name",
                phone_number=None,
                country=None,
                language=None,
                address_line1=None,
                address_line2=None,
                city=None,
                state=None,
                postal_code=None,
                visa_status=None,
                linkedin_url=None,
                other_professional_url=None,
            )


@pytest.mark.unit
class TestPhoneNumber:
    async def test_updates_phone_number(self, service) -> None:
        svc, users = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        await users.create(_make_user(tenant_id=tenant_id, user_id=user_id))

        result = await svc.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            salutation=None,
            first_name="Jordan",
            last_name="Rivera",
            phone_number="+1 (555) 123-4567",
            country=None,
            language=None,
            address_line1=None,
            address_line2=None,
            city=None,
            state=None,
            postal_code=None,
            visa_status=None,
            linkedin_url=None,
            other_professional_url=None,
        )

        assert result.phone_number == "+1 (555) 123-4567"

    async def test_blank_phone_number_is_stored_as_none(self, service) -> None:
        svc, users = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        await users.create(_make_user(tenant_id=tenant_id, user_id=user_id))
        await svc.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            salutation=None,
            first_name="Jordan",
            last_name="Rivera",
            phone_number="+1 555 123 4567",
            country=None,
            language=None,
            address_line1=None,
            address_line2=None,
            city=None,
            state=None,
            postal_code=None,
            visa_status=None,
            linkedin_url=None,
            other_professional_url=None,
        )

        result = await svc.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            salutation=None,
            first_name="Jordan",
            last_name="Rivera",
            phone_number="   ",
            country=None,
            language=None,
            address_line1=None,
            address_line2=None,
            city=None,
            state=None,
            postal_code=None,
            visa_status=None,
            linkedin_url=None,
            other_professional_url=None,
        )

        assert result.phone_number is None

    async def test_trims_whitespace(self, service) -> None:
        svc, users = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        await users.create(_make_user(tenant_id=tenant_id, user_id=user_id))

        result = await svc.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            salutation=None,
            first_name="Jordan",
            last_name="Rivera",
            phone_number="  +1 555 123 4567  ",
            country=None,
            language=None,
            address_line1=None,
            address_line2=None,
            city=None,
            state=None,
            postal_code=None,
            visa_status=None,
            linkedin_url=None,
            other_professional_url=None,
        )

        assert result.phone_number == "+1 555 123 4567"


@pytest.mark.unit
class TestCountryLanguage:
    async def test_updates_country_language(self, service) -> None:
        svc, users = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        await users.create(_make_user(tenant_id=tenant_id, user_id=user_id))

        result = await svc.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            salutation=None,
            first_name="Jordan",
            last_name="Rivera",
            phone_number=None,
            country="us",
            language="en-US",
            address_line1=None,
            address_line2=None,
            city=None,
            state=None,
            postal_code=None,
            visa_status=None,
            linkedin_url=None,
            other_professional_url=None,
        )

        assert result.country == "US"
        assert result.language == "en-US"

    async def test_blank_fields_are_stored_as_none(self, service) -> None:
        svc, users = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        await users.create(_make_user(tenant_id=tenant_id, user_id=user_id))
        await svc.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            salutation=None,
            first_name="Jordan",
            last_name="Rivera",
            phone_number=None,
            country="US",
            language="en",
            address_line1=None,
            address_line2=None,
            city=None,
            state=None,
            postal_code=None,
            visa_status=None,
            linkedin_url=None,
            other_professional_url=None,
        )

        result = await svc.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            salutation=None,
            first_name="Jordan",
            last_name="Rivera",
            phone_number=None,
            country="   ",
            language="   ",
            address_line1=None,
            address_line2=None,
            city=None,
            state=None,
            postal_code=None,
            visa_status=None,
            linkedin_url=None,
            other_professional_url=None,
        )

        assert result.country is None
        assert result.language is None

    async def test_trims_and_uppercases_country(self, service) -> None:
        svc, users = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        await users.create(_make_user(tenant_id=tenant_id, user_id=user_id))

        result = await svc.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            salutation=None,
            first_name="Jordan",
            last_name="Rivera",
            phone_number=None,
            country="  gb  ",
            language=None,
            address_line1=None,
            address_line2=None,
            city=None,
            state=None,
            postal_code=None,
            visa_status=None,
            linkedin_url=None,
            other_professional_url=None,
        )

        assert result.country == "GB"

    async def test_rejects_invalid_country_code(self, service) -> None:
        svc, users = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        await users.create(_make_user(tenant_id=tenant_id, user_id=user_id))

        with pytest.raises(ValidationError) as exc_info:
            await svc.execute(
                tenant_id=tenant_id,
                user_id=user_id,
                salutation=None,
                first_name="Jordan",
                last_name="Rivera",
                phone_number=None,
                country="USA",
                language=None,
                address_line1=None,
                address_line2=None,
                city=None,
                state=None,
                postal_code=None,
                visa_status=None,
                linkedin_url=None,
                other_professional_url=None,
            )

        assert exc_info.value.code == "INVALID_COUNTRY"

    async def test_rejects_non_alphabetic_country_code(self, service) -> None:
        svc, users = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        await users.create(_make_user(tenant_id=tenant_id, user_id=user_id))

        with pytest.raises(ValidationError) as exc_info:
            await svc.execute(
                tenant_id=tenant_id,
                user_id=user_id,
                salutation=None,
                first_name="Jordan",
                last_name="Rivera",
                phone_number=None,
                country="U1",
                language=None,
                address_line1=None,
                address_line2=None,
                city=None,
                state=None,
                postal_code=None,
                visa_status=None,
                linkedin_url=None,
                other_professional_url=None,
            )

        assert exc_info.value.code == "INVALID_COUNTRY"


@pytest.mark.unit
class TestStructuredAddress:
    async def test_updates_all_address_fields(self, service) -> None:
        svc, users = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        await users.create(_make_user(tenant_id=tenant_id, user_id=user_id))

        result = await svc.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            salutation=None,
            first_name="Jordan",
            last_name="Rivera",
            phone_number=None,
            country="US",
            language=None,
            address_line1="123 Main St",
            address_line2="Apt 4B",
            city="Springfield",
            state="IL",
            postal_code="62701",
            visa_status=None,
            linkedin_url=None,
            other_professional_url=None,
        )

        assert result.address_line1 == "123 Main St"
        assert result.address_line2 == "Apt 4B"
        assert result.city == "Springfield"
        assert result.state == "IL"
        assert result.postal_code == "62701"

    async def test_blank_address_fields_are_stored_as_none(self, service) -> None:
        svc, users = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        await users.create(_make_user(tenant_id=tenant_id, user_id=user_id))
        await svc.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            salutation=None,
            first_name="Jordan",
            last_name="Rivera",
            phone_number=None,
            country=None,
            language=None,
            address_line1="123 Main St",
            address_line2="Apt 4B",
            city="Springfield",
            state="IL",
            postal_code="62701",
            visa_status=None,
            linkedin_url=None,
            other_professional_url=None,
        )

        result = await svc.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            salutation=None,
            first_name="Jordan",
            last_name="Rivera",
            phone_number=None,
            country=None,
            language=None,
            address_line1="   ",
            address_line2="   ",
            city="   ",
            state="   ",
            postal_code="   ",
            visa_status=None,
            linkedin_url=None,
            other_professional_url=None,
        )

        assert result.address_line1 is None
        assert result.address_line2 is None
        assert result.city is None
        assert result.state is None
        assert result.postal_code is None

    async def test_trims_whitespace(self, service) -> None:
        svc, users = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        await users.create(_make_user(tenant_id=tenant_id, user_id=user_id))

        result = await svc.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            salutation=None,
            first_name="Jordan",
            last_name="Rivera",
            phone_number=None,
            country=None,
            language=None,
            address_line1="  123 Main St  ",
            address_line2=None,
            city="  Springfield  ",
            state=None,
            postal_code="  62701  ",
            visa_status=None,
            linkedin_url=None,
            other_professional_url=None,
        )

        assert result.address_line1 == "123 Main St"
        assert result.city == "Springfield"
        assert result.postal_code == "62701"

    async def test_address_line2_is_optional(self, service) -> None:
        svc, users = service
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        await users.create(_make_user(tenant_id=tenant_id, user_id=user_id))

        result = await svc.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            salutation=None,
            first_name="Jordan",
            last_name="Rivera",
            phone_number=None,
            country=None,
            language=None,
            address_line1="123 Main St",
            address_line2=None,
            city="Springfield",
            state=None,
            postal_code="62701",
            visa_status=None,
            linkedin_url=None,
            other_professional_url=None,
        )

        assert result.address_line1 == "123 Main St"
        assert result.address_line2 is None


@pytest.mark.unit
class TestPersonalPhoneLoginLookup:
    """personal_phone_logins is only maintained for Personal (p-prefixed
    subdomain) tenants — see is_personal_subdomain. Enterprise tenants
    must be completely unaffected."""

    def _service(
        self, *, tenant: Tenant | None
    ) -> tuple[
        UpdateUserProfileService, FakeUserRepository, FakePersonalPhoneLoginRepository
    ]:
        users = FakeUserRepository()
        tenants = FakeTenantRepository()
        phone_logins = FakePersonalPhoneLoginRepository()
        if tenant is not None:
            tenants.tenants[tenant.id] = tenant
        svc = UpdateUserProfileService(
            users, FakeRoleRepository(), tenants, phone_logins, FakePlatformAdminRepository()
        )
        return svc, users, phone_logins

    async def test_personal_tenant_phone_save_registers_lookup(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        tenant = _make_tenant(tenant_id=tenant_id, subdomain="p-abc123")
        svc, users, phone_logins = self._service(tenant=tenant)
        await users.create(_make_user(tenant_id=tenant_id, user_id=user_id))

        await svc.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            salutation=None,
            first_name="Jordan",
            last_name="Rivera",
            phone_number="+1 415 555 2671",
            country="US",
            language=None,
            address_line1=None,
            address_line2=None,
            city=None,
            state=None,
            postal_code=None,
            visa_status=None,
            linkedin_url=None,
            other_professional_url=None,
        )

        assert await phone_logins.get_tenant_id("+14155552671") == tenant_id

    async def test_changing_phone_replaces_old_lookup_entry(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        tenant = _make_tenant(tenant_id=tenant_id, subdomain="p-abc123")
        svc, users, phone_logins = self._service(tenant=tenant)
        await users.create(_make_user(tenant_id=tenant_id, user_id=user_id))

        common = dict(
            tenant_id=tenant_id,
            user_id=user_id,
            salutation=None,
            first_name="Jordan",
            last_name="Rivera",
            country="US",
            language=None,
            address_line1=None,
            address_line2=None,
            city=None,
            state=None,
            postal_code=None,
            visa_status=None,
            linkedin_url=None,
            other_professional_url=None,
        )
        await svc.execute(phone_number="+1 415 555 2671", **common)
        await svc.execute(phone_number="+1 415 555 0100", **common)

        assert await phone_logins.get_tenant_id("+14155552671") is None
        assert await phone_logins.get_tenant_id("+14155550100") == tenant_id

    async def test_clearing_phone_deletes_lookup_entry(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        tenant = _make_tenant(tenant_id=tenant_id, subdomain="p-abc123")
        svc, users, phone_logins = self._service(tenant=tenant)
        await users.create(_make_user(tenant_id=tenant_id, user_id=user_id))

        common = dict(
            tenant_id=tenant_id,
            user_id=user_id,
            salutation=None,
            first_name="Jordan",
            last_name="Rivera",
            country="US",
            language=None,
            address_line1=None,
            address_line2=None,
            city=None,
            state=None,
            postal_code=None,
            visa_status=None,
            linkedin_url=None,
            other_professional_url=None,
        )
        await svc.execute(phone_number="+1 415 555 2671", **common)
        await svc.execute(phone_number=None, **common)

        assert await phone_logins.get_tenant_id("+14155552671") is None

    async def test_enterprise_tenant_phone_save_does_not_register_lookup(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        tenant = _make_tenant(tenant_id=tenant_id, subdomain="acme")
        svc, users, phone_logins = self._service(tenant=tenant)
        await users.create(_make_user(tenant_id=tenant_id, user_id=user_id))

        await svc.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            salutation=None,
            first_name="Jordan",
            last_name="Rivera",
            phone_number="+1 415 555 2671",
            country="US",
            language=None,
            address_line1=None,
            address_line2=None,
            city=None,
            state=None,
            postal_code=None,
            visa_status=None,
            linkedin_url=None,
            other_professional_url=None,
        )

        assert await phone_logins.get_tenant_id("+14155552671") is None

    async def test_phone_already_claimed_by_a_different_user_raises_conflict(self) -> None:
        tenant_id = uuid.uuid4()
        user_a, user_b = uuid.uuid4(), uuid.uuid4()
        tenant = _make_tenant(tenant_id=tenant_id, subdomain="p-abc123")
        svc, users, phone_logins = self._service(tenant=tenant)
        await users.create(_make_user(tenant_id=tenant_id, user_id=user_a))
        await users.create(_make_user(tenant_id=tenant_id, user_id=user_b))

        common = dict(
            tenant_id=tenant_id,
            salutation=None,
            first_name="Jordan",
            last_name="Rivera",
            phone_number="+1 415 555 2671",
            country="US",
            language=None,
            address_line1=None,
            address_line2=None,
            city=None,
            state=None,
            postal_code=None,
            visa_status=None,
            linkedin_url=None,
            other_professional_url=None,
        )
        await svc.execute(user_id=user_a, **common)

        with pytest.raises(ConflictError) as exc_info:
            await svc.execute(user_id=user_b, **common)

        assert exc_info.value.code == "PHONE_NUMBER_ALREADY_REGISTERED"
        # First user's registration is untouched by the failed attempt.
        assert await phone_logins.get_tenant_id("+14155552671") == tenant_id


@pytest.mark.unit
class TestPlatformAdminSnapshotRefresh:
    """platform_admins.full_name is a snapshot taken at grant time (see
    PlatformAdminGrant's own docstring) — without this refresh, a
    platform admin changing their own salutation/name here would leave
    the Platform Admin admins list showing stale text indefinitely."""

    def _service(
        self,
    ) -> tuple[UpdateUserProfileService, FakeUserRepository, FakePlatformAdminRepository]:
        users = FakeUserRepository()
        platform_admins = FakePlatformAdminRepository()
        svc = UpdateUserProfileService(
            users,
            FakeRoleRepository(),
            FakeTenantRepository(),
            FakePersonalPhoneLoginRepository(),
            platform_admins,
        )
        return svc, users, platform_admins

    async def test_refreshes_existing_grants_full_name(self) -> None:
        tenant_id, user_id, granter_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        svc, users, platform_admins = self._service()
        await users.create(_make_user(tenant_id=tenant_id, user_id=user_id))
        platform_admins.grants[(tenant_id, user_id)] = PlatformAdminGrant(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            email="jordan@example.com",
            full_name="Dr. First Last",
            subdomain="p-abc123",
            permission_codes=frozenset({"platform.settings.view"}),
            granted_at=datetime.now(UTC),
            granted_by_user_id=granter_id,
        )

        await svc.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            salutation=None,
            first_name="Jordan",
            last_name="Rivera",
            phone_number=None,
            country=None,
            language=None,
            address_line1=None,
            address_line2=None,
            city=None,
            state=None,
            postal_code=None,
            visa_status=None,
            linkedin_url=None,
            other_professional_url=None,
        )

        refreshed = platform_admins.grants[(tenant_id, user_id)]
        assert refreshed.full_name == "Jordan Rivera"
        # Everything else about the grant is preserved untouched.
        assert refreshed.permission_codes == frozenset({"platform.settings.view"})
        assert refreshed.subdomain == "p-abc123"
        assert refreshed.granted_by_user_id == granter_id

    async def test_no_op_when_user_is_not_a_platform_admin(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        svc, users, platform_admins = self._service()
        await users.create(_make_user(tenant_id=tenant_id, user_id=user_id))

        await svc.execute(
            tenant_id=tenant_id,
            user_id=user_id,
            salutation="Ms.",
            first_name="Jordan",
            last_name="Rivera",
            phone_number=None,
            country=None,
            language=None,
            address_line1=None,
            address_line2=None,
            city=None,
            state=None,
            postal_code=None,
            visa_status=None,
            linkedin_url=None,
            other_professional_url=None,
        )

        assert platform_admins.grants == {}
