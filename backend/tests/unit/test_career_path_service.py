"""Unit tests for CareerPathService — fake repositories/search, no
database. Mirrors the fake-repository pattern established in
tests/unit/test_target_role_service.py and test_career_intelligence.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.application.career_profile.target_role_service import TargetRoleService
from app.application.opportunity_intelligence.career_path_service import CareerPathService
from app.domain.career_intelligence.entities import CikgRole, RoleProgressesToEdge, SearchResult
from app.domain.career_profile.entities import TargetRole

pytestmark = pytest.mark.unit


class FakeTargetRoleRepository:
    def __init__(self) -> None:
        self.target_roles: dict[uuid.UUID, TargetRole] = {}

    async def create(self, target_role: TargetRole) -> TargetRole:
        self.target_roles[target_role.id] = target_role
        return target_role

    async def get_by_id(self, tenant_id: uuid.UUID, target_role_id: uuid.UUID) -> TargetRole | None:
        role = self.target_roles.get(target_role_id)
        return role if role and role.tenant_id == tenant_id else None

    async def list_for_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[TargetRole]:
        return [
            r
            for r in self.target_roles.values()
            if r.tenant_id == tenant_id and r.user_id == user_id
        ]

    async def update(self, target_role: TargetRole) -> TargetRole:
        self.target_roles[target_role.id] = target_role
        return target_role

    async def soft_delete(self, tenant_id: uuid.UUID, target_role_id: uuid.UUID) -> None:
        self.target_roles.pop(target_role_id, None)


class FakeCikgRoleRepository:
    def __init__(self) -> None:
        self.roles: dict[uuid.UUID, CikgRole] = {}

    async def create(self, role: CikgRole) -> CikgRole:
        self.roles[role.id] = role
        return role

    async def update(self, role: CikgRole) -> CikgRole:
        self.roles[role.id] = role
        return role

    async def get_by_id(self, role_id: uuid.UUID) -> CikgRole | None:
        return self.roles.get(role_id)

    async def get_by_title(self, title: str) -> CikgRole | None:
        for role in self.roles.values():
            if role.title == title:
                return role
        return None

    async def list_approved(self) -> list[CikgRole]:
        return [r for r in self.roles.values() if r.content_status == "approved"]


class FakeRoleProgressesToEdgeRepository:
    def __init__(self, edges: list[RoleProgressesToEdge] | None = None) -> None:
        self.edges = edges or []

    async def create(self, edge: RoleProgressesToEdge) -> RoleProgressesToEdge:
        self.edges.append(edge)
        return edge

    async def get_by_pair(
        self, source_role_id: uuid.UUID, target_role_id: uuid.UUID
    ) -> RoleProgressesToEdge | None:
        for e in self.edges:
            if e.source_role_id == source_role_id and e.target_role_id == target_role_id:
                return e
        return None

    async def list_all_approved(self) -> list[RoleProgressesToEdge]:
        return [e for e in self.edges if e.content_status == "approved"]

    async def list_for_role(self, role_id: uuid.UUID) -> list[RoleProgressesToEdge]:
        return [e for e in self.edges if e.source_role_id == role_id or e.target_role_id == role_id]


class FakeSearchService:
    def __init__(self, results: list[SearchResult] | None = None) -> None:
        self._results = results or []

    async def search(
        self,
        *,
        query: str,
        entity_type: object = None,
        category_id: object = None,
        role_id: object = None,
        limit: int = 20,
    ) -> list[SearchResult]:
        return self._results


def _make_role(title: str) -> CikgRole:
    now = datetime.now(UTC)
    return CikgRole(
        id=uuid.uuid4(),
        title=title,
        description=None,
        experience_level=None,
        content_status="approved",
        source_attribution=None,
        created_at=now,
        updated_at=now,
    )


def _make_edge(source_id: uuid.UUID, target_id: uuid.UUID) -> RoleProgressesToEdge:
    return RoleProgressesToEdge(
        id=uuid.uuid4(),
        source_role_id=source_id,
        target_role_id=target_id,
        content_status="approved",
        source_attribution=None,
        created_at=datetime.now(UTC),
    )


def _make_target_role(tenant_id: uuid.UUID, user_id: uuid.UUID, role_name: str) -> TargetRole:
    return TargetRole(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        role_name=role_name,
        tag="X",
        created_at=datetime.now(UTC),
    )


class TestGetCareerPath:
    async def test_exact_title_match_returns_upstream_and_downstream(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_roles_repo = FakeTargetRoleRepository()
        cikg_roles = FakeCikgRoleRepository()

        junior = await cikg_roles.create(_make_role("Junior Engineer"))
        mid = await cikg_roles.create(_make_role("Software Engineer"))
        senior = await cikg_roles.create(_make_role("Senior Engineer"))
        edges = FakeRoleProgressesToEdgeRepository(
            [_make_edge(junior.id, mid.id), _make_edge(mid.id, senior.id)]
        )
        target_role = await target_roles_repo.create(
            _make_target_role(tenant_id, user_id, "Software Engineer")
        )

        service = CareerPathService(
            TargetRoleService(target_roles_repo), cikg_roles, FakeSearchService(), edges
        )
        result = await service.get_career_path(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id
        )

        assert result.resolved is True
        assert result.match_type == "exact_title"
        assert result.matched_role is not None
        assert result.matched_role.id == mid.id
        assert [r.id for r in result.upstream] == [junior.id]
        assert [r.id for r in result.downstream] == [senior.id]

    async def test_no_match_returns_unresolved_not_an_error(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_roles_repo = FakeTargetRoleRepository()
        cikg_roles = FakeCikgRoleRepository()
        edges = FakeRoleProgressesToEdgeRepository()
        target_role = await target_roles_repo.create(
            _make_target_role(tenant_id, user_id, "Extremely Niche Made-Up Title")
        )

        service = CareerPathService(
            TargetRoleService(target_roles_repo), cikg_roles, FakeSearchService(results=[]), edges
        )
        result = await service.get_career_path(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id
        )

        assert result.resolved is False
        assert result.matched_role is None
        assert result.upstream == []
        assert result.downstream == []

    async def test_search_fallback_used_when_no_exact_title(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_roles_repo = FakeTargetRoleRepository()
        cikg_roles = FakeCikgRoleRepository()
        matched = await cikg_roles.create(_make_role("Staff Engineer"))
        edges = FakeRoleProgressesToEdgeRepository()
        target_role = await target_roles_repo.create(
            _make_target_role(tenant_id, user_id, "Staff Software Engineer II")
        )
        search_result = SearchResult(
            entity_type="cikg_role",
            entity_id=matched.id,
            name=matched.title,
            description=None,
            score=1.5,
            matched_via=["fulltext"],
        )

        service = CareerPathService(
            TargetRoleService(target_roles_repo),
            cikg_roles,
            FakeSearchService(results=[search_result]),
            edges,
        )
        result = await service.get_career_path(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id
        )

        assert result.resolved is True
        assert result.match_type == "search_fallback"
        assert result.matched_role is not None
        assert result.matched_role.id == matched.id

    async def test_low_score_search_hit_is_treated_as_unresolved(self) -> None:
        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        target_roles_repo = FakeTargetRoleRepository()
        cikg_roles = FakeCikgRoleRepository()
        unrelated = await cikg_roles.create(_make_role("Totally Unrelated Role"))
        edges = FakeRoleProgressesToEdgeRepository()
        target_role = await target_roles_repo.create(
            _make_target_role(tenant_id, user_id, "Something Else Entirely")
        )
        weak_hit = SearchResult(
            entity_type="cikg_role",
            entity_id=unrelated.id,
            name=unrelated.title,
            description=None,
            score=0.0,
            matched_via=["fulltext"],
        )

        service = CareerPathService(
            TargetRoleService(target_roles_repo),
            cikg_roles,
            FakeSearchService(results=[weak_hit]),
            edges,
        )
        result = await service.get_career_path(
            tenant_id=tenant_id, user_id=user_id, target_role_id=target_role.id
        )

        assert result.resolved is False
