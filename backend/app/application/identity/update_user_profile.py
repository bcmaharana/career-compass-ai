"""Update the current user's own profile (salutation/first/last name/
phone number/country/language/structured address).

Self-service only — a user updates their own record, identified by the
already-verified identity claims the API-layer auth dependency resolved
(see app/api/dependencies.py's get_current_identity), the same trust
boundary GetCurrentUserService relies on.
"""

from __future__ import annotations

from uuid import UUID

from app.application.identity.dto import CurrentUserResult
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.identity.repositories import RoleRepository, UserRepository


class UpdateUserProfileService:
    def __init__(self, users: UserRepository, roles: RoleRepository) -> None:
        self._users = users
        self._roles = roles

    async def execute(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        salutation: str | None,
        first_name: str,
        last_name: str,
        phone_number: str | None,
        country: str | None,
        language: str | None,
        address_line1: str | None,
        address_line2: str | None,
        city: str | None,
        state: str | None,
        postal_code: str | None,
    ) -> CurrentUserResult:
        user = await self._users.get_by_id(tenant_id, user_id)
        if user is None or not user.is_active:
            raise NotFoundError("User not found.", code="USER_NOT_FOUND")

        trimmed_first = first_name.strip()
        trimmed_last = last_name.strip()
        if not trimmed_first or not trimmed_last:
            raise ValidationError(
                "First and last name are required.", code="NAME_REQUIRED"
            )

        trimmed_country = country.strip().upper() if country and country.strip() else None
        if trimmed_country is not None and (
            len(trimmed_country) != 2 or not trimmed_country.isalpha()
        ):
            raise ValidationError(
                "Country must be a 2-letter code (e.g. US, GB, IN).", code="INVALID_COUNTRY"
            )

        user.salutation = salutation.strip() if salutation and salutation.strip() else None
        user.first_name = trimmed_first
        user.last_name = trimmed_last
        # Deliberately no format validation (E.164, digit-count, etc.) —
        # free text, trimmed, blank-to-None, same permissive treatment as
        # salutation. Users worldwide enter phone numbers in wildly
        # different formats; rejecting on format would reject valid ones.
        # The frontend formats/validates against the selected country
        # using libphonenumber-js before it ever reaches here.
        user.phone_number = phone_number.strip() if phone_number and phone_number.strip() else None
        user.country = trimmed_country
        user.language = language.strip() if language and language.strip() else None
        user.address_line1 = (
            address_line1.strip() if address_line1 and address_line1.strip() else None
        )
        user.address_line2 = (
            address_line2.strip() if address_line2 and address_line2.strip() else None
        )
        user.city = city.strip() if city and city.strip() else None
        user.state = state.strip() if state and state.strip() else None
        user.postal_code = postal_code.strip() if postal_code and postal_code.strip() else None
        updated = await self._users.update(user)

        roles = await self._roles.list_for_user(tenant_id, user_id)

        return CurrentUserResult(
            user_id=updated.id,
            tenant_id=updated.tenant_id,
            org_id=updated.org_id,
            email=updated.email,
            full_name=updated.display_name,
            salutation=updated.salutation,
            first_name=updated.first_name,
            last_name=updated.last_name,
            phone_number=updated.phone_number,
            country=updated.country,
            language=updated.language,
            address_line1=updated.address_line1,
            address_line2=updated.address_line2,
            city=updated.city,
            state=updated.state,
            postal_code=updated.postal_code,
            roles=tuple(role.name for role in roles),
        )
