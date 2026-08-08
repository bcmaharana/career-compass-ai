"""Curator-facing skill_alias management — creation only.

Split out from the old MVP 1 `ContentGovernanceService` (removed in
Phase 4.5.1 MVP 2B in favor of `ContentRevisionService`) because
`skill_alias` was never part of that governance system to begin with:
per its own domain docstring, it's "not governed by content_status —
trust is carried by `source` instead." It doesn't belong under the
revision workflow any more than `SkillAliasResolutionService` (its
read-only counterpart) does.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from uuid import UUID

from app.core.exceptions import ConflictError
from app.domain.career_intelligence.aliasing import normalize_alias_text
from app.domain.career_intelligence.entities import AliasSource, SkillAlias
from app.domain.career_intelligence.repositories import SkillAliasRepository


class SkillAliasAdminService:
    def __init__(self, aliases: SkillAliasRepository) -> None:
        self._aliases = aliases

    async def create(
        self,
        *,
        skill_id: UUID,
        alias_text: str,
        source: AliasSource,
        confidence: float | None = None,
    ) -> SkillAlias:
        """The one duplicate check that matters is on the normalized
        text itself, since two different skills claiming the same
        free-text alias would make resolution ambiguous."""
        normalized = normalize_alias_text(alias_text)
        existing = await self._aliases.get_by_normalized_text(normalized)
        if existing is not None:
            raise ConflictError(
                f'"{alias_text}" already resolves to a different skill.',
                code="SKILL_ALIAS_DUPLICATE",
            )
        return await self._aliases.create(
            SkillAlias(
                id=uuid.uuid4(),
                skill_id=skill_id,
                alias_text=alias_text,
                normalized_text=normalized,
                source=source,
                confidence=confidence,
                created_at=datetime.now(UTC),
            )
        )
