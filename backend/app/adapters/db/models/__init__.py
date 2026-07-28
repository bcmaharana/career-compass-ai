"""ORM models, organized one module per domain.

`from app.adapters.db.models import UserModel` (and every other existing
import site) keeps working unchanged — this package re-exports every
model from its domain submodule, so splitting identity.py out of a
single models.py file is invisible to callers.

New domains add a new submodule here (e.g. career_profile.py) and add
its re-exports below — never grow identity.py to hold unrelated tables.
"""

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
    PermissionModel,
    RoleModel,
    RolePermissionModel,
    TenantModel,
    UserModel,
    UserRoleModel,
)

__all__ = [
    "AuditEventModel",
    "CareerGoalModel",
    "CareerHighlightModel",
    "CareerProfileModel",
    "CareerProfileVersionModel",
    "CertificationModel",
    "ChatConversationModel",
    "ChatMessageModel",
    "EducationModel",
    "ExperienceModel",
    "FeatureFlagModel",
    "KeyAchievementModel",
    "OrganizationModel",
    "PeerEndorsementModel",
    "PermissionModel",
    "RoleModel",
    "RolePermissionModel",
    "TargetRoleModel",
    "TenantModel",
    "UserModel",
    "UserRoleModel",
]
