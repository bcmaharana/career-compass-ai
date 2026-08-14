"""Platform-admin domain entities.

Platform admin is a genuinely cross-tenant concern — unlike every other
permission in this app (see app/domain/identity/authorization.py), which
is enforced via Postgres RLS scoped to the caller's own tenant. A
PlatformAdminGrant lives in a table with no RLS at all (same shape as
personal_phone_logins), so "is this specific caller a platform admin"
can be answered directly from their own (tenant_id, user_id) without
first needing tenant context bound and without ever touching another
tenant's data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class PlatformAdminGrant:
    id: UUID
    tenant_id: UUID
    user_id: UUID
    #: Snapshot of the granted user's email/name/tenant-subdomain at
    #: grant time, so the admins list can be rendered without a
    #: cross-tenant users/tenants lookup (RLS would block that without
    #: already knowing this exact tenant_id). Refreshed whenever the
    #: grant itself is updated. subdomain also disambiguates two grants
    #: for the same email under different tenants (e.g. a Personal and
    #: an Enterprise account sharing an email) — is_personal_subdomain()
    #: on it tells Personal from Enterprise.
    email: str
    full_name: str
    subdomain: str
    permission_codes: frozenset[str]
    granted_at: datetime
    granted_by_user_id: UUID


@dataclass(slots=True)
class PlatformSetting:
    id: UUID
    key: str
    value: str
    description: str
    updated_at: datetime
    updated_by_user_id: UUID | None = None
