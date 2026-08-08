"""SQLAlchemy repository implementation for the Resume Intelligence domain.

Mirrors the mapping-function pattern established in
app/adapters/db/repositories/career_profile.py. A resume row is
write-once after creation — no update()/move().
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.models import ResumeModel
from app.domain.resume_intelligence.entities import Resume


def _resume_to_domain(model: ResumeModel) -> Resume:
    return Resume(
        id=model.id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        original_filename=model.original_filename,
        file_key=model.file_key,
        content_type=model.content_type,
        file_size_bytes=model.file_size_bytes,
        status=model.status,
        raw_text=model.raw_text,
        extracted_data=dict(model.extracted_data) if model.extracted_data is not None else None,
        error_message=model.error_message,
        created_at=model.created_at,
        updated_at=model.updated_at,
        target_role_id=model.target_role_id,
        deleted_at=model.deleted_at,
    )


class SqlAlchemyResumeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, resume: Resume) -> Resume:
        model = ResumeModel(
            id=resume.id,
            tenant_id=resume.tenant_id,
            user_id=resume.user_id,
            original_filename=resume.original_filename,
            file_key=resume.file_key,
            content_type=resume.content_type,
            file_size_bytes=resume.file_size_bytes,
            status=resume.status,
            raw_text=resume.raw_text,
            extracted_data=resume.extracted_data,
            error_message=resume.error_message,
            target_role_id=resume.target_role_id,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _resume_to_domain(model)

    async def get_by_id(self, tenant_id: UUID, resume_id: UUID) -> Resume | None:
        result = await self._session.execute(
            select(ResumeModel).where(
                ResumeModel.tenant_id == tenant_id,
                ResumeModel.id == resume_id,
                ResumeModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        return _resume_to_domain(model) if model else None

    async def list_for_user(self, tenant_id: UUID, user_id: UUID) -> list[Resume]:
        result = await self._session.execute(
            select(ResumeModel)
            .where(
                ResumeModel.tenant_id == tenant_id,
                ResumeModel.user_id == user_id,
                ResumeModel.deleted_at.is_(None),
            )
            .order_by(ResumeModel.created_at.desc())
        )
        return [_resume_to_domain(model) for model in result.scalars().all()]

    async def soft_delete(self, tenant_id: UUID, resume_id: UUID) -> None:
        result = await self._session.execute(
            select(ResumeModel).where(
                ResumeModel.tenant_id == tenant_id, ResumeModel.id == resume_id
            )
        )
        model = result.scalar_one_or_none()
        if model is not None:
            model.deleted_at = datetime.now(UTC)
            await self._session.flush()
