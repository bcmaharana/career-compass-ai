"""Skill Intelligence API routes (Phase 3, simplified per ADR-005).

Only Gap Analysis remains here — My Skills is just Career Profile's
core_competencies, and Target Role Skill Requirements is a plain field on
TargetRole, both served by app/api/v1/career_profile/router.py. This route
is pure computation over those two, via GapAnalysisService.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_identity, get_gap_analysis_service
from app.api.v1.skill_intelligence.schemas import GapAnalysisResponse, TargetRoleGapResponse
from app.application.skill_intelligence.gap_analysis_service import GapAnalysisService
from app.core.identity_provider_interface import IdentityClaims

router = APIRouter(tags=["skill-intelligence"])


@router.get("/skills/gap-analysis", response_model=GapAnalysisResponse)
async def get_gap_analysis(
    identity: IdentityClaims = Depends(get_current_identity),
    service: GapAnalysisService = Depends(get_gap_analysis_service),
) -> GapAnalysisResponse:
    result = await service.compute(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id)
    )
    return GapAnalysisResponse(
        target_role_gaps=[
            TargetRoleGapResponse(
                target_role_id=gap.target_role_id,
                role_name=gap.role_name,
                tag=gap.tag,
                missing_skills=gap.missing_skills,
            )
            for gap in result.target_role_gaps
        ],
    )
