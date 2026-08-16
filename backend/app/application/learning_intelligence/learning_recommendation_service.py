"""AI-generated learning recommendations (Phase 7).

Driven by the existing GapAnalysisService's missing_skills output — no
new gap-computation logic here, just turning that into concrete
suggested resources via LLMService.generate(). Degrade-gracefully
choice: persist a status="failed" row with error_message (Resume
Intelligence's pattern), not a hardcoded fallback (Chat's pattern) — a
canned reply would actively mislead here since it has nothing to do
with the user's real gaps; a durable failed row + Regenerate action is
the honest equivalent of Resume Intelligence's failed extraction state.

Caching: a `missing_skills_hash` staleness check means a cached set
regenerates automatically the moment the underlying gap analysis
actually changes, not just after the TTL — `force_regenerate=True` is
the explicit user-facing override (wired to POST .../regenerate).
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.ai_platform.llm_service.service import LLMServiceInterface
from app.application.career_profile.target_role_service import TargetRoleService
from app.application.skill_intelligence.gap_analysis_service import GapAnalysisService
from app.core.exceptions import CareerCompassError
from app.domain.learning_intelligence.entities import LearningRecommendationSet
from app.domain.learning_intelligence.repositories import LearningRecommendationRepository

_USE_CASE = "learning_recommendations"
_CACHE_TTL = timedelta(hours=24)
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
# A real gap analysis can list 20+ missing skills for a role with a lot
# of ground to cover (confirmed live) — 2-3 resources + a summary per
# skill for that many quickly outgrows a bounded response budget and
# gets cut off mid-JSON. Cap what's actually sent to the LLM; the cache
# key still hashes the FULL missing_skills list (see _hash_skills call
# below), so gaining/losing a skill beyond the cap still invalidates
# the cache correctly, even though it wouldn't change what's requested.
_MAX_SKILLS_PER_PROMPT = 12
# Verified live (2026-08-15): 1200 tokens truncated mid-response for an
# 18-skill role (output_tokens hit the cap exactly, confirmed via
# ai_invocations). 3000 comfortably covers _MAX_SKILLS_PER_PROMPT's worth
# of 2-3 resources + a summary per skill.
_MAX_RESPONSE_TOKENS = 3000


def _hash_skills(missing_skills: list[str]) -> str:
    joined = "|".join(sorted(s.lower() for s in missing_skills))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _parse_recommendations(text: str) -> list[dict[str, object]]:
    fence_match = _JSON_FENCE_RE.search(text)
    candidate = fence_match.group(1) if fence_match else text

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("The AI did not return recognizable JSON.")

    try:
        parsed = json.loads(candidate[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"The AI's response was not valid JSON: {exc}") from exc

    recommendations = parsed.get("recommendations")
    if not isinstance(recommendations, list):
        raise ValueError("The AI's response was missing a 'recommendations' array.")
    return recommendations


class LearningRecommendationService:
    def __init__(
        self,
        recommendations: LearningRecommendationRepository,
        gap_analysis: GapAnalysisService,
        llm: LLMServiceInterface,
        target_roles: TargetRoleService,
    ) -> None:
        self._recommendations = recommendations
        self._gap_analysis = gap_analysis
        self._llm = llm
        self._target_roles = target_roles

    async def get_or_generate(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        target_role_id: UUID,
        force_regenerate: bool = False,
    ) -> LearningRecommendationSet:
        target_role = await self._target_roles.get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )
        gap_result = await self._gap_analysis.compute(tenant_id=tenant_id, user_id=user_id)
        gap = next(
            (g for g in gap_result.target_role_gaps if g.target_role_id == target_role_id), None
        )
        missing_skills = gap.missing_skills if gap else []
        skills_hash = _hash_skills(missing_skills)

        existing = await self._recommendations.get_for_target_role(
            tenant_id, user_id, target_role_id
        )
        if (
            not force_regenerate
            and existing is not None
            and existing.status == "generated"
            and existing.missing_skills_hash == skills_hash
            and (datetime.now(UTC) - existing.generated_at) < _CACHE_TTL
        ):
            return existing

        if not missing_skills:
            return await self._recommendations.upsert(
                LearningRecommendationSet(
                    id=existing.id if existing else uuid.uuid4(),
                    tenant_id=tenant_id,
                    user_id=user_id,
                    target_role_id=target_role_id,
                    status="generated",
                    missing_skills_hash=skills_hash,
                    recommendations=[],
                    error_message=None,
                    generated_at=datetime.now(UTC),
                )
            )

        try:
            raw = await self._llm.generate(
                use_case=_USE_CASE,
                input_variables={
                    "role_name": target_role.role_name,
                    "missing_skills": ", ".join(missing_skills[:_MAX_SKILLS_PER_PROMPT]),
                },
                tenant_id=tenant_id,
                user_id=user_id,
                max_tokens=_MAX_RESPONSE_TOKENS,
                temperature=0.3,
            )
            parsed = _parse_recommendations(raw)
            new_set = LearningRecommendationSet(
                id=existing.id if existing else uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                target_role_id=target_role_id,
                status="generated",
                missing_skills_hash=skills_hash,
                recommendations=parsed,
                error_message=None,
                generated_at=datetime.now(UTC),
            )
        except (CareerCompassError, ValueError) as exc:
            new_set = LearningRecommendationSet(
                id=existing.id if existing else uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                target_role_id=target_role_id,
                status="failed",
                missing_skills_hash=skills_hash,
                recommendations=None,
                error_message=str(exc),
                generated_at=datetime.now(UTC),
            )

        return await self._recommendations.upsert(new_set)
