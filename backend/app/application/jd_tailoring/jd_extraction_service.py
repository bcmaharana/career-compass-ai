"""One-shot AI extraction of Company/Role Title from raw JD text.

No persistence — the frontend's "Add Your Own JD" flow calls this to
pre-fill a small confirm form, which the user then fills the gaps of
by hand. Same fence-strip + json.loads structured-output pattern as
LearningRecommendationService's _parse_recommendations; degrades to
nulls on any failure (never a 500) since the user can always type the
values in manually regardless.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from uuid import UUID

from app.ai_platform.llm_service.service import LLMServiceInterface
from app.core.exceptions import CareerCompassError
from app.core.logging import get_logger

logger = get_logger(__name__)

_USE_CASE = "jd_extraction"
_MAX_RESPONSE_TOKENS = 200
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


@dataclass(slots=True)
class JdExtractionResult:
    company: str | None
    role_title: str | None


def _parse_extraction(text: str) -> JdExtractionResult:
    fence_match = _JSON_FENCE_RE.search(text)
    candidate = fence_match.group(1) if fence_match else text

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("The AI did not return recognizable JSON.")

    parsed = json.loads(candidate[start : end + 1])
    company = parsed.get("company")
    role_title = parsed.get("role_title")
    return JdExtractionResult(
        company=str(company) if isinstance(company, str) and company else None,
        role_title=str(role_title) if isinstance(role_title, str) and role_title else None,
    )


class JdExtractionService:
    def __init__(self, llm: LLMServiceInterface) -> None:
        self._llm = llm

    async def extract(self, *, tenant_id: UUID, user_id: UUID, jd_text: str) -> JdExtractionResult:
        try:
            raw = await self._llm.generate(
                use_case=_USE_CASE,
                input_variables={"jd_text": jd_text},
                tenant_id=tenant_id,
                user_id=user_id,
                max_tokens=_MAX_RESPONSE_TOKENS,
                temperature=0.0,
            )
            return _parse_extraction(raw)
        except (CareerCompassError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("jd_extraction_failed", error=str(exc))
            return JdExtractionResult(company=None, role_title=None)
