"""Career Intelligence Knowledge Graph (CIKG) API routes.

Thin per backend-architecture.md. Reads (list/get) require only an
authenticated identity, per cikg-api-boundaries.md's resource-hierarchy
table — this is global reference data, not owned by any one caller.

Phase 4.5.1 MVP 2B: every node/edge write now goes through
`/revisions` (ContentRevisionService) — `cikg.content.create` to
propose, `cikg.content.review` to submit for review,
`cikg.content.approve` to approve/reject/mark-rejected/batch-approve.
`skill_alias` is the one write path outside this system (unchanged
from MVP 1 — never content_status-governed to begin with).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import (
    get_catalog_query_service,
    get_content_revision_service,
    get_current_identity,
    get_search_service,
    get_skill_alias_admin_service,
    get_skill_alias_resolution_service,
    require_permission,
)
from app.api.v1.career_intelligence.schemas import (
    BatchApprovalResultResponse,
    BatchApproveRequest,
    CategoryParentResponse,
    CikgRoleDetailResponse,
    CikgRoleResponse,
    CompetencyResponse,
    ContentRevisionResponse,
    CreateSkillAliasRequest,
    FailedRevisionResponse,
    ProposeRevisionRequest,
    RejectRevisionRequest,
    RelatedSkillResponse,
    RequiredSkillResponse,
    ResolveAliasResponse,
    RoleRequiredSkillResponse,
    SearchResultResponse,
    SkillAliasResponse,
    SkillCategoryMembershipResponse,
    SkillCategoryResponse,
    SkillCompetencyMembershipResponse,
    SkillDetailResponse,
    SkillResponse,
)
from app.application.career_intelligence.catalog_query_service import CatalogQueryService
from app.application.career_intelligence.content_revision_service import (
    BatchApprovalResult,
    ContentRevisionService,
)
from app.application.career_intelligence.search_service import SearchService
from app.application.career_intelligence.skill_alias_admin_service import SkillAliasAdminService
from app.application.career_intelligence.skill_alias_resolution_service import (
    SkillAliasResolutionService,
)
from app.core.identity_provider_interface import IdentityClaims
from app.domain.career_intelligence.entities import (
    CikgRole,
    Competency,
    ContentRevision,
    EmbeddableEntityType,
    Skill,
    SkillCategory,
)

router = APIRouter(prefix="/career-intelligence", tags=["career-intelligence"])


def _category_response(category: SkillCategory) -> SkillCategoryResponse:
    return SkillCategoryResponse(
        id=category.id,
        name=category.name,
        description=category.description,
        content_status=category.content_status,
    )


def _competency_response(competency: Competency) -> CompetencyResponse:
    return CompetencyResponse(
        id=competency.id,
        name=competency.name,
        description=competency.description,
        content_status=competency.content_status,
    )


def _skill_response(skill: Skill) -> SkillResponse:
    return SkillResponse(
        id=skill.id,
        name=skill.name,
        description=skill.description,
        content_status=skill.content_status,
        ats_keywords=skill.ats_keywords,
        proficiency_level_definitions=skill.proficiency_level_definitions,
    )


def _role_response(role: CikgRole) -> CikgRoleResponse:
    return CikgRoleResponse(
        id=role.id,
        title=role.title,
        description=role.description,
        experience_level=role.experience_level,
        content_status=role.content_status,
    )


def _revision_response(revision: ContentRevision) -> ContentRevisionResponse:
    return ContentRevisionResponse(
        id=revision.id,
        entity_type=revision.entity_type,
        entity_id=revision.entity_id,
        proposed_data=revision.proposed_data,
        revision_number=revision.revision_number,
        status=revision.status,
        confidence=revision.confidence,
        source_attribution=revision.source_attribution,
        import_batch_id=revision.import_batch_id,
        reviewed_by=revision.reviewed_by,
        review_notes=revision.review_notes,
        created_at=revision.created_at,
        reviewed_at=revision.reviewed_at,
    )


def _batch_result_response(result: BatchApprovalResult) -> BatchApprovalResultResponse:
    return BatchApprovalResultResponse(
        approved=result.approved,
        failed=[FailedRevisionResponse(revision_id=rid, error=err) for rid, err in result.failed],
    )


# --- Skill categories (read-only here — writes via /revisions) ---


@router.get("/categories", response_model=list[SkillCategoryResponse])
async def list_categories(
    identity: IdentityClaims = Depends(get_current_identity),
    catalog: CatalogQueryService = Depends(get_catalog_query_service),
) -> list[SkillCategoryResponse]:
    return [_category_response(c) for c in await catalog.list_categories()]


@router.get("/categories/{category_id}", response_model=SkillCategoryResponse)
async def get_category(
    category_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    catalog: CatalogQueryService = Depends(get_catalog_query_service),
) -> SkillCategoryResponse:
    return _category_response(await catalog.get_category(category_id))


# --- Competencies ---


@router.get("/competencies", response_model=list[CompetencyResponse])
async def list_competencies(
    identity: IdentityClaims = Depends(get_current_identity),
    catalog: CatalogQueryService = Depends(get_catalog_query_service),
) -> list[CompetencyResponse]:
    return [_competency_response(c) for c in await catalog.list_competencies()]


# --- Skills ---


@router.get("/skills", response_model=list[SkillResponse])
async def list_skills(
    identity: IdentityClaims = Depends(get_current_identity),
    catalog: CatalogQueryService = Depends(get_catalog_query_service),
) -> list[SkillResponse]:
    return [_skill_response(s) for s in await catalog.list_skills()]


@router.get("/skills/{skill_id}", response_model=SkillDetailResponse)
async def get_skill(
    skill_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    catalog: CatalogQueryService = Depends(get_catalog_query_service),
) -> SkillDetailResponse:
    skill = await catalog.get_skill(skill_id)
    categories = await catalog.list_skill_categories(skill_id)
    related = await catalog.list_related_skills(skill_id)
    aliases = await catalog.list_skill_aliases(skill_id)
    return SkillDetailResponse(
        **_skill_response(skill).model_dump(),
        category_ids=[m.category_id for m in categories],
        related_skill_ids=[
            edge.skill_b_id if edge.skill_a_id == skill_id else edge.skill_a_id
            for edge in related
        ],
        aliases=[a.alias_text for a in aliases],
    )


@router.post("/skill-aliases", response_model=SkillAliasResponse, status_code=201)
async def create_skill_alias(
    request: CreateSkillAliasRequest,
    identity: IdentityClaims = Depends(require_permission("cikg.content.create")),
    service: SkillAliasAdminService = Depends(get_skill_alias_admin_service),
) -> SkillAliasResponse:
    alias = await service.create(
        skill_id=request.skill_id,
        alias_text=request.alias_text,
        source=request.source,  # type: ignore[arg-type]
        confidence=request.confidence,
    )
    return SkillAliasResponse(
        id=alias.id,
        skill_id=alias.skill_id,
        alias_text=alias.alias_text,
        normalized_text=alias.normalized_text,
        source=alias.source,
        confidence=alias.confidence,
    )


@router.get("/skill-aliases/resolve", response_model=ResolveAliasResponse)
async def resolve_skill_alias(
    text: str,
    identity: IdentityClaims = Depends(get_current_identity),
    resolver: SkillAliasResolutionService = Depends(get_skill_alias_resolution_service),
) -> ResolveAliasResponse:
    skill = await resolver.resolve(text)
    return ResolveAliasResponse(skill=_skill_response(skill) if skill is not None else None)


# --- CikgRoles ---


@router.get("/roles", response_model=list[CikgRoleResponse])
async def list_roles(
    identity: IdentityClaims = Depends(get_current_identity),
    catalog: CatalogQueryService = Depends(get_catalog_query_service),
) -> list[CikgRoleResponse]:
    return [_role_response(r) for r in await catalog.list_roles()]


@router.get("/roles/{role_id}", response_model=CikgRoleDetailResponse)
async def get_role(
    role_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    catalog: CatalogQueryService = Depends(get_catalog_query_service),
) -> CikgRoleDetailResponse:
    role = await catalog.get_role(role_id)
    required = await catalog.list_required_skills(role_id)
    return CikgRoleDetailResponse(
        **_role_response(role).model_dump(),
        required_skills=[
            RequiredSkillResponse(skill_id=r.skill_id, requirement_level=r.requirement_level)
            for r in required
        ],
    )


# --- Search (Phase 4.5.1 MVP 2A) ---


@router.get("/search", response_model=list[SearchResultResponse])
async def search(
    q: str,
    entity_type: EmbeddableEntityType | None = None,
    category_id: UUID | None = None,
    role_id: UUID | None = None,
    limit: int = 20,
    identity: IdentityClaims = Depends(get_current_identity),
    service: SearchService = Depends(get_search_service),
) -> list[SearchResultResponse]:
    results = await service.search(
        query=q, entity_type=entity_type, category_id=category_id, role_id=role_id, limit=limit
    )
    return [
        SearchResultResponse(
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            name=r.name,
            description=r.description,
            score=r.score,
            matched_via=r.matched_via,
        )
        for r in results
    ]


# --- Content revisions (Phase 4.5.1 MVP 2B) ---


@router.post("/revisions", response_model=ContentRevisionResponse, status_code=201)
async def propose_revision(
    request: ProposeRevisionRequest,
    identity: IdentityClaims = Depends(require_permission("cikg.content.create")),
    service: ContentRevisionService = Depends(get_content_revision_service),
) -> ContentRevisionResponse:
    revision = await service.propose(
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        proposed_data=request.proposed_data,
        source_attribution=request.source_attribution,  # type: ignore[arg-type]
        confidence=request.confidence,
        import_batch_id=request.import_batch_id,
    )
    return _revision_response(revision)


@router.get("/revisions", response_model=list[ContentRevisionResponse])
async def list_revisions(
    status: str | None = None,
    import_batch_id: UUID | None = None,
    identity: IdentityClaims = Depends(require_permission("cikg.content.review")),
    service: ContentRevisionService = Depends(get_content_revision_service),
) -> list[ContentRevisionResponse]:
    if import_batch_id is not None:
        revisions = await service.list_by_batch(import_batch_id)
        if status is not None:
            revisions = [r for r in revisions if r.status == status]
        return [_revision_response(r) for r in revisions]
    revisions = await service.list_by_status(status or "in_review")
    return [_revision_response(r) for r in revisions]


@router.post("/revisions/{revision_id}/submit", response_model=ContentRevisionResponse)
async def submit_revision_for_review(
    revision_id: UUID,
    identity: IdentityClaims = Depends(require_permission("cikg.content.review")),
    service: ContentRevisionService = Depends(get_content_revision_service),
) -> ContentRevisionResponse:
    return _revision_response(await service.submit_for_review(revision_id))


@router.post("/revisions/{revision_id}/approve", response_model=ContentRevisionResponse)
async def approve_revision(
    revision_id: UUID,
    identity: IdentityClaims = Depends(require_permission("cikg.content.approve")),
    service: ContentRevisionService = Depends(get_content_revision_service),
) -> ContentRevisionResponse:
    revision = await service.approve(revision_id, reviewed_by=UUID(identity.user_id))
    return _revision_response(revision)


@router.post("/revisions/{revision_id}/reject", response_model=ContentRevisionResponse)
async def reject_revision(
    revision_id: UUID,
    request: RejectRevisionRequest,
    identity: IdentityClaims = Depends(require_permission("cikg.content.approve")),
    service: ContentRevisionService = Depends(get_content_revision_service),
) -> ContentRevisionResponse:
    revision = await service.reject(revision_id, review_notes=request.review_notes)
    return _revision_response(revision)


@router.post("/revisions/{revision_id}/mark-rejected", response_model=ContentRevisionResponse)
async def mark_revision_rejected(
    revision_id: UUID,
    request: RejectRevisionRequest,
    identity: IdentityClaims = Depends(require_permission("cikg.content.approve")),
    service: ContentRevisionService = Depends(get_content_revision_service),
) -> ContentRevisionResponse:
    revision = await service.mark_rejected(revision_id, review_notes=request.review_notes)
    return _revision_response(revision)


@router.post("/revisions/batch-approve", response_model=BatchApprovalResultResponse)
async def batch_approve_revisions(
    request: BatchApproveRequest,
    identity: IdentityClaims = Depends(require_permission("cikg.content.approve")),
    service: ContentRevisionService = Depends(get_content_revision_service),
) -> BatchApprovalResultResponse:
    result = await service.batch_approve(
        request.import_batch_id, reviewed_by=UUID(identity.user_id)
    )
    return _batch_result_response(result)
