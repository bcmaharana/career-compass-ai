"""SQLAlchemy repository implementations.

Each class implements one of the Protocol interfaces in
app/domain/identity/repositories.py, translating between ORM models
(app/adapters/db/models.py) and domain dataclasses
(app/domain/identity/entities.py). Application services never see an ORM
model directly.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.base import set_tenant_context
from app.adapters.db.models import (
    AuditEventModel,
    FeatureFlagModel,
    OrganizationModel,
    PasswordResetTokenModel,
    PendingSignupModel,
    PersonalPhoneLoginModel,
    RoleModel,
    TenantModel,
    UserModel,
    UserRoleModel,
)
from app.core.exceptions import ConflictError
from app.domain.identity.entities import (
    AuditEvent,
    FeatureFlag,
    Organization,
    PasswordResetToken,
    PendingSignup,
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
        platform_org_id=model.platform_org_id,
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
        phone_number_e164=model.phone_number_e164,
        country=model.country,
        language=model.language,
        address_line1=model.address_line1,
        address_line2=model.address_line2,
        city=model.city,
        state=model.state,
        postal_code=model.postal_code,
        preferred_model_version_id=model.preferred_model_version_id,
        agreed_to_terms_at=model.agreed_to_terms_at,
        terms_version=model.terms_version,
        visa_status=model.visa_status,
        linkedin_url=model.linkedin_url,
        other_professional_url=model.other_professional_url,
        job_search_location=model.job_search_location,
        job_search_max_days_old=model.job_search_max_days_old,
        job_search_distance_miles=model.job_search_distance_miles,
        job_search_employment_time=model.job_search_employment_time,
        job_search_employment_type=model.job_search_employment_type,
        middle_name=model.middle_name,
        handle=model.handle,
        platform_account_id=model.platform_account_id,
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


def _password_reset_token_to_domain(model: PasswordResetTokenModel) -> PasswordResetToken:
    return PasswordResetToken(
        id=model.id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        token_hash=model.token_hash,
        expires_at=model.expires_at,
        used_at=model.used_at,
        created_at=model.created_at,
    )


def _pending_signup_to_domain(model: PendingSignupModel) -> PendingSignup:
    return PendingSignup(
        id=model.id,
        kind=model.kind,
        email=model.email,
        hashed_password=model.hashed_password,
        first_name=model.first_name,
        last_name=model.last_name,
        tenant_name=model.tenant_name,
        subdomain=model.subdomain,
        organization_name=model.organization_name,
        token_hash=model.token_hash,
        expires_at=model.expires_at,
        created_at=model.created_at,
        agreed_to_terms_at=model.agreed_to_terms_at,
        terms_version=model.terms_version,
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
            platform_org_id=tenant.platform_org_id,
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

    async def get_by_platform_org_id(self, platform_org_id: UUID) -> Tenant | None:
        result = await self._session.execute(
            select(TenantModel).where(TenantModel.platform_org_id == platform_org_id)
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
            agreed_to_terms_at=user.agreed_to_terms_at,
            terms_version=user.terms_version,
            platform_account_id=user.platform_account_id,
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

    async def get_by_phone_e164(self, tenant_id: UUID, phone_e164: str) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(
                UserModel.tenant_id == tenant_id, UserModel.phone_number_e164 == phone_e164
            )
        )
        model = result.scalar_one_or_none()
        return _user_to_domain(model) if model else None

    async def get_by_platform_account_id(
        self, tenant_id: UUID, platform_account_id: UUID
    ) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(
                UserModel.tenant_id == tenant_id,
                UserModel.platform_account_id == platform_account_id,
            )
        )
        model = result.scalar_one_or_none()
        return _user_to_domain(model) if model else None

    async def update(self, user: User) -> User:
        model = await self._session.get(UserModel, user.id)
        assert model is not None, "update() called with a user id that no longer exists"
        model.hashed_password = user.hashed_password
        model.salutation = user.salutation
        model.first_name = user.first_name
        model.last_name = user.last_name
        model.last_login_at = user.last_login_at
        model.phone_number = user.phone_number
        model.phone_number_e164 = user.phone_number_e164
        model.country = user.country
        model.language = user.language
        model.address_line1 = user.address_line1
        model.address_line2 = user.address_line2
        model.city = user.city
        model.state = user.state
        model.postal_code = user.postal_code
        model.preferred_model_version_id = user.preferred_model_version_id
        model.visa_status = user.visa_status
        model.linkedin_url = user.linkedin_url
        model.other_professional_url = user.other_professional_url
        model.job_search_location = user.job_search_location
        model.job_search_max_days_old = user.job_search_max_days_old
        model.job_search_distance_miles = user.job_search_distance_miles
        model.job_search_employment_time = user.job_search_employment_time
        model.job_search_employment_type = user.job_search_employment_type
        model.middle_name = user.middle_name
        model.platform_account_id = user.platform_account_id
        # handle is deliberately NOT written here — see set_handle below,
        # the only path allowed to change it, since it needs savepoint
        # protection against a cross-tenant collision this RLS-scoped
        # session can't proactively see coming.
        await self._session.flush()
        await self._session.refresh(model)
        return _user_to_domain(model)

    async def set_handle(self, *, tenant_id: UUID, user_id: UUID, handle: str) -> bool:
        model = await self._session.get(UserModel, user_id)
        assert model is not None, "set_handle() called with a user id that no longer exists"
        try:
            # SAVEPOINT, not a plain flush — same reasoning as
            # SqlAlchemyCareerProfileRepository.create()'s own
            # begin_nested() usage: a plain session.rollback() on
            # IntegrityError would also discard the RLS tenant-context GUC
            # set once at session start, silently breaking RLS for every
            # later query this request makes. Rolling back only to the
            # savepoint undoes just this failed UPDATE.
            async with self._session.begin_nested():
                model.handle = handle
                await self._session.flush()
        except IntegrityError as e:
            if "uq_users_handle_lower" not in str(e.orig):
                raise
            await self._session.refresh(model)
            return False
        await self._session.refresh(model)
        return True


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


class SqlAlchemyPasswordResetTokenRepository:
    """Deliberately never filters by tenant_id in get_by_token_hash() —
    this table is RLS-exempt (see adapters/db/models/identity.py) and
    this is the pre-tenant-context lookup a confirm-reset request starts
    from, the same shape as SqlAlchemyTenantRepository.get_by_subdomain.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, token: PasswordResetToken) -> PasswordResetToken:
        model = PasswordResetTokenModel(
            id=token.id,
            tenant_id=token.tenant_id,
            user_id=token.user_id,
            token_hash=token.token_hash,
            expires_at=token.expires_at,
            used_at=token.used_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _password_reset_token_to_domain(model)

    async def get_by_token_hash(self, token_hash: str) -> PasswordResetToken | None:
        result = await self._session.execute(
            select(PasswordResetTokenModel).where(PasswordResetTokenModel.token_hash == token_hash)
        )
        model = result.scalar_one_or_none()
        return _password_reset_token_to_domain(model) if model else None

    async def invalidate_unused_for_user(self, tenant_id: UUID, user_id: UUID) -> None:
        await self._session.execute(
            update(PasswordResetTokenModel)
            .where(
                PasswordResetTokenModel.tenant_id == tenant_id,
                PasswordResetTokenModel.user_id == user_id,
                PasswordResetTokenModel.used_at.is_(None),
            )
            .values(used_at=func.now())
        )
        await self._session.flush()

    async def mark_used(self, token_id: UUID) -> None:
        await self._session.execute(
            update(PasswordResetTokenModel)
            .where(PasswordResetTokenModel.id == token_id)
            .values(used_at=func.now())
        )
        await self._session.flush()


class SqlAlchemyPendingSignupRepository:
    """Deliberately never filters by tenant_id in get_by_token_hash() —
    no tenant exists yet for a pending signup at all, the same
    RLS-exempt shape as SqlAlchemyPasswordResetTokenRepository.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, signup: PendingSignup) -> PendingSignup:
        model = PendingSignupModel(
            id=signup.id,
            kind=signup.kind,
            email=signup.email,
            hashed_password=signup.hashed_password,
            first_name=signup.first_name,
            last_name=signup.last_name,
            tenant_name=signup.tenant_name,
            subdomain=signup.subdomain,
            organization_name=signup.organization_name,
            token_hash=signup.token_hash,
            expires_at=signup.expires_at,
            agreed_to_terms_at=signup.agreed_to_terms_at,
            terms_version=signup.terms_version,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _pending_signup_to_domain(model)

    async def get_by_token_hash(self, token_hash: str) -> PendingSignup | None:
        result = await self._session.execute(
            select(PendingSignupModel).where(PendingSignupModel.token_hash == token_hash)
        )
        model = result.scalar_one_or_none()
        return _pending_signup_to_domain(model) if model else None

    async def delete(self, signup_id: UUID) -> None:
        await self._session.execute(
            delete(PendingSignupModel).where(PendingSignupModel.id == signup_id)
        )
        await self._session.flush()

    async def delete_all_for_email(self, email: str) -> None:
        await self._session.execute(
            delete(PendingSignupModel).where(PendingSignupModel.email == email)
        )
        await self._session.flush()


class SqlAlchemyPersonalPhoneLoginRepository:
    """Deliberately never filters by tenant_id — this table is the
    RLS-exempt cross-tenant lookup Personal phone login resolves through
    before any tenant context exists, the same shape as
    SqlAlchemyPendingSignupRepository/SqlAlchemyPasswordResetTokenRepository.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, *, phone_e164: str, tenant_id: UUID, user_id: UUID) -> None:
        result = await self._session.execute(
            select(PersonalPhoneLoginModel).where(
                PersonalPhoneLoginModel.phone_number_e164 == phone_e164
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None and existing.user_id != user_id:
            raise ConflictError(
                "This phone number is already registered to a different account.",
                code="PHONE_NUMBER_ALREADY_REGISTERED",
            )

        # Remove any prior number registered for this user (it may
        # differ from phone_e164, e.g. the user just changed it) before
        # inserting the new row — phone_number_e164 is the primary key,
        # so a plain re-insert without this would leave a stale row
        # behind under the old number rather than replacing it.
        await self._session.execute(
            delete(PersonalPhoneLoginModel).where(PersonalPhoneLoginModel.user_id == user_id)
        )
        self._session.add(
            PersonalPhoneLoginModel(
                phone_number_e164=phone_e164, tenant_id=tenant_id, user_id=user_id
            )
        )
        await self._session.flush()

    async def get_tenant_id(self, phone_e164: str) -> UUID | None:
        result = await self._session.execute(
            select(PersonalPhoneLoginModel.tenant_id).where(
                PersonalPhoneLoginModel.phone_number_e164 == phone_e164
            )
        )
        return result.scalar_one_or_none()

    async def delete_for_user(self, user_id: UUID) -> None:
        await self._session.execute(
            delete(PersonalPhoneLoginModel).where(PersonalPhoneLoginModel.user_id == user_id)
        )
        await self._session.flush()


class SqlAlchemyTenantContextBinder:
    """Concrete TenantContextBinder — the only place application services
    touch anything resembling SQLAlchemy, and even then only through the
    set_tenant_context helper, never the session's query API directly.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bind(self, tenant_id: UUID) -> None:
        await set_tenant_context(self._session, tenant_id)
