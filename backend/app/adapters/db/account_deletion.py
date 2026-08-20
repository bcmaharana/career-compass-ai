"""Real, permanent account (tenant) deletion.

The one place allowed to issue ordered multi-table deletes directly
against the session — same "raw session access is a deliberate, narrow
exception" precedent as set_tenant_context in app/adapters/db/base.py.
Application services never see this session-level detail.

No foreign key in this schema has ON DELETE CASCADE (confirmed live
against the real schema, not assumed) — deletion order matters and is
enforced here explicitly, children before parents. See
app/application/identity/delete_account.py's docstring for why this
approach was chosen over adding CASCADE to every FK, and for the known,
accepted edge cases (content_revisions.reviewed_by,
platform_admins.granted_by_user_id) this doesn't handle — both are
NOT NULL FKs a deleted user can be referenced by from *outside* their
own tenant, which this file's tenant-scoped deletes can't reach.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.models.ai_platform import AIInvocationModel
from app.adapters.db.models.career_profile import (
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
from app.adapters.db.models.chat import ChatConversationModel, ChatMessageModel
from app.adapters.db.models.identity import (
    AuditEventModel,
    FeatureFlagModel,
    OrganizationModel,
    PasswordResetTokenModel,
    PersonalPhoneLoginModel,
    RoleModel,
    TenantModel,
    UserModel,
    UserRoleModel,
)
from app.adapters.db.models.interview_prep import InterviewQuestionModel, InterviewTopicModel
from app.adapters.db.models.jd_tailoring import JdTailoringMessageModel, JdTailoringSessionModel
from app.adapters.db.models.job_application_tracking import (
    InterviewRoundModel,
    JobApplicationModel,
    RecruiterContactModel,
)
from app.adapters.db.models.learning_intelligence import (
    LearningItemModel,
    LearningRecommendationSetModel,
)
from app.adapters.db.models.platform_admin import PlatformAdminModel, PlatformSettingModel
from app.adapters.db.models.resume_intelligence import ResumeModel
from app.domain.identity.account_deletion import TenantDeletionArtifacts


class SqlAlchemyAccountDeletionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def delete_tenant(self, tenant_id: UUID) -> TenantDeletionArtifacts:
        """Deletes every row this tenant owns, in dependency order, and
        returns what existed in object storage for it (DB is the source
        of truth, same best-effort convention
        CareerProfileService.delete_photo already established).
        """
        profile_ids_subq = select(CareerProfileModel.id).where(
            CareerProfileModel.tenant_id == tenant_id
        )
        conversation_ids_subq = select(ChatConversationModel.id).where(
            ChatConversationModel.tenant_id == tenant_id
        )

        photo_result = await self._session.execute(
            select(CareerProfileModel.id, CareerProfileModel.photo_url).where(
                CareerProfileModel.tenant_id == tenant_id,
                CareerProfileModel.photo_url.is_not(None),
            )
        )
        profile_photos = [(row.id, row.photo_url) for row in photo_result]

        # Collect Interview Topic image keys before deleting the rows —
        # same best-effort "DB is the source of truth" convention as
        # profile_photos/resume_file_keys above.
        topic_image_result = await self._session.execute(
            select(InterviewTopicModel.image_key).where(
                InterviewTopicModel.tenant_id == tenant_id,
                InterviewTopicModel.image_key.is_not(None),
            )
        )
        interview_topic_image_keys = [
            key for key in topic_image_result.scalars().all() if key is not None
        ]

        # Collect tailored-resume file keys before deleting the rows —
        # same best-effort "DB is the source of truth" convention as
        # profile_photos/resume_file_keys/interview_topic_image_keys.
        tailored_resume_result = await self._session.execute(
            select(
                JdTailoringSessionModel.tailored_resume_docx_key,
                JdTailoringSessionModel.tailored_resume_pdf_key,
            ).where(JdTailoringSessionModel.tenant_id == tenant_id)
        )
        tailored_resume_file_keys = [
            key
            for row in tailored_resume_result
            for key in (row.tailored_resume_docx_key, row.tailored_resume_pdf_key)
            if key is not None
        ]

        # 1. Career-profile sub-entities (-> career_profiles.id)
        for model in (
            CareerHighlightModel,
            CareerProfileVersionModel,
            CertificationModel,
            EducationModel,
            ExperienceModel,
            KeyAchievementModel,
            PeerEndorsementModel,
        ):
            await self._session.execute(
                delete(model).where(model.career_profile_id.in_(profile_ids_subq))
            )

        # 2. chat_messages (-> chat_conversations.id)
        await self._session.execute(
            delete(ChatMessageModel).where(
                ChatMessageModel.conversation_id.in_(conversation_ids_subq)
            )
        )

        # 2b. jd_tailoring_messages (-> jd_tailoring_sessions.id) and
        # interview_rounds (-> job_applications.id) — neither has
        # ON DELETE CASCADE (same "no FK in this schema has CASCADE"
        # convention as chat_messages), so both must be deleted before
        # step 3 removes their parent rows below.
        jd_tailoring_session_ids_subq = select(JdTailoringSessionModel.id).where(
            JdTailoringSessionModel.tenant_id == tenant_id
        )
        await self._session.execute(
            delete(JdTailoringMessageModel).where(
                JdTailoringMessageModel.session_id.in_(jd_tailoring_session_ids_subq)
            )
        )
        job_application_ids_subq = select(JobApplicationModel.id).where(
            JobApplicationModel.tenant_id == tenant_id
        )
        await self._session.execute(
            delete(InterviewRoundModel).where(
                InterviewRoundModel.job_application_id.in_(job_application_ids_subq)
            )
        )

        # Collect resume file_keys before deleting the rows.
        result = await self._session.execute(
            select(ResumeModel.file_key).where(ResumeModel.tenant_id == tenant_id)
        )
        resume_file_keys = list(result.scalars().all())

        # 3. Direct tenant_id/user_id children. Deliberately a different
        # loop variable name than step 1's `model` — mypy infers each
        # for-loop's variable type from its own tuple, and reusing the
        # same name across two loops with different (non-overlapping)
        # model unions confuses that narrowing into a false
        # "incompatible types in assignment" error.
        for direct_model in (
            CareerProfileModel,
            ChatConversationModel,
            ResumeModel,
            AIInvocationModel,
            AuditEventModel,
            PasswordResetTokenModel,
            PersonalPhoneLoginModel,
            CareerGoalModel,
            # Both reference target_role_id — must be deleted before step 4's
            # target_roles delete below (LearningItem's FK is ON DELETE
            # SET NULL, but LearningRecommendationSet's is NOT NULL and
            # would otherwise block it, same as CareerProfile/Resume above).
            LearningItemModel,
            LearningRecommendationSetModel,
            # Deleting these cascades (ON DELETE CASCADE, a real DB-level
            # FK constraint that fires regardless of how the row is
            # deleted) to their InterviewTopicScopeTagModel/
            # InterviewQuestionScopeTagModel rows automatically — no
            # separate cleanup needed for those two tables. Order
            # relative to target_roles below isn't a hard requirement
            # (topic_id/target_role_id on the scope-tag tables are also
            # ON DELETE CASCADE), unlike LearningRecommendationSet's
            # NOT NULL FK above.
            InterviewQuestionModel,
            InterviewTopicModel,
            # All three cross-references from these are ON DELETE SET
            # NULL (target_role_id, jd_tailoring_session_id/recruiter_id,
            # same target_role_id precedent as CareerGoal/LearningItem
            # above) — order among these three and relative to
            # target_roles below doesn't matter.
            JobApplicationModel,
            JdTailoringSessionModel,
            RecruiterContactModel,
            UserRoleModel,
            PlatformAdminModel,
        ):
            await self._session.execute(
                delete(direct_model).where(direct_model.tenant_id == tenant_id)
            )

        # platform_settings.updated_by_user_id is nullable and genuinely
        # global (not tenant-owned) — clear the attribution rather than
        # deleting the setting itself, which would wrongly destroy real
        # platform config just because whoever last edited it also had
        # their account deleted.
        await self._session.execute(
            update(PlatformSettingModel)
            .where(
                PlatformSettingModel.updated_by_user_id.in_(
                    select(UserModel.id).where(UserModel.tenant_id == tenant_id)
                )
            )
            .values(updated_by_user_id=None)
        )
        # Known, accepted edge case (same shape as content_revisions.reviewed_by,
        # see this file's module docstring): platform_admins.granted_by_user_id
        # is NOT NULL — if this tenant's user granted platform-admin access to
        # a still-existing admin in a *different* tenant, deleting this
        # tenant correctly fails loudly (FK violation) rather than silently
        # leaving that grant's "granted by" attribution dangling. Not
        # expected to come up in practice at this app's admin-count scale.

        # 4. target_roles — after career_profiles/resumes (both reference
        # target_role_id) are already gone.
        await self._session.execute(
            delete(TargetRoleModel).where(TargetRoleModel.tenant_id == tenant_id)
        )

        # 5. users, organizations, and only this tenant's own roles/
        # feature_flags rows — equality against tenant_id never matches
        # the global tenant_id IS NULL rows, so those are untouched.
        await self._session.execute(delete(UserModel).where(UserModel.tenant_id == tenant_id))
        await self._session.execute(
            delete(OrganizationModel).where(OrganizationModel.tenant_id == tenant_id)
        )
        await self._session.execute(delete(RoleModel).where(RoleModel.tenant_id == tenant_id))
        await self._session.execute(
            delete(FeatureFlagModel).where(FeatureFlagModel.tenant_id == tenant_id)
        )

        # 6. tenants — last.
        await self._session.execute(delete(TenantModel).where(TenantModel.id == tenant_id))

        await self._session.flush()
        return TenantDeletionArtifacts(
            resume_file_keys=resume_file_keys,
            profile_photos=profile_photos,
            interview_topic_image_keys=interview_topic_image_keys,
            tailored_resume_file_keys=tailored_resume_file_keys,
        )
