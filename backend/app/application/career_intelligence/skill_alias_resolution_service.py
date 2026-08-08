"""Free-text -> canonical Skill resolution (ADR-006 §3).

A separate, read-only application service — per
cikg-knowledge-graph-model.md: "A separate, read-only resolution
service (part of CIKG's application layer, not Career Profile's) can
look up skill_alias for a given free-text string." Deliberately
tolerant: resolution failing (no match) is a normal, expected outcome,
never an error — callers (gap-analysis enrichment, AI grounding) always
degrade gracefully to "no suggestion" rather than being blocked by a
failed lookup.
"""

from __future__ import annotations

from app.domain.career_intelligence.aliasing import normalize_alias_text
from app.domain.career_intelligence.entities import Skill
from app.domain.career_intelligence.repositories import SkillAliasRepository, SkillRepository


class SkillAliasResolutionService:
    def __init__(self, aliases: SkillAliasRepository, skills: SkillRepository) -> None:
        self._aliases = aliases
        self._skills = skills

    async def resolve(self, free_text: str) -> Skill | None:
        """Exact canonical-name match first, then the skill_alias table.

        `cikg-semantic-search.md`'s worked example describes this as an
        "exact/alias match" — matching the free text against a skill's
        own name is the more basic, prior case, and skipping it would
        mean a query using a skill's literal canonical name (not
        registered as one of its aliases) fails to resolve at all.
        """
        exact = await self._skills.get_by_name(free_text)
        if exact is not None:
            return exact

        normalized = normalize_alias_text(free_text)
        alias = await self._aliases.get_by_normalized_text(normalized)
        if alias is None:
            return None
        return await self._skills.get_by_id(alias.skill_id)
