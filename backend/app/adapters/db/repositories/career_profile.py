"""SQLAlchemy repository implementations for the Career Profile domain.

Mirrors the mapping-function pattern established in
app/adapters/db/repositories/identity.py: each repository translates
between its ORM model and the corresponding domain dataclass, so
application services never see an ORM model directly.

Every orderable entity's create() assigns display_order via
next_display_order() (append to the end of the list), list_for_*()
orders by display_order rather than a date column, and move() delegates
to the shared swap logic in app/adapters/db/reorder.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.models import (
    CareerGoalModel,
    CareerHighlightModel,
    CareerProfileModel,
    CareerProfileVersionModel,
    CertificationModel,
    EducationModel,
    ExperienceModel,
    KeyAchievementModel,
    PeerEndorsementModel,
    TargetRoleModel,
)
from app.adapters.db.reorder import Direction, move_item, next_display_order
from app.domain.career_profile.entities import (
    CareerGoal,
    CareerHighlight,
    CareerProfile,
    CareerProfileVersion,
    Certification,
    Education,
    Experience,
    KeyAchievement,
    PeerEndorsement,
    TargetRole,
)


def _profile_to_domain(model: CareerProfileModel) -> CareerProfile:
    return CareerProfile(
        id=model.id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        current_version=model.current_version,
        headline=model.headline,
        summary=model.summary,
        career_readiness_score=model.career_readiness_score,
        photo_url=model.photo_url,
        core_competencies=list(model.core_competencies),
        section_order=list(model.section_order) if model.section_order is not None else None,
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
    )


def _version_to_domain(model: CareerProfileVersionModel) -> CareerProfileVersion:
    return CareerProfileVersion(
        id=model.id,
        career_profile_id=model.career_profile_id,
        version_number=model.version_number,
        snapshot=model.snapshot,
        change_reason=model.change_reason,
        created_at=model.created_at,
    )


def _experience_to_domain(model: ExperienceModel) -> Experience:
    return Experience(
        id=model.id,
        tenant_id=model.tenant_id,
        career_profile_id=model.career_profile_id,
        title=model.title,
        company=model.company,
        location=model.location,
        start_date=model.start_date,
        end_date=model.end_date,
        description=model.description,
        display_order=model.display_order,
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
    )


def _education_to_domain(model: EducationModel) -> Education:
    return Education(
        id=model.id,
        tenant_id=model.tenant_id,
        career_profile_id=model.career_profile_id,
        institution=model.institution,
        degree=model.degree,
        field_of_study=model.field_of_study,
        start_date=model.start_date,
        end_date=model.end_date,
        description=model.description,
        display_order=model.display_order,
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
    )


def _certification_to_domain(model: CertificationModel) -> Certification:
    return Certification(
        id=model.id,
        tenant_id=model.tenant_id,
        career_profile_id=model.career_profile_id,
        name=model.name,
        issuing_organization=model.issuing_organization,
        issue_date=model.issue_date,
        expiration_date=model.expiration_date,
        credential_id=model.credential_id,
        credential_url=model.credential_url,
        display_order=model.display_order,
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
    )


def _goal_to_domain(model: CareerGoalModel) -> CareerGoal:
    return CareerGoal(
        id=model.id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        target_role=model.target_role,
        target_date=model.target_date,
        status=model.status,
        description=model.description,
        display_order=model.display_order,
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
    )


def _highlight_to_domain(model: CareerHighlightModel) -> CareerHighlight:
    return CareerHighlight(
        id=model.id,
        tenant_id=model.tenant_id,
        career_profile_id=model.career_profile_id,
        title=model.title,
        company=model.company,
        description=model.description,
        occurred_on=model.occurred_on,
        display_order=model.display_order,
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
    )


def _achievement_to_domain(model: KeyAchievementModel) -> KeyAchievement:
    return KeyAchievement(
        id=model.id,
        tenant_id=model.tenant_id,
        career_profile_id=model.career_profile_id,
        title=model.title,
        company=model.company,
        description=model.description,
        occurred_on=model.occurred_on,
        display_order=model.display_order,
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
    )


def _endorsement_to_domain(model: PeerEndorsementModel) -> PeerEndorsement:
    return PeerEndorsement(
        id=model.id,
        tenant_id=model.tenant_id,
        career_profile_id=model.career_profile_id,
        recommender_name=model.recommender_name,
        recommender_title=model.recommender_title,
        relationship=model.relationship,
        content=model.content,
        display_order=model.display_order,
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
    )


class SqlAlchemyCareerProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, profile: CareerProfile) -> CareerProfile:
        model = CareerProfileModel(
            id=profile.id,
            tenant_id=profile.tenant_id,
            user_id=profile.user_id,
            current_version=profile.current_version,
            headline=profile.headline,
            summary=profile.summary,
            career_readiness_score=profile.career_readiness_score,
            photo_url=profile.photo_url,
            core_competencies=profile.core_competencies,
            section_order=profile.section_order,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _profile_to_domain(model)

    async def get_by_user_id(self, tenant_id: UUID, user_id: UUID) -> CareerProfile | None:
        result = await self._session.execute(
            select(CareerProfileModel).where(
                CareerProfileModel.tenant_id == tenant_id,
                CareerProfileModel.user_id == user_id,
                CareerProfileModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        return _profile_to_domain(model) if model else None

    async def get_by_id(self, tenant_id: UUID, profile_id: UUID) -> CareerProfile | None:
        result = await self._session.execute(
            select(CareerProfileModel).where(
                CareerProfileModel.tenant_id == tenant_id,
                CareerProfileModel.id == profile_id,
                CareerProfileModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        return _profile_to_domain(model) if model else None

    async def update(self, profile: CareerProfile) -> CareerProfile:
        model = await self._session.get(CareerProfileModel, profile.id)
        assert model is not None, "update() called with a profile id that no longer exists"
        model.current_version = profile.current_version
        model.headline = profile.headline
        model.summary = profile.summary
        model.career_readiness_score = profile.career_readiness_score
        model.photo_url = profile.photo_url
        model.core_competencies = profile.core_competencies
        model.section_order = profile.section_order
        await self._session.flush()
        await self._session.refresh(model)
        return _profile_to_domain(model)


class SqlAlchemyCareerProfileVersionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, version: CareerProfileVersion) -> CareerProfileVersion:
        model = CareerProfileVersionModel(
            id=version.id,
            career_profile_id=version.career_profile_id,
            version_number=version.version_number,
            snapshot=version.snapshot,
            change_reason=version.change_reason,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _version_to_domain(model)

    async def list_for_profile(
        self, career_profile_id: UUID, *, limit: int = 50
    ) -> list[CareerProfileVersion]:
        result = await self._session.execute(
            select(CareerProfileVersionModel)
            .where(CareerProfileVersionModel.career_profile_id == career_profile_id)
            .order_by(CareerProfileVersionModel.version_number.desc())
            .limit(limit)
        )
        return [_version_to_domain(model) for model in result.scalars().all()]


class SqlAlchemyExperienceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, experience: Experience) -> Experience:
        order = await next_display_order(
            self._session,
            ExperienceModel,
            tenant_id=experience.tenant_id,
            scope_filter=ExperienceModel.career_profile_id == experience.career_profile_id,
        )
        model = ExperienceModel(
            id=experience.id,
            tenant_id=experience.tenant_id,
            career_profile_id=experience.career_profile_id,
            title=experience.title,
            company=experience.company,
            location=experience.location,
            start_date=experience.start_date,
            end_date=experience.end_date,
            description=experience.description,
            display_order=order,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _experience_to_domain(model)

    async def get_by_id(self, tenant_id: UUID, experience_id: UUID) -> Experience | None:
        result = await self._session.execute(
            select(ExperienceModel).where(
                ExperienceModel.tenant_id == tenant_id,
                ExperienceModel.id == experience_id,
                ExperienceModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        return _experience_to_domain(model) if model else None

    async def list_for_profile(self, tenant_id: UUID, career_profile_id: UUID) -> list[Experience]:
        result = await self._session.execute(
            select(ExperienceModel)
            .where(
                ExperienceModel.tenant_id == tenant_id,
                ExperienceModel.career_profile_id == career_profile_id,
                ExperienceModel.deleted_at.is_(None),
            )
            .order_by(ExperienceModel.display_order.asc())
        )
        return [_experience_to_domain(model) for model in result.scalars().all()]

    async def update(self, experience: Experience) -> Experience:
        model = await self._session.get(ExperienceModel, experience.id)
        assert model is not None, "update() called with an experience id that no longer exists"
        model.title = experience.title
        model.company = experience.company
        model.location = experience.location
        model.start_date = experience.start_date
        model.end_date = experience.end_date
        model.description = experience.description
        await self._session.flush()
        await self._session.refresh(model)
        return _experience_to_domain(model)

    async def soft_delete(self, tenant_id: UUID, experience_id: UUID) -> None:
        result = await self._session.execute(
            select(ExperienceModel).where(
                ExperienceModel.tenant_id == tenant_id, ExperienceModel.id == experience_id
            )
        )
        model = result.scalar_one_or_none()
        if model is not None:
            model.deleted_at = datetime.now(UTC)
            await self._session.flush()

    async def move(self, tenant_id: UUID, experience_id: UUID, direction: Direction) -> None:
        model = await self._session.get(ExperienceModel, experience_id)
        if model is None:
            return
        await move_item(
            self._session,
            ExperienceModel,
            tenant_id=tenant_id,
            scope_filter=ExperienceModel.career_profile_id == model.career_profile_id,
            item_id=experience_id,
            direction=direction,
        )


class SqlAlchemyEducationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, education: Education) -> Education:
        order = await next_display_order(
            self._session,
            EducationModel,
            tenant_id=education.tenant_id,
            scope_filter=EducationModel.career_profile_id == education.career_profile_id,
        )
        model = EducationModel(
            id=education.id,
            tenant_id=education.tenant_id,
            career_profile_id=education.career_profile_id,
            institution=education.institution,
            degree=education.degree,
            field_of_study=education.field_of_study,
            start_date=education.start_date,
            end_date=education.end_date,
            description=education.description,
            display_order=order,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _education_to_domain(model)

    async def get_by_id(self, tenant_id: UUID, education_id: UUID) -> Education | None:
        result = await self._session.execute(
            select(EducationModel).where(
                EducationModel.tenant_id == tenant_id,
                EducationModel.id == education_id,
                EducationModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        return _education_to_domain(model) if model else None

    async def list_for_profile(self, tenant_id: UUID, career_profile_id: UUID) -> list[Education]:
        result = await self._session.execute(
            select(EducationModel)
            .where(
                EducationModel.tenant_id == tenant_id,
                EducationModel.career_profile_id == career_profile_id,
                EducationModel.deleted_at.is_(None),
            )
            .order_by(EducationModel.display_order.asc())
        )
        return [_education_to_domain(model) for model in result.scalars().all()]

    async def update(self, education: Education) -> Education:
        model = await self._session.get(EducationModel, education.id)
        assert model is not None, "update() called with an education id that no longer exists"
        model.institution = education.institution
        model.degree = education.degree
        model.field_of_study = education.field_of_study
        model.start_date = education.start_date
        model.end_date = education.end_date
        model.description = education.description
        await self._session.flush()
        await self._session.refresh(model)
        return _education_to_domain(model)

    async def soft_delete(self, tenant_id: UUID, education_id: UUID) -> None:
        result = await self._session.execute(
            select(EducationModel).where(
                EducationModel.tenant_id == tenant_id, EducationModel.id == education_id
            )
        )
        model = result.scalar_one_or_none()
        if model is not None:
            model.deleted_at = datetime.now(UTC)
            await self._session.flush()

    async def move(self, tenant_id: UUID, education_id: UUID, direction: Direction) -> None:
        model = await self._session.get(EducationModel, education_id)
        if model is None:
            return
        await move_item(
            self._session,
            EducationModel,
            tenant_id=tenant_id,
            scope_filter=EducationModel.career_profile_id == model.career_profile_id,
            item_id=education_id,
            direction=direction,
        )


class SqlAlchemyCertificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, certification: Certification) -> Certification:
        order = await next_display_order(
            self._session,
            CertificationModel,
            tenant_id=certification.tenant_id,
            scope_filter=CertificationModel.career_profile_id == certification.career_profile_id,
        )
        model = CertificationModel(
            id=certification.id,
            tenant_id=certification.tenant_id,
            career_profile_id=certification.career_profile_id,
            name=certification.name,
            issuing_organization=certification.issuing_organization,
            issue_date=certification.issue_date,
            expiration_date=certification.expiration_date,
            credential_id=certification.credential_id,
            credential_url=certification.credential_url,
            display_order=order,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _certification_to_domain(model)

    async def get_by_id(self, tenant_id: UUID, certification_id: UUID) -> Certification | None:
        result = await self._session.execute(
            select(CertificationModel).where(
                CertificationModel.tenant_id == tenant_id,
                CertificationModel.id == certification_id,
                CertificationModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        return _certification_to_domain(model) if model else None

    async def list_for_profile(
        self, tenant_id: UUID, career_profile_id: UUID
    ) -> list[Certification]:
        result = await self._session.execute(
            select(CertificationModel)
            .where(
                CertificationModel.tenant_id == tenant_id,
                CertificationModel.career_profile_id == career_profile_id,
                CertificationModel.deleted_at.is_(None),
            )
            .order_by(CertificationModel.display_order.asc())
        )
        return [_certification_to_domain(model) for model in result.scalars().all()]

    async def update(self, certification: Certification) -> Certification:
        model = await self._session.get(CertificationModel, certification.id)
        assert model is not None, "update() called with a certification id that no longer exists"
        model.name = certification.name
        model.issuing_organization = certification.issuing_organization
        model.issue_date = certification.issue_date
        model.expiration_date = certification.expiration_date
        model.credential_id = certification.credential_id
        model.credential_url = certification.credential_url
        await self._session.flush()
        await self._session.refresh(model)
        return _certification_to_domain(model)

    async def soft_delete(self, tenant_id: UUID, certification_id: UUID) -> None:
        result = await self._session.execute(
            select(CertificationModel).where(
                CertificationModel.tenant_id == tenant_id,
                CertificationModel.id == certification_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is not None:
            model.deleted_at = datetime.now(UTC)
            await self._session.flush()

    async def move(self, tenant_id: UUID, certification_id: UUID, direction: Direction) -> None:
        model = await self._session.get(CertificationModel, certification_id)
        if model is None:
            return
        await move_item(
            self._session,
            CertificationModel,
            tenant_id=tenant_id,
            scope_filter=CertificationModel.career_profile_id == model.career_profile_id,
            item_id=certification_id,
            direction=direction,
        )


class SqlAlchemyCareerGoalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, goal: CareerGoal) -> CareerGoal:
        order = await next_display_order(
            self._session,
            CareerGoalModel,
            tenant_id=goal.tenant_id,
            scope_filter=CareerGoalModel.user_id == goal.user_id,
        )
        model = CareerGoalModel(
            id=goal.id,
            tenant_id=goal.tenant_id,
            user_id=goal.user_id,
            target_role=goal.target_role,
            target_date=goal.target_date,
            status=goal.status,
            description=goal.description,
            display_order=order,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _goal_to_domain(model)

    async def get_by_id(self, tenant_id: UUID, goal_id: UUID) -> CareerGoal | None:
        result = await self._session.execute(
            select(CareerGoalModel).where(
                CareerGoalModel.tenant_id == tenant_id,
                CareerGoalModel.id == goal_id,
                CareerGoalModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        return _goal_to_domain(model) if model else None

    async def list_for_user(self, tenant_id: UUID, user_id: UUID) -> list[CareerGoal]:
        result = await self._session.execute(
            select(CareerGoalModel)
            .where(
                CareerGoalModel.tenant_id == tenant_id,
                CareerGoalModel.user_id == user_id,
                CareerGoalModel.deleted_at.is_(None),
            )
            .order_by(CareerGoalModel.display_order.asc())
        )
        return [_goal_to_domain(model) for model in result.scalars().all()]

    async def update(self, goal: CareerGoal) -> CareerGoal:
        model = await self._session.get(CareerGoalModel, goal.id)
        assert model is not None, "update() called with a goal id that no longer exists"
        model.target_role = goal.target_role
        model.target_date = goal.target_date
        model.status = goal.status
        model.description = goal.description
        await self._session.flush()
        await self._session.refresh(model)
        return _goal_to_domain(model)

    async def soft_delete(self, tenant_id: UUID, goal_id: UUID) -> None:
        result = await self._session.execute(
            select(CareerGoalModel).where(
                CareerGoalModel.tenant_id == tenant_id, CareerGoalModel.id == goal_id
            )
        )
        model = result.scalar_one_or_none()
        if model is not None:
            model.deleted_at = datetime.now(UTC)
            await self._session.flush()

    async def move(self, tenant_id: UUID, goal_id: UUID, direction: Direction) -> None:
        model = await self._session.get(CareerGoalModel, goal_id)
        if model is None:
            return
        await move_item(
            self._session,
            CareerGoalModel,
            tenant_id=tenant_id,
            scope_filter=CareerGoalModel.user_id == model.user_id,
            item_id=goal_id,
            direction=direction,
        )


class SqlAlchemyCareerHighlightRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, highlight: CareerHighlight) -> CareerHighlight:
        order = await next_display_order(
            self._session,
            CareerHighlightModel,
            tenant_id=highlight.tenant_id,
            scope_filter=CareerHighlightModel.career_profile_id == highlight.career_profile_id,
        )
        model = CareerHighlightModel(
            id=highlight.id,
            tenant_id=highlight.tenant_id,
            career_profile_id=highlight.career_profile_id,
            title=highlight.title,
            company=highlight.company,
            description=highlight.description,
            occurred_on=highlight.occurred_on,
            display_order=order,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _highlight_to_domain(model)

    async def get_by_id(self, tenant_id: UUID, highlight_id: UUID) -> CareerHighlight | None:
        result = await self._session.execute(
            select(CareerHighlightModel).where(
                CareerHighlightModel.tenant_id == tenant_id,
                CareerHighlightModel.id == highlight_id,
                CareerHighlightModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        return _highlight_to_domain(model) if model else None

    async def list_for_profile(
        self, tenant_id: UUID, career_profile_id: UUID
    ) -> list[CareerHighlight]:
        result = await self._session.execute(
            select(CareerHighlightModel)
            .where(
                CareerHighlightModel.tenant_id == tenant_id,
                CareerHighlightModel.career_profile_id == career_profile_id,
                CareerHighlightModel.deleted_at.is_(None),
            )
            .order_by(CareerHighlightModel.display_order.asc())
        )
        return [_highlight_to_domain(model) for model in result.scalars().all()]

    async def update(self, highlight: CareerHighlight) -> CareerHighlight:
        model = await self._session.get(CareerHighlightModel, highlight.id)
        assert model is not None, "update() called with a highlight id that no longer exists"
        model.title = highlight.title
        model.company = highlight.company
        model.description = highlight.description
        model.occurred_on = highlight.occurred_on
        await self._session.flush()
        await self._session.refresh(model)
        return _highlight_to_domain(model)

    async def soft_delete(self, tenant_id: UUID, highlight_id: UUID) -> None:
        result = await self._session.execute(
            select(CareerHighlightModel).where(
                CareerHighlightModel.tenant_id == tenant_id,
                CareerHighlightModel.id == highlight_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is not None:
            model.deleted_at = datetime.now(UTC)
            await self._session.flush()

    async def move(self, tenant_id: UUID, highlight_id: UUID, direction: Direction) -> None:
        model = await self._session.get(CareerHighlightModel, highlight_id)
        if model is None:
            return
        await move_item(
            self._session,
            CareerHighlightModel,
            tenant_id=tenant_id,
            scope_filter=CareerHighlightModel.career_profile_id == model.career_profile_id,
            item_id=highlight_id,
            direction=direction,
        )


class SqlAlchemyKeyAchievementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, achievement: KeyAchievement) -> KeyAchievement:
        order = await next_display_order(
            self._session,
            KeyAchievementModel,
            tenant_id=achievement.tenant_id,
            scope_filter=KeyAchievementModel.career_profile_id == achievement.career_profile_id,
        )
        model = KeyAchievementModel(
            id=achievement.id,
            tenant_id=achievement.tenant_id,
            career_profile_id=achievement.career_profile_id,
            title=achievement.title,
            company=achievement.company,
            description=achievement.description,
            occurred_on=achievement.occurred_on,
            display_order=order,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _achievement_to_domain(model)

    async def get_by_id(self, tenant_id: UUID, achievement_id: UUID) -> KeyAchievement | None:
        result = await self._session.execute(
            select(KeyAchievementModel).where(
                KeyAchievementModel.tenant_id == tenant_id,
                KeyAchievementModel.id == achievement_id,
                KeyAchievementModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        return _achievement_to_domain(model) if model else None

    async def list_for_profile(
        self, tenant_id: UUID, career_profile_id: UUID
    ) -> list[KeyAchievement]:
        result = await self._session.execute(
            select(KeyAchievementModel)
            .where(
                KeyAchievementModel.tenant_id == tenant_id,
                KeyAchievementModel.career_profile_id == career_profile_id,
                KeyAchievementModel.deleted_at.is_(None),
            )
            .order_by(KeyAchievementModel.display_order.asc())
        )
        return [_achievement_to_domain(model) for model in result.scalars().all()]

    async def update(self, achievement: KeyAchievement) -> KeyAchievement:
        model = await self._session.get(KeyAchievementModel, achievement.id)
        assert model is not None, "update() called with an achievement id that no longer exists"
        model.title = achievement.title
        model.company = achievement.company
        model.description = achievement.description
        model.occurred_on = achievement.occurred_on
        await self._session.flush()
        await self._session.refresh(model)
        return _achievement_to_domain(model)

    async def soft_delete(self, tenant_id: UUID, achievement_id: UUID) -> None:
        result = await self._session.execute(
            select(KeyAchievementModel).where(
                KeyAchievementModel.tenant_id == tenant_id,
                KeyAchievementModel.id == achievement_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is not None:
            model.deleted_at = datetime.now(UTC)
            await self._session.flush()

    async def move(self, tenant_id: UUID, achievement_id: UUID, direction: Direction) -> None:
        model = await self._session.get(KeyAchievementModel, achievement_id)
        if model is None:
            return
        await move_item(
            self._session,
            KeyAchievementModel,
            tenant_id=tenant_id,
            scope_filter=KeyAchievementModel.career_profile_id == model.career_profile_id,
            item_id=achievement_id,
            direction=direction,
        )


class SqlAlchemyPeerEndorsementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, endorsement: PeerEndorsement) -> PeerEndorsement:
        order = await next_display_order(
            self._session,
            PeerEndorsementModel,
            tenant_id=endorsement.tenant_id,
            scope_filter=PeerEndorsementModel.career_profile_id == endorsement.career_profile_id,
        )
        model = PeerEndorsementModel(
            id=endorsement.id,
            tenant_id=endorsement.tenant_id,
            career_profile_id=endorsement.career_profile_id,
            recommender_name=endorsement.recommender_name,
            recommender_title=endorsement.recommender_title,
            relationship=endorsement.relationship,
            content=endorsement.content,
            display_order=order,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _endorsement_to_domain(model)

    async def get_by_id(self, tenant_id: UUID, endorsement_id: UUID) -> PeerEndorsement | None:
        result = await self._session.execute(
            select(PeerEndorsementModel).where(
                PeerEndorsementModel.tenant_id == tenant_id,
                PeerEndorsementModel.id == endorsement_id,
                PeerEndorsementModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        return _endorsement_to_domain(model) if model else None

    async def list_for_profile(
        self, tenant_id: UUID, career_profile_id: UUID
    ) -> list[PeerEndorsement]:
        result = await self._session.execute(
            select(PeerEndorsementModel)
            .where(
                PeerEndorsementModel.tenant_id == tenant_id,
                PeerEndorsementModel.career_profile_id == career_profile_id,
                PeerEndorsementModel.deleted_at.is_(None),
            )
            .order_by(PeerEndorsementModel.display_order.asc())
        )
        return [_endorsement_to_domain(model) for model in result.scalars().all()]

    async def update(self, endorsement: PeerEndorsement) -> PeerEndorsement:
        model = await self._session.get(PeerEndorsementModel, endorsement.id)
        assert model is not None, "update() called with an endorsement id that no longer exists"
        model.recommender_name = endorsement.recommender_name
        model.recommender_title = endorsement.recommender_title
        model.relationship = endorsement.relationship
        model.content = endorsement.content
        await self._session.flush()
        await self._session.refresh(model)
        return _endorsement_to_domain(model)

    async def soft_delete(self, tenant_id: UUID, endorsement_id: UUID) -> None:
        result = await self._session.execute(
            select(PeerEndorsementModel).where(
                PeerEndorsementModel.tenant_id == tenant_id,
                PeerEndorsementModel.id == endorsement_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is not None:
            model.deleted_at = datetime.now(UTC)
            await self._session.flush()

    async def move(self, tenant_id: UUID, endorsement_id: UUID, direction: Direction) -> None:
        model = await self._session.get(PeerEndorsementModel, endorsement_id)
        if model is None:
            return
        await move_item(
            self._session,
            PeerEndorsementModel,
            tenant_id=tenant_id,
            scope_filter=PeerEndorsementModel.career_profile_id == model.career_profile_id,
            item_id=endorsement_id,
            direction=direction,
        )


def _target_role_to_domain(model: TargetRoleModel) -> TargetRole:
    return TargetRole(
        id=model.id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        role_name=model.role_name,
        tag=model.tag,
        created_at=model.created_at,
        deleted_at=model.deleted_at,
        required_skills=list(model.required_skills),
    )


class SqlAlchemyTargetRoleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, target_role: TargetRole) -> TargetRole:
        model = TargetRoleModel(
            id=target_role.id,
            tenant_id=target_role.tenant_id,
            user_id=target_role.user_id,
            role_name=target_role.role_name,
            tag=target_role.tag,
            required_skills=target_role.required_skills,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _target_role_to_domain(model)

    async def update(self, target_role: TargetRole) -> TargetRole:
        model = await self._session.get(TargetRoleModel, target_role.id)
        assert model is not None, "update() called with a target_role id that no longer exists"
        model.role_name = target_role.role_name
        model.tag = target_role.tag
        model.required_skills = target_role.required_skills
        await self._session.flush()
        await self._session.refresh(model)
        return _target_role_to_domain(model)

    async def get_by_id(self, tenant_id: UUID, target_role_id: UUID) -> TargetRole | None:
        result = await self._session.execute(
            select(TargetRoleModel).where(
                TargetRoleModel.tenant_id == tenant_id,
                TargetRoleModel.id == target_role_id,
                TargetRoleModel.deleted_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        return _target_role_to_domain(model) if model else None

    async def list_for_user(self, tenant_id: UUID, user_id: UUID) -> list[TargetRole]:
        result = await self._session.execute(
            select(TargetRoleModel)
            .where(
                TargetRoleModel.tenant_id == tenant_id,
                TargetRoleModel.user_id == user_id,
                TargetRoleModel.deleted_at.is_(None),
            )
            .order_by(TargetRoleModel.created_at.asc())
        )
        return [_target_role_to_domain(model) for model in result.scalars().all()]

    async def soft_delete(self, tenant_id: UUID, target_role_id: UUID) -> None:
        result = await self._session.execute(
            select(TargetRoleModel).where(
                TargetRoleModel.tenant_id == tenant_id, TargetRoleModel.id == target_role_id
            )
        )
        model = result.scalar_one_or_none()
        if model is not None:
            model.deleted_at = datetime.now(UTC)
            await self._session.flush()
