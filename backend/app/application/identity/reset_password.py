"""Confirm a password reset (the "set new password" step).

Unlike RequestPasswordResetService, this can be specific about invalid/
expired/already-used tokens — safe to do so since the token itself is an
unguessable, high-entropy random value, not something an attacker could
enumerate the way an email address can be.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from app.application.identity.audit_service import AuditService
from app.core.exceptions import UnauthorizedError
from app.core.security import hash_password
from app.domain.identity.repositories import (
    PasswordResetTokenRepository,
    TenantContextBinder,
    UserRepository,
)


class ResetPasswordService:
    def __init__(
        self,
        reset_tokens: PasswordResetTokenRepository,
        users: UserRepository,
        tenant_context: TenantContextBinder,
        audit: AuditService,
    ) -> None:
        self._reset_tokens = reset_tokens
        self._users = users
        self._tenant_context = tenant_context
        self._audit = audit

    async def execute(self, *, token: str, new_password: str) -> None:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        record = await self._reset_tokens.get_by_token_hash(token_hash)
        if (
            record is None
            or record.used_at is not None
            or record.expires_at < datetime.now(UTC)
        ):
            raise UnauthorizedError(
                "This reset link is invalid or has expired.", code="INVALID_RESET_TOKEN"
            )

        await self._tenant_context.bind(record.tenant_id)

        user = await self._users.get_by_id(record.tenant_id, record.user_id)
        assert user is not None, "reset token references a user that no longer exists"

        user.hashed_password = hash_password(new_password)
        await self._users.update(user)
        await self._reset_tokens.mark_used(record.id)

        await self._audit.record(
            tenant_id=record.tenant_id,
            user_id=record.user_id,
            action="password_reset.completed",
            resource_type="user",
        )
