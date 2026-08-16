"""Career-path resolution + traversal (Phase 6).

Resolves a user's free-text TargetRole.role_name to a CikgRole, then
walks the role_progresses_to graph in both directions. Free text can
never guarantee a match — a miss returns `resolved=False` as a normal
result, never a dead end or an error, per this codebase's established
"degrade gracefully" convention (same posture as Resume Intelligence's
persisted `failed` status).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from app.application.career_intelligence.search_service import SearchService
from app.application.career_profile.target_role_service import TargetRoleService
from app.domain.career_intelligence.career_path_traversal import (
    traverse_downstream,
    traverse_upstream,
)
from app.domain.career_intelligence.entities import CikgRole
from app.domain.career_intelligence.repositories import (
    CikgRoleRepository,
    RoleProgressesToEdgeRepository,
)

# SearchService's score isn't a single normalized scale (graph hits score
# a flat 2.0; fulltext/vector are roughly 0-1). Tuned against real
# vector-search results (2026-08-15), not a priori: a genuinely close
# role-title match ("Senior Agile Coach" -> "Enterprise Agile Coach")
# scored 0.89, while a deliberately nonsense query ("Role 9") and a
# plausible-but-uncovered title ("Delivery Lead") both landed in a tight
# 0.38-0.47 noise band across every one of the 13 seeded roles — cosine
# similarity between short role-title embeddings doesn't spread much
# below real relevance at this content volume, so 0.6 is a real gap
# between "meaningful match" and "embedding noise," not a guess.
_MIN_MATCH_SCORE = 0.6


@dataclass(slots=True)
class CareerPathResult:
    resolved: bool
    matched_role: CikgRole | None
    match_type: str | None
    upstream: list[CikgRole] = field(default_factory=list)
    downstream: list[CikgRole] = field(default_factory=list)


class CareerPathService:
    def __init__(
        self,
        target_roles: TargetRoleService,
        cikg_roles: CikgRoleRepository,
        search: SearchService,
        edges: RoleProgressesToEdgeRepository,
    ) -> None:
        self._target_roles = target_roles
        self._cikg_roles = cikg_roles
        self._search = search
        self._edges = edges

    async def get_career_path(
        self, *, tenant_id: UUID, user_id: UUID, target_role_id: UUID
    ) -> CareerPathResult:
        target_role = await self._target_roles.get_owned_or_raise(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role_id
        )

        cikg_role = await self._cikg_roles.get_by_title(target_role.role_name)
        match_type = "exact_title"
        if cikg_role is None:
            hits = await self._search.search(
                query=target_role.role_name, entity_type="cikg_role", limit=1
            )
            if not hits or hits[0].score < _MIN_MATCH_SCORE:
                return CareerPathResult(resolved=False, matched_role=None, match_type=None)
            cikg_role = await self._cikg_roles.get_by_id(hits[0].entity_id)
            match_type = "search_fallback"

        if cikg_role is None:
            return CareerPathResult(resolved=False, matched_role=None, match_type=None)

        all_edges = await self._edges.list_all_approved()
        edge_pairs = [(e.source_role_id, e.target_role_id) for e in all_edges]
        upstream_ids = traverse_upstream(edge_pairs, cikg_role.id)
        downstream_ids = traverse_downstream(edge_pairs, cikg_role.id)

        return CareerPathResult(
            resolved=True,
            matched_role=cikg_role,
            match_type=match_type,
            upstream=await self._resolve_roles(upstream_ids),
            downstream=await self._resolve_roles(downstream_ids),
        )

    async def _resolve_roles(self, role_ids: list[UUID]) -> list[CikgRole]:
        roles = []
        for role_id in role_ids:
            role = await self._cikg_roles.get_by_id(role_id)
            if role is not None:
                roles.append(role)
        return roles
