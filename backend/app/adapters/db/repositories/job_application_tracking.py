"""SQLAlchemy repository implementations for the Job Application
Tracking domain.

SqlAlchemyJobApplicationRepository's `_rounds_for_many` batches Interview
Rounds for a whole page of applications in one extra query — exact
shape as app/adapters/db/repositories/interview_prep.py's
`_follow_ups_for_many`, not N+1.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.models import (
    InterviewRoundModel,
    JobApplicationModel,
    RecruiterContactModel,
)
from app.adapters.db.reorder import Direction, move_item, next_display_order
from app.domain.job_application_tracking.entities import (
    ContactHistoryEntry,
    InterviewRound,
    JobApplication,
    RecruiterContact,
)


def _contact_history_to_domain(raw: list[dict[str, object]]) -> list[ContactHistoryEntry]:
    return [
        ContactHistoryEntry(date=date.fromisoformat(str(entry["date"])), note=str(entry["note"]))
        for entry in raw
    ]


def _contact_history_to_json(entries: list[ContactHistoryEntry]) -> list[dict[str, object]]:
    return [{"date": entry.date.isoformat(), "note": entry.note} for entry in entries]


def _recruiter_to_domain(model: RecruiterContactModel) -> RecruiterContact:
    return RecruiterContact(
        id=model.id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        name=model.name,
        created_at=model.created_at,
        updated_at=model.updated_at,
        email=model.email,
        phone=model.phone,
        company=model.company,
        linkedin_url=model.linkedin_url,
        role_title=model.role_title,
        contact_history=_contact_history_to_domain(list(model.contact_history)),
        deleted_at=model.deleted_at,
    )


def _round_to_domain(model: InterviewRoundModel) -> InterviewRound:
    return InterviewRound(
        id=model.id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        job_application_id=model.job_application_id,
        stage_label=model.stage_label,
        display_order=model.display_order,
        created_at=model.created_at,
        updated_at=model.updated_at,
        round_date=model.round_date,
        interviewer_name=model.interviewer_name,
        interviewer_title=model.interviewer_title,
        notes=model.notes,
        deleted_at=model.deleted_at,
    )


def _application_to_domain(
    model: JobApplicationModel, rounds: list[InterviewRound]
) -> JobApplication:
    return JobApplication(
        id=model.id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        company=model.company,
        role_title=model.role_title,
        status=model.status,  # type: ignore[arg-type]  # DB-CHECK-constrained
        status_changed_at=model.status_changed_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
        target_role_id=model.target_role_id,
        source_provider_id=model.source_provider_id,
        source_title=model.source_title,
        source_company=model.source_company,
        source_redirect_url=model.source_redirect_url,
        jd_tailoring_session_id=model.jd_tailoring_session_id,
        recruiter_id=model.recruiter_id,
        applied_at=model.applied_at,
        notes=model.notes,
        interview_rounds=rounds,
        deleted_at=model.deleted_at,
    )


class SqlAlchemyRecruiterContactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, contact: RecruiterContact) -> RecruiterContact:
        model = RecruiterContactModel(
            id=contact.id,
            tenant_id=contact.tenant_id,
            user_id=contact.user_id,
            name=contact.name,
            email=contact.email,
            phone=contact.phone,
            company=contact.company,
            linkedin_url=contact.linkedin_url,
            role_title=contact.role_title,
            contact_history=_contact_history_to_json(contact.contact_history),
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _recruiter_to_domain(model)

    async def get_by_id(self, tenant_id: UUID, contact_id: UUID) -> RecruiterContact | None:
        result = await self._session.execute(
            select(RecruiterContactModel).where(
                RecruiterContactModel.tenant_id == tenant_id,
                RecruiterContactModel.id == contact_id,
                RecruiterContactModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        return _recruiter_to_domain(model) if model else None

    async def list_for_user(self, tenant_id: UUID, user_id: UUID) -> list[RecruiterContact]:
        result = await self._session.execute(
            select(RecruiterContactModel)
            .where(
                RecruiterContactModel.tenant_id == tenant_id,
                RecruiterContactModel.user_id == user_id,
                RecruiterContactModel.deleted_at.is_(None),
            )
            .order_by(RecruiterContactModel.name.asc())
        )
        return [_recruiter_to_domain(model) for model in result.scalars().all()]

    async def update(self, contact: RecruiterContact) -> RecruiterContact:
        model = await self._session.get(RecruiterContactModel, contact.id)
        assert model is not None, "update() called with a contact id that no longer exists"
        model.name = contact.name
        model.email = contact.email
        model.phone = contact.phone
        model.company = contact.company
        model.linkedin_url = contact.linkedin_url
        model.role_title = contact.role_title
        model.contact_history = _contact_history_to_json(contact.contact_history)
        await self._session.flush()
        await self._session.refresh(model)
        return _recruiter_to_domain(model)

    async def soft_delete(self, tenant_id: UUID, contact_id: UUID) -> None:
        result = await self._session.execute(
            select(RecruiterContactModel).where(
                RecruiterContactModel.tenant_id == tenant_id,
                RecruiterContactModel.id == contact_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is not None:
            model.deleted_at = datetime.now(UTC)
            await self._session.flush()


class SqlAlchemyInterviewRoundRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, round_: InterviewRound) -> InterviewRound:
        order = await next_display_order(
            self._session,
            InterviewRoundModel,
            tenant_id=round_.tenant_id,
            scope_filter=InterviewRoundModel.job_application_id == round_.job_application_id,
        )
        model = InterviewRoundModel(
            id=round_.id,
            tenant_id=round_.tenant_id,
            user_id=round_.user_id,
            job_application_id=round_.job_application_id,
            stage_label=round_.stage_label,
            round_date=round_.round_date,
            interviewer_name=round_.interviewer_name,
            interviewer_title=round_.interviewer_title,
            notes=round_.notes,
            display_order=order,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _round_to_domain(model)

    async def get_by_id(self, tenant_id: UUID, round_id: UUID) -> InterviewRound | None:
        result = await self._session.execute(
            select(InterviewRoundModel).where(
                InterviewRoundModel.tenant_id == tenant_id,
                InterviewRoundModel.id == round_id,
                InterviewRoundModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        return _round_to_domain(model) if model else None

    async def update(self, round_: InterviewRound) -> InterviewRound:
        model = await self._session.get(InterviewRoundModel, round_.id)
        assert model is not None, "update() called with a round id that no longer exists"
        model.stage_label = round_.stage_label
        model.round_date = round_.round_date
        model.interviewer_name = round_.interviewer_name
        model.interviewer_title = round_.interviewer_title
        model.notes = round_.notes
        await self._session.flush()
        await self._session.refresh(model)
        return _round_to_domain(model)

    async def soft_delete(self, tenant_id: UUID, round_id: UUID) -> None:
        result = await self._session.execute(
            select(InterviewRoundModel).where(
                InterviewRoundModel.tenant_id == tenant_id, InterviewRoundModel.id == round_id
            )
        )
        model = result.scalar_one_or_none()
        if model is not None:
            model.deleted_at = datetime.now(UTC)
            await self._session.flush()

    async def move(self, tenant_id: UUID, round_id: UUID, direction: Direction) -> None:
        model = await self._session.get(InterviewRoundModel, round_id)
        if model is None:
            return
        await move_item(
            self._session,
            InterviewRoundModel,
            tenant_id=tenant_id,
            scope_filter=InterviewRoundModel.job_application_id == model.job_application_id,
            item_id=round_id,
            direction=direction,
        )


class SqlAlchemyJobApplicationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _rounds_for_many(
        self, application_ids: list[UUID]
    ) -> dict[UUID, list[InterviewRound]]:
        by_application: dict[UUID, list[InterviewRound]] = {aid: [] for aid in application_ids}
        if not application_ids:
            return by_application
        result = await self._session.execute(
            select(InterviewRoundModel)
            .where(
                InterviewRoundModel.job_application_id.in_(application_ids),
                InterviewRoundModel.deleted_at.is_(None),
            )
            .order_by(InterviewRoundModel.display_order.asc())
        )
        for model in result.scalars().all():
            by_application[model.job_application_id].append(_round_to_domain(model))
        return by_application

    async def create(self, application: JobApplication) -> JobApplication:
        model = JobApplicationModel(
            id=application.id,
            tenant_id=application.tenant_id,
            user_id=application.user_id,
            target_role_id=application.target_role_id,
            company=application.company,
            role_title=application.role_title,
            status=application.status,
            status_changed_at=application.status_changed_at,
            source_provider_id=application.source_provider_id,
            source_title=application.source_title,
            source_company=application.source_company,
            source_redirect_url=application.source_redirect_url,
            jd_tailoring_session_id=application.jd_tailoring_session_id,
            recruiter_id=application.recruiter_id,
            applied_at=application.applied_at,
            notes=application.notes,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _application_to_domain(model, [])

    async def get_by_id(self, tenant_id: UUID, application_id: UUID) -> JobApplication | None:
        result = await self._session.execute(
            select(JobApplicationModel).where(
                JobApplicationModel.tenant_id == tenant_id,
                JobApplicationModel.id == application_id,
                JobApplicationModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        rounds = await self._rounds_for_many([model.id])
        return _application_to_domain(model, rounds[model.id])

    async def get_by_source_provider_id(
        self, tenant_id: UUID, user_id: UUID, provider_id: str
    ) -> JobApplication | None:
        result = await self._session.execute(
            select(JobApplicationModel)
            .where(
                JobApplicationModel.tenant_id == tenant_id,
                JobApplicationModel.user_id == user_id,
                JobApplicationModel.source_provider_id == provider_id,
                JobApplicationModel.deleted_at.is_(None),
            )
            .order_by(desc(JobApplicationModel.created_at))
            .limit(1)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        rounds = await self._rounds_for_many([model.id])
        return _application_to_domain(model, rounds[model.id])

    async def list_for_user(self, tenant_id: UUID, user_id: UUID) -> list[JobApplication]:
        result = await self._session.execute(
            select(JobApplicationModel)
            .where(
                JobApplicationModel.tenant_id == tenant_id,
                JobApplicationModel.user_id == user_id,
                JobApplicationModel.deleted_at.is_(None),
            )
            .order_by(desc(JobApplicationModel.updated_at))
        )
        models = list(result.scalars().all())
        rounds_by_application = await self._rounds_for_many([m.id for m in models])
        return [_application_to_domain(m, rounds_by_application[m.id]) for m in models]

    async def list_tracked_provider_ids(self, tenant_id: UUID, user_id: UUID) -> set[str]:
        result = await self._session.execute(
            select(JobApplicationModel.source_provider_id).where(
                JobApplicationModel.tenant_id == tenant_id,
                JobApplicationModel.user_id == user_id,
                JobApplicationModel.source_provider_id.is_not(None),
                JobApplicationModel.deleted_at.is_(None),
            )
        )
        return {pid for pid in result.scalars().all() if pid is not None}

    async def update(self, application: JobApplication) -> JobApplication:
        model = await self._session.get(JobApplicationModel, application.id)
        assert model is not None, "update() called with an application id that no longer exists"
        model.target_role_id = application.target_role_id
        model.company = application.company
        model.role_title = application.role_title
        model.status = application.status
        model.status_changed_at = application.status_changed_at
        model.jd_tailoring_session_id = application.jd_tailoring_session_id
        model.recruiter_id = application.recruiter_id
        model.applied_at = application.applied_at
        model.notes = application.notes
        await self._session.flush()
        await self._session.refresh(model)
        rounds = await self._rounds_for_many([model.id])
        return _application_to_domain(model, rounds[model.id])

    async def soft_delete(self, tenant_id: UUID, application_id: UUID) -> None:
        result = await self._session.execute(
            select(JobApplicationModel).where(
                JobApplicationModel.tenant_id == tenant_id,
                JobApplicationModel.id == application_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is not None:
            model.deleted_at = datetime.now(UTC)
            await self._session.flush()
