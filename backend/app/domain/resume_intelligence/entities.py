"""Resume Intelligence domain entities.

Plain dataclasses — no SQLAlchemy, no Pydantic, no FastAPI. Mirrors the
pattern established in app/domain/career_profile/entities.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

# Parsing happens synchronously within the upload request (no job queue
# in this codebase — same "live computation, no batch job" call already
# made for CIKG's knowledge_quality_score). A Resume row is written once
# it has already either succeeded or failed, so there's no transient
# "uploaded"/"parsing" state to model.
ResumeStatus = str  # "parsed" | "failed"


@dataclass(slots=True)
class Resume:
    id: UUID
    tenant_id: UUID
    user_id: UUID
    original_filename: str
    file_key: str  # key in the private resumes bucket
    content_type: str
    file_size_bytes: int
    status: ResumeStatus
    raw_text: str | None
    extracted_data: dict[str, object] | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    # Optional link to one of the user's TargetRole entries (a person
    # can keep multiple resume versions, each tailored to a different
    # target role) — None means "general", not tied to any one role.
    target_role_id: UUID | None = None
    deleted_at: datetime | None = None
