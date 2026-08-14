"""Resolve the current user from already-verified identity claims.

The claims themselves come from IdentityProviderInterface.verify_token,
called by the API-layer auth dependency (app/api/dependencies.py) before
this service ever runs — this service's job is purely to look up the
full user record and roles for a caller whose identity is already
established.
"""

from __future__ import annotations

from uuid import UUID

from app.application.identity.dto import CurrentUserResult
from app.core.exceptions import NotFoundError
from app.domain.identity.repositories import RoleRepository, UserRepository


class GetCurrentUserService:
    def __init__(self, users: UserRepository, roles: RoleRepository) -> None:
        self._users = users
        self._roles = roles

    async def execute(self, *, tenant_id: UUID, user_id: UUID) -> CurrentUserResult:
        user = await self._users.get_by_id(tenant_id, user_id)
        if user is None or not user.is_active:
            raise NotFoundError("User not found.", code="USER_NOT_FOUND")

        roles = await self._roles.list_for_user(tenant_id, user_id)

        return CurrentUserResult(
            user_id=user.id,
            tenant_id=user.tenant_id,
            org_id=user.org_id,
            email=user.email,
            full_name=user.display_name,
            salutation=user.salutation,
            first_name=user.first_name,
            last_name=user.last_name,
            phone_number=user.phone_number,
            country=user.country,
            language=user.language,
            address_line1=user.address_line1,
            address_line2=user.address_line2,
            city=user.city,
            state=user.state,
            postal_code=user.postal_code,
            visa_status=user.visa_status,
            linkedin_url=user.linkedin_url,
            other_professional_url=user.other_professional_url,
            roles=tuple(role.name for role in roles),
        )
