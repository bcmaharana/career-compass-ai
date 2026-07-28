"""Repository implementations, organized one module per domain.

`from app.adapters.db.repositories import SqlAlchemyUserRepository` (and
every other existing import site) keeps working unchanged — this
package re-exports every repository from its domain submodule.
"""

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

__all__ = [
    "SqlAlchemyAuditEventRepository",
    "SqlAlchemyCareerGoalRepository",
    "SqlAlchemyCareerHighlightRepository",
    "SqlAlchemyCareerProfileRepository",
    "SqlAlchemyCertificationRepository",
    "SqlAlchemyChatConversationRepository",
    "SqlAlchemyChatMessageRepository",
    "SqlAlchemyEducationRepository",
    "SqlAlchemyExperienceRepository",
    "SqlAlchemyFeatureFlagRepository",
    "SqlAlchemyKeyAchievementRepository",
    "SqlAlchemyOrganizationRepository",
    "SqlAlchemyPeerEndorsementRepository",
    "SqlAlchemyRoleRepository",
    "SqlAlchemyTargetRoleRepository",
    "SqlAlchemyTenantContextBinder",
    "SqlAlchemyTenantRepository",
    "SqlAlchemyUserRepository",
]
