"""SQLAlchemy repository implementations for platform-admin.

Neither PlatformAdminModel nor PlatformSettingModel carries RLS (see
their module docstring in app/adapters/db/models/platform_admin.py), so
both repositories operate on a plain session — never
get_tenant_scoped_session — the same shape as
SqlAlchemyPersonalPhoneLoginRepository.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.models import PlatformAdminModel, PlatformSettingModel
from app.domain.platform_admin.entities import PlatformAdminGrant, PlatformSetting


def _grant_to_domain(model: PlatformAdminModel) -> PlatformAdminGrant:
    return PlatformAdminGrant(
        id=model.id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        email=model.email,
        full_name=model.full_name,
        subdomain=model.subdomain,
        permission_codes=frozenset(model.permission_codes),
        granted_at=model.granted_at,
        granted_by_user_id=model.granted_by_user_id,
    )


def _setting_to_domain(model: PlatformSettingModel) -> PlatformSetting:
    return PlatformSetting(
        id=model.id,
        key=model.key,
        value=model.value,
        description=model.description,
        updated_at=model.updated_at,
        updated_by_user_id=model.updated_by_user_id,
    )


class SqlAlchemyPlatformAdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_user(self, tenant_id: UUID, user_id: UUID) -> PlatformAdminGrant | None:
        result = await self._session.execute(
            select(PlatformAdminModel).where(
                PlatformAdminModel.tenant_id == tenant_id,
                PlatformAdminModel.user_id == user_id,
            )
        )
        model = result.scalar_one_or_none()
        return _grant_to_domain(model) if model else None

    async def get_by_id(self, grant_id: UUID) -> PlatformAdminGrant | None:
        model = await self._session.get(PlatformAdminModel, grant_id)
        return _grant_to_domain(model) if model else None

    async def list_all(self) -> list[PlatformAdminGrant]:
        result = await self._session.execute(
            select(PlatformAdminModel).order_by(PlatformAdminModel.granted_at)
        )
        return [_grant_to_domain(m) for m in result.scalars().all()]

    async def count_with_permission(self, permission_code: str) -> int:
        # permission_codes is a plain JSON column (not JSONB), so a
        # containment query isn't available — this table only ever holds
        # a handful of rows (one per platform admin, never per tenant),
        # so filtering in Python is genuinely cheap here, not a
        # shortcut that'll bite at scale.
        grants = await self.list_all()
        return sum(1 for g in grants if permission_code in g.permission_codes)

    async def upsert(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        email: str,
        full_name: str,
        subdomain: str,
        permission_codes: frozenset[str],
        granted_by_user_id: UUID,
    ) -> PlatformAdminGrant:
        result = await self._session.execute(
            select(PlatformAdminModel).where(
                PlatformAdminModel.tenant_id == tenant_id,
                PlatformAdminModel.user_id == user_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            model = PlatformAdminModel(
                tenant_id=tenant_id,
                user_id=user_id,
                email=email,
                full_name=full_name,
                subdomain=subdomain,
                permission_codes=sorted(permission_codes),
                granted_by_user_id=granted_by_user_id,
            )
            self._session.add(model)
        else:
            model.email = email
            model.full_name = full_name
            model.subdomain = subdomain
            model.permission_codes = sorted(permission_codes)
            model.granted_by_user_id = granted_by_user_id

        await self._session.flush()
        await self._session.refresh(model)
        return _grant_to_domain(model)

    async def delete(self, grant_id: UUID) -> None:
        await self._session.execute(
            delete(PlatformAdminModel).where(PlatformAdminModel.id == grant_id)
        )
        await self._session.flush()


class SqlAlchemyPlatformSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, key: str) -> PlatformSetting | None:
        result = await self._session.execute(
            select(PlatformSettingModel).where(PlatformSettingModel.key == key)
        )
        model = result.scalar_one_or_none()
        return _setting_to_domain(model) if model else None

    async def list_all(self) -> list[PlatformSetting]:
        result = await self._session.execute(
            select(PlatformSettingModel).order_by(PlatformSettingModel.key)
        )
        return [_setting_to_domain(m) for m in result.scalars().all()]

    async def upsert(
        self, *, key: str, value: str, description: str, updated_by_user_id: UUID | None
    ) -> PlatformSetting:
        result = await self._session.execute(
            select(PlatformSettingModel).where(PlatformSettingModel.key == key)
        )
        model = result.scalar_one_or_none()
        if model is None:
            model = PlatformSettingModel(
                key=key,
                value=value,
                description=description,
                updated_by_user_id=updated_by_user_id,
            )
            self._session.add(model)
        else:
            model.value = value
            model.description = description
            model.updated_by_user_id = updated_by_user_id

        await self._session.flush()
        await self._session.refresh(model)
        return _setting_to_domain(model)

    async def seed_if_missing(self, *, key: str, value: str, description: str) -> None:
        existing = await self.get(key)
        if existing is not None:
            return
        self._session.add(PlatformSettingModel(key=key, value=value, description=description))
        await self._session.flush()
