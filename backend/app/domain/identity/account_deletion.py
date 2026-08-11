"""Real, permanent account (tenant) deletion — domain-layer contract.

The actual multi-table delete lives in
app/adapters/db/account_deletion.py (SqlAlchemyAccountDeletionRepository)
— this module only defines the Protocol and the plain data shape it
returns, so app/application/identity/delete_account.py depends on an
interface, not SQLAlchemy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TenantDeletionArtifacts:
    """What existed in object storage for a tenant, collected before the
    DB rows referencing it are deleted — the caller (application layer)
    cleans these up from S3 afterward, same "DB is the source of truth,
    a storage-side failure shouldn't block deletion" best-effort
    convention CareerProfileService.delete_photo already established.
    """

    resume_file_keys: list[str]
    #: (career_profile_id, photo_url) for every profile row (Master and
    #: any Target Role Profiles) that had a photo set.
    profile_photos: list[tuple[UUID, str]]


class AccountDeletionRepository(Protocol):
    async def delete_tenant(self, tenant_id: UUID) -> TenantDeletionArtifacts: ...
