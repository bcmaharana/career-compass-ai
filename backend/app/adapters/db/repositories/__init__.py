"""Repository implementations, organized one module per domain.

`from app.adapters.db.repositories import SqlAlchemyUserRepository` (and
every other existing import site) keeps working unchanged — this
package re-exports every repository from its domain submodule.
"""

from app.adapters.db.repositories.ai_platform import (
    SqlAlchemyInvocationLogger,
    SqlAlchemyModelRegistry,
    SqlAlchemyPromptRegistry,
)
from app.adapters.db.repositories.career_intelligence import (
    SqlAlchemyCategoryParentRepository,
    SqlAlchemyCikgRoleRepository,
    SqlAlchemyCompetencyRepository,
    SqlAlchemyPrerequisiteOfEdgeRepository,
    SqlAlchemyRelatedSkillRepository,
    SqlAlchemyRoleRequiredSkillRepository,
    SqlAlchemySkillAliasRepository,
    SqlAlchemySkillCategoryMembershipRepository,
    SqlAlchemySkillCategoryRepository,
    SqlAlchemySkillCompetencyMembershipRepository,
    SqlAlchemySkillRepository,
    SqlAlchemySpecializesEdgeRepository,
    SqlAlchemySynonymOfEdgeRepository,
)
from app.adapters.db.repositories.career_profile import (
    SqlAlchemyCareerGoalRepository,
    SqlAlchemyCareerHighlightRepository,
    SqlAlchemyCareerProfileRepository,
    SqlAlchemyCertificationRepository,
    SqlAlchemyEducationRepository,
    SqlAlchemyExperienceRepository,
    SqlAlchemyKeyAchievementRepository,
    SqlAlchemyPeerEndorsementRepository,
    SqlAlchemyTargetRoleRepository,
)
from app.adapters.db.repositories.chat import (
    SqlAlchemyChatConversationRepository,
    SqlAlchemyChatMessageRepository,
)
from app.adapters.db.repositories.identity import (
    SqlAlchemyAuditEventRepository,
    SqlAlchemyFeatureFlagRepository,
    SqlAlchemyOrganizationRepository,
    SqlAlchemyRoleRepository,
    SqlAlchemyTenantContextBinder,
    SqlAlchemyTenantRepository,
    SqlAlchemyUserRepository,
)
from app.adapters.db.repositories.governance import (
    SqlAlchemyContentHistoryRepository,
    SqlAlchemyContentRevisionRepository,
)
from app.adapters.db.repositories.search import (
    SqlAlchemyContentEmbeddingRepository,
    SqlAlchemyEmbeddingModelRepository,
    SqlAlchemySearchRepository,
)

__all__ = [
    "SqlAlchemyAuditEventRepository",
    "SqlAlchemyCareerGoalRepository",
    "SqlAlchemyCareerHighlightRepository",
    "SqlAlchemyCareerProfileRepository",
    "SqlAlchemyCategoryParentRepository",
    "SqlAlchemyCertificationRepository",
    "SqlAlchemyChatConversationRepository",
    "SqlAlchemyChatMessageRepository",
    "SqlAlchemyCikgRoleRepository",
    "SqlAlchemyCompetencyRepository",
    "SqlAlchemyContentEmbeddingRepository",
    "SqlAlchemyContentHistoryRepository",
    "SqlAlchemyContentRevisionRepository",
    "SqlAlchemyEducationRepository",
    "SqlAlchemyEmbeddingModelRepository",
    "SqlAlchemyExperienceRepository",
    "SqlAlchemyFeatureFlagRepository",
    "SqlAlchemyInvocationLogger",
    "SqlAlchemyKeyAchievementRepository",
    "SqlAlchemyModelRegistry",
    "SqlAlchemyOrganizationRepository",
    "SqlAlchemyPeerEndorsementRepository",
    "SqlAlchemyPrerequisiteOfEdgeRepository",
    "SqlAlchemyPromptRegistry",
    "SqlAlchemyRelatedSkillRepository",
    "SqlAlchemyRoleRepository",
    "SqlAlchemyRoleRequiredSkillRepository",
    "SqlAlchemySearchRepository",
    "SqlAlchemySkillAliasRepository",
    "SqlAlchemySkillCategoryMembershipRepository",
    "SqlAlchemySkillCategoryRepository",
    "SqlAlchemySkillCompetencyMembershipRepository",
    "SqlAlchemySkillRepository",
    "SqlAlchemySpecializesEdgeRepository",
    "SqlAlchemySynonymOfEdgeRepository",
    "SqlAlchemyTargetRoleRepository",
    "SqlAlchemyTenantContextBinder",
    "SqlAlchemyTenantRepository",
    "SqlAlchemyUserRepository",
]
