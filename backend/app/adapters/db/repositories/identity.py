"""SQLAlchemy repository implementations.

Each class implements one of the Protocol interfaces in
app/domain/identity/repositories.py, translating between ORM models
(app/adapters/db/models.py) and domain dataclasses
(app/domain/identity/entities.py). Application services never see an ORM
model directly.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.base import set_tenant_context
from app.adapters.db.models import (
    AuditEventModel,
    FeatureFlagModel,
    OrganizationModel,
    RoleModel,
    TenantModel,
    UserModel,
    UserRoleModel,
)
from app.domain.identity.entities import (
    AuditEvent,
    FeatureFlag,
    Organization,
    Role,
    Tenant,
    User,
    UserRoleAssignment,
)


def _tenant_to_domain(model: TenantModel) -> Tenant:
    return Tenant(
        id=model.id,
        name=model.name,
        subdomain=model.subdomain,
        plan_tier=model.plan_tier,
        status=model.status,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _org_to_domain(model: OrganizationModel) -> Organization:
    return Organization(
        id=model.id,
        tenant_id=model.tenant_id,
        name=model.name,
        parent_org_id=model.parent_org_id,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _user_to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        tenant_id=model.tenant_id,
        org_id=model.org_id,
        email=model.email,
        salutation=model.salutation,
        first_name=model.first_name,
        last_name=model.last_name,
        hashed_password=model.hashed_password,
        status=model.status,
        mfa_enabled=model.mfa_enabled,
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
        last_login_at=model.last_login_at,
        phone_number=model.phone_number,
        country=model.country,
        language=model.language,
        address_line1=model.address_line1,
        address_line2=model.address_line2,
        city=model.city,
        state=model.state,
        postal_code=model.postal_code,
    )


def _role_to_domain(model: RoleModel) -> Role:
    return Role(
        id=model.id,
        tenant_id=model.tenant_id,
        name=model.name,
        permission_codes=frozenset(rp.permission.code for rp in model.permissions),
    )


def _audit_event_to_domain(model: AuditEventModel) -> AuditEvent:
    return AuditEvent(
        id=model.id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        action=model.action,
        resource_type=model.resource_type,
        resource_id=model.resource_id,
        occurred_at=model.occurred_at,
        metadata=model.event_metadata,
        ip_address=model.ip_address,
    )


def _feature_flag_to_domain(model: FeatureFlagModel) -> FeatureFlag:
    return FeatureFlag(
        id=model.id,
        tenant_id=model.tenant_id,
        key=model.key,
        enabled=model.enabled,
        config=model.config,
    )


class SqlAlchemyTenantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, tenant: Tenant) -> Tenant:
        model = TenantModel(
            id=tenant.id,
            name=tenant.name,
            subdomain=tenant.subdomain,
            plan_tier=tenant.plan_tier,
            status=tenant.status,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _tenant_to_domain(model)

    async def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        model = await self._session.get(TenantModel, tenant_id)
        return _tenant_to_domain(model) if model else None

    async def get_by_subdomain(self, subdomain: str) -> Tenant | None:
        result = await self._session.execute(
            select(TenantModel).where(TenantModel.subdomain == subdomain)
        )
        model = result.scalar_one_or_none()
        return _tenant_to_domain(model) if model else None


class SqlAlchemyOrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, organization: Organization) -> Organization:
        model = OrganizationModel(
            id=organization.id,
            tenant_id=organization.tenant_id,
            name=organization.name,
            parent_org_id=organization.parent_org_id,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _org_to_domain(model)

    async def get_by_id(self, tenant_id: UUID, org_id: UUID) -> Organization | None:
        result = await self._session.execute(
            select(OrganizationModel).where(
                OrganizationModel.tenant_id == tenant_id, OrganizationModel.id == org_id
            )
        )
        model = result.scalar_one_or_none()
        return _org_to_domain(model) if model else None


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user: User) -> User:
        model = UserModel(
            id=user.id,
            tenant_id=user.tenant_id,
            org_id=user.org_id,
            email=user.email,
            salutation=user.salutation,
            first_name=user.first_name,
            last_name=user.last_name,
            hashed_password=user.hashed_password,
            status=user.status,
            mfa_enabled=user.mfa_enabled,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _user_to_domain(model)

    async def get_by_id(self, tenant_id: UUID, user_id: UUID) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.tenant_id == tenant_id, UserModel.id == user_id)
        )
        model = result.scalar_one_or_none()
        return _user_to_domain(model) if model else None

    async def get_by_email(self, tenant_id: UUID, email: str) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.tenant_id == tenant_id, UserModel.email == email)
        )
        model = result.scalar_one_or_none()
        return _user_to_domain(model) if model else None

    async def update(self, user: User) -> User:
        model = await self._session.get(UserModel, user.id)
        assert model is not None, "update() called with a user id that no longer exists"
        model.salutation = user.salutation
        model.first_name = user.first_name
        model.last_name = user.last_name
        model.last_login_at = user.last_login_at
        model.phone_number = user.phone_number
        model.country = user.country
        model.language = user.language
        model.address_line1 = user.address_line1
        model.address_line2 = user.address_line2
        model.city = user.city
        model.state = user.state
        model.postal_code = user.postal_code
        await self._session.flush()
        await self._session.refresh(model)
        return _user_to_domain(model)


class SqlAlchemyRoleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_name(self, name: str, *, tenant_id: UUID | None = None) -> Role | None:
        result = await self._session.execute(
            select(RoleModel).where(RoleModel.name == name, RoleModel.tenant_id == tenant_id)
        )
        model = result.scalar_one_or_none()
        return _role_to_domain(model) if model else None

    async def list_for_user(self, tenant_id: UUID, user_id: UUID) -> list[Role]:
        result = await self._session.execute(
            select(RoleModel)
            .join(UserRoleModel, UserRoleModel.role_id == RoleModel.id)
            .where(UserRoleModel.tenant_id == tenant_id, UserRoleModel.user_id == user_id)
        )
        return [_role_to_domain(model) for model in result.scalars().all()]

    async def assign_to_user(self, assignment: UserRoleAssignment) -> UserRoleAssignment:
        model = UserRoleModel(
            id=assignment.id,
            tenant_id=assignment.tenant_id,
            user_id=assignment.user_id,
            role_id=assignment.role_id,
            org_id=assignment.org_id,
        )
        self._session.add(model)
        await self._session.flush()
        return assignment


class SqlAlchemyAuditEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, event: AuditEvent) -> AuditEvent:
        model = AuditEventModel(
            id=event.id,
            tenant_id=event.tenant_id,
            user_id=event.user_id,
            action=event.action,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            event_metadata=event.metadata,
            ip_address=event.ip_address,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _audit_event_to_domain(model)

    async def list_recent(self, tenant_id: UUID, *, limit: int = 50) -> list[AuditEvent]:
        result = await self._session.execute(
            select(AuditEventModel)
            .where(AuditEventModel.tenant_id == tenant_id)
            .order_by(AuditEventModel.occurred_at.desc())
            .limit(limit)
        )
        return [_audit_event_to_domain(model) for model in result.scalars().all()]


class SqlAlchemyFeatureFlagRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_tenant(self, tenant_id: UUID) -> list[FeatureFlag]:
        result = await self._session.execute(
            select(FeatureFlagModel).where(
                (FeatureFlagModel.tenant_id == tenant_id) | (FeatureFlagModel.tenant_id.is_(None))
            )
        )
        return [_feature_flag_to_domain(model) for model in result.scalars().all()]


class SqlAlchemyTenantContextBinder:
    """Concrete TenantContextBinder — the only place application services
    touch anything resembling SQLAlchemy, and even then only through the
    set_tenant_context helper, never the session's query API directly.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bind(self, tenant_id: UUID) -> None:
        await set_tenant_context(self._session, tenant_id)
