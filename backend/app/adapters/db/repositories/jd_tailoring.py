"""SQLAlchemy repository implementations for the JD Tailoring domain.

Mirrors the mapping-function pattern established in
app/adapters/db/repositories/chat.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.models import JdTailoringMessageModel, JdTailoringSessionModel
from app.domain.jd_tailoring.entities import (
    JdTailoringMessage,
    JdTailoringMessageRole,
    JdTailoringSession,
)


def _session_to_domain(model: JdTailoringSessionModel) -> JdTailoringSession:
    return JdTailoringSession(
        id=model.id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        source_type=model.source_type,  # type: ignore[arg-type]  # DB-CHECK-constrained
        jd_text=model.jd_text,
        created_at=model.created_at,
        updated_at=model.updated_at,
        target_role_id=model.target_role_id,
        source_provider_id=model.source_provider_id,
        source_title=model.source_title,
        source_company=model.source_company,
        source_redirect_url=model.source_redirect_url,
        tailored_resume_docx_key=model.tailored_resume_docx_key,
        tailored_resume_pdf_key=model.tailored_resume_pdf_key,
        tailored_resume_content=(
            dict(model.tailored_resume_content)
            if model.tailored_resume_content is not None
            else None
        ),
        tailored_resume_status=model.tailored_resume_status,  # type: ignore[arg-type]
        tailored_resume_error=model.tailored_resume_error,
        tailored_resume_generated_at=model.tailored_resume_generated_at,
        deleted_at=model.deleted_at,
    )


def _message_to_domain(model: JdTailoringMessageModel) -> JdTailoringMessage:
    return JdTailoringMessage(
        id=model.id,
        tenant_id=model.tenant_id,
        session_id=model.session_id,
        role=JdTailoringMessageRole(model.role),
        content=model.content,
        created_at=model.created_at,
    )


class SqlAlchemyJdTailoringSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, session: JdTailoringSession) -> JdTailoringSession:
        model = JdTailoringSessionModel(
            id=session.id,
            tenant_id=session.tenant_id,
            user_id=session.user_id,
            target_role_id=session.target_role_id,
            source_type=session.source_type,
            source_provider_id=session.source_provider_id,
            source_title=session.source_title,
            source_company=session.source_company,
            source_redirect_url=session.source_redirect_url,
            jd_text=session.jd_text,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _session_to_domain(model)

    async def get_by_id(self, tenant_id: UUID, session_id: UUID) -> JdTailoringSession | None:
        result = await self._session.execute(
            select(JdTailoringSessionModel).where(
                JdTailoringSessionModel.tenant_id == tenant_id,
                JdTailoringSessionModel.id == session_id,
                JdTailoringSessionModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        return _session_to_domain(model) if model else None

    async def get_by_source_provider_id(
        self, tenant_id: UUID, user_id: UUID, provider_id: str
    ) -> JdTailoringSession | None:
        result = await self._session.execute(
            select(JdTailoringSessionModel)
            .where(
                JdTailoringSessionModel.tenant_id == tenant_id,
                JdTailoringSessionModel.user_id == user_id,
                JdTailoringSessionModel.source_provider_id == provider_id,
                JdTailoringSessionModel.deleted_at.is_(None),
            )
            .order_by(desc(JdTailoringSessionModel.created_at))
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return _session_to_domain(model) if model else None

    async def list_for_user(self, tenant_id: UUID, user_id: UUID) -> list[JdTailoringSession]:
        result = await self._session.execute(
            select(JdTailoringSessionModel)
            .where(
                JdTailoringSessionModel.tenant_id == tenant_id,
                JdTailoringSessionModel.user_id == user_id,
                JdTailoringSessionModel.deleted_at.is_(None),
            )
            .order_by(desc(JdTailoringSessionModel.created_at))
        )
        return [_session_to_domain(model) for model in result.scalars().all()]

    async def update(self, session: JdTailoringSession) -> JdTailoringSession:
        model = await self._session.get(JdTailoringSessionModel, session.id)
        assert model is not None, "update() called with a session id that no longer exists"
        model.target_role_id = session.target_role_id
        model.jd_text = session.jd_text
        model.tailored_resume_docx_key = session.tailored_resume_docx_key
        model.tailored_resume_pdf_key = session.tailored_resume_pdf_key
        model.tailored_resume_content = session.tailored_resume_content
        model.tailored_resume_status = session.tailored_resume_status
        model.tailored_resume_error = session.tailored_resume_error
        model.tailored_resume_generated_at = session.tailored_resume_generated_at
        await self._session.flush()
        await self._session.refresh(model)
        return _session_to_domain(model)

    async def soft_delete(self, tenant_id: UUID, session_id: UUID) -> None:
        result = await self._session.execute(
            select(JdTailoringSessionModel).where(
                JdTailoringSessionModel.tenant_id == tenant_id,
                JdTailoringSessionModel.id == session_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is not None:
            model.deleted_at = datetime.now(UTC)
            await self._session.flush()


class SqlAlchemyJdTailoringMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, message: JdTailoringMessage) -> JdTailoringMessage:
        model = JdTailoringMessageModel(
            id=message.id,
            tenant_id=message.tenant_id,
            session_id=message.session_id,
            role=message.role.value,
            content=message.content,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _message_to_domain(model)

    async def list_by_session(
        self, tenant_id: UUID, session_id: UUID
    ) -> list[JdTailoringMessage]:
        result = await self._session.execute(
            select(JdTailoringMessageModel)
            .where(
                JdTailoringMessageModel.tenant_id == tenant_id,
                JdTailoringMessageModel.session_id == session_id,
            )
            .order_by(JdTailoringMessageModel.created_at)
        )
        return [_message_to_domain(model) for model in result.scalars().all()]
