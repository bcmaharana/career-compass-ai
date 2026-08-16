"""ORM models, organized one module per domain.

`from app.adapters.db.models import UserModel` (and every other existing
import site) keeps working unchanged — this package re-exports every
model from its domain submodule, so splitting identity.py out of a
single models.py file is invisible to callers.

New domains add a new submodule here (e.g. career_profile.py) and add
its re-exports below — never grow identity.py to hold unrelated tables.
"""

from app.adapters.db.models.ai_platform import (
    AIInvocationModel,
    ModelVersionModel,
    PromptVersionModel,
)
from app.adapters.db.models.career_intelligence import (
    CategoryParentModel,
    CikgRoleModel,
    CompetencyModel,
    PrerequisiteOfEdgeModel,
    RelatedSkillModel,
    RoleProgressesToEdgeModel,
    RoleRequiredSkillModel,
    SkillAliasModel,
    SkillCategoryMembershipModel,
    SkillCategoryModel,
    SkillCompetencyMembershipModel,
    SkillModel,
    SpecializesEdgeModel,
    SynonymOfEdgeModel,
)
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
from app.adapters.db.models.governance import ContentHistoryModel, ContentRevisionModel
from app.adapters.db.models.identity import (
    AuditEventModel,
    FeatureFlagModel,
    OrganizationModel,
    PasswordResetTokenModel,
    PendingSignupModel,
    PermissionModel,
    PersonalPhoneLoginModel,
    RoleModel,
    RolePermissionModel,
    TenantModel,
    UserModel,
    UserRoleModel,
)
from app.adapters.db.models.learning_intelligence import (
    LearningItemModel,
    LearningRecommendationSetModel,
)
from app.adapters.db.models.opportunity_intelligence import JobListingCacheModel
from app.adapters.db.models.platform_admin import PlatformAdminModel, PlatformSettingModel
from app.adapters.db.models.resume_intelligence import ResumeModel
from app.adapters.db.models.search import ContentEmbeddingModel, EmbeddingModelModel

__all__ = [
    "AIInvocationModel",
    "AuditEventModel",
    "CareerGoalModel",
    "CareerHighlightModel",
    "CareerProfileModel",
    "CareerProfileVersionModel",
    "CategoryParentModel",
    "CertificationModel",
    "ChatConversationModel",
    "ChatMessageModel",
    "CikgRoleModel",
    "CompetencyModel",
    "ContentEmbeddingModel",
    "ContentHistoryModel",
    "ContentRevisionModel",
    "EducationModel",
    "EmbeddingModelModel",
    "ExperienceModel",
    "FeatureFlagModel",
    "JobListingCacheModel",
    "KeyAchievementModel",
    "LearningItemModel",
    "LearningRecommendationSetModel",
    "ModelVersionModel",
    "OrganizationModel",
    "PasswordResetTokenModel",
    "PeerEndorsementModel",
    "PendingSignupModel",
    "PermissionModel",
    "PersonalPhoneLoginModel",
    "PlatformAdminModel",
    "PlatformSettingModel",
    "PrerequisiteOfEdgeModel",
    "PromptVersionModel",
    "RelatedSkillModel",
    "ResumeModel",
    "RoleModel",
    "RolePermissionModel",
    "RoleProgressesToEdgeModel",
    "RoleRequiredSkillModel",
    "SkillAliasModel",
    "SkillCategoryMembershipModel",
    "SkillCategoryModel",
    "SkillCompetencyMembershipModel",
    "SkillModel",
    "SpecializesEdgeModel",
    "SynonymOfEdgeModel",
    "TargetRoleModel",
    "TenantModel",
    "UserModel",
    "UserRoleModel",
]
