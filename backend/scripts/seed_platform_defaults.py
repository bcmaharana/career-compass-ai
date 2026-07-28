"""Seed global (tenant_id = NULL) permissions and roles.

Idempotent — safe to run multiple times (checks for existing rows by
unique code/name before inserting). Run after migrations, before the
first tenant registers:

    python scripts/seed_platform_defaults.py

Permissions and roles are deliberately not created via Alembic data
migrations here — schema changes (tables, columns, RLS policies) go
through Alembic; reference data that might reasonably be adjusted per
environment (e.g. a staging environment wanting an extra test role)
lives in a seed script instead. If this list grows to need review/audit
history of its own, revisit as an Alembic data migration then.
"""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.base import async_session_factory
from app.adapters.db.models import PermissionModel, RoleModel, RolePermissionModel
from app.core.logging import get_logger

logger = get_logger(__name__)

PERMISSIONS: list[tuple[str, str]] = [
    ("user:read", "View users within the tenant."),
    ("user:write", "Create, update, or deactivate users within the tenant."),
    ("org:read", "View organizations/departments/teams within the tenant."),
    ("org:write", "Create or update organizations/departments/teams within the tenant."),
    ("role:read", "View roles and their assigned permissions."),
    ("role:assign", "Assign or revoke roles for a user."),
    ("audit_event:read", "View the tenant's audit event history."),
    ("feature_flag:read", "View feature flags visible to the tenant."),
]

# name -> permission codes granted
ROLES: dict[str, list[str]] = {
    "platform_admin": [code for code, _ in PERMISSIONS],  # all permissions
    "organization_admin": [
        "user:read",
        "user:write",
        "org:read",
        "org:write",
        "role:read",
        "role:assign",
        "audit_event:read",
        "feature_flag:read",
    ],
    "manager": ["user:read", "org:read"],
    "career_coach": ["user:read"],
    "employee": ["user:read"],
    "ai_service_account": [],
}


async def _seed_permissions(session: AsyncSession) -> dict[str, uuid.UUID]:
    code_to_id: dict[str, uuid.UUID] = {}
    for code, description in PERMISSIONS:
        result = await session.execute(select(PermissionModel).where(PermissionModel.code == code))
        existing = result.scalar_one_or_none()
        if existing is not None:
            code_to_id[code] = existing.id
            continue

        model = PermissionModel(id=uuid.uuid4(), code=code, description=description)
        session.add(model)
        await session.flush()
        code_to_id[code] = model.id
        logger.info("seeded_permission", code=code)

    return code_to_id


async def _seed_roles(session: AsyncSession, permission_ids_by_code: dict[str, uuid.UUID]) -> None:
    for role_name, permission_codes in ROLES.items():
        result = await session.execute(
            select(RoleModel).where(RoleModel.name == role_name, RoleModel.tenant_id.is_(None))
        )
        role = result.scalar_one_or_none()
        if role is None:
            role = RoleModel(id=uuid.uuid4(), tenant_id=None, name=role_name)
            session.add(role)
            await session.flush()
            logger.info("seeded_role", name=role_name)

        # Queried directly rather than via role.permissions (the ORM
        # relationship) — accessing that collection lazily on a
        # freshly-flushed object hit a MissingGreenlet error in practice
        # against the real async engine. A direct query sidesteps the
        # relationship-loading-strategy question entirely and is no less
        # correct for this idempotency check.
        existing_result = await session.execute(
            select(RolePermissionModel.permission_id).where(RolePermissionModel.role_id == role.id)
        )
        existing_permission_ids = set(existing_result.scalars().all())

        for code in permission_codes:
            permission_id = permission_ids_by_code[code]
            if permission_id in existing_permission_ids:
                continue
            session.add(RolePermissionModel(role_id=role.id, permission_id=permission_id))
            logger.info("seeded_role_permission", role=role_name, permission=code)


async def seed_platform_defaults() -> None:
    async with async_session_factory() as session:
        permission_ids_by_code = await _seed_permissions(session)
        await _seed_roles(session, permission_ids_by_code)
        await session.commit()
    logger.info("seed_complete")


if __name__ == "__main__":
    asyncio.run(seed_platform_defaults())
