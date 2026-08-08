"""Unit tests for UpdateUserProfileService."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.application.identity.update_user_profile import UpdateUserProfileService
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.identity.entities import Role, User


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
    return UpdateUserProfileService(users, FakeRoleRepository()), users


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
        )

        assert result.address_line1 == "123 Main St"
        assert result.address_line2 is None
