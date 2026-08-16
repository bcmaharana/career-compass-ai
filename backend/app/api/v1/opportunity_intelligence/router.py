"""Opportunity Intelligence API routes (Phase 6).

Thin per backend-architecture.md: parse input, call one application
service, map the result to a response schema. Self-service data, no
extra RBAC permission required beyond get_current_identity — same as
every career-profile route.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import (
    get_career_path_service,
    get_current_identity,
    get_job_listing_service,
    get_job_search_preference_service,
)
from app.api.v1.opportunity_intelligence.schemas import (
    CareerPathResponse,
    CikgRoleSummary,
    JobListingResponse,
    JobListingsResponse,
    JobSearchPreferenceRequest,
    JobSearchPreferenceResponse,
)
from app.application.opportunity_intelligence.career_path_service import (
    CareerPathResult,
    CareerPathService,
)
from app.application.opportunity_intelligence.job_listing_service import (
    JobListingService,
    JobListingsResult,
)
from app.application.opportunity_intelligence.job_search_preference_service import (
    JobSearchPreference,
    JobSearchPreferenceService,
)
from app.core.identity_provider_interface import IdentityClaims
from app.domain.career_intelligence.entities import CikgRole

router = APIRouter(tags=["opportunity-intelligence"])


def _job_listings_response(result: JobListingsResult) -> JobListingsResponse:
    return JobListingsResponse(
        target_role_id=result.target_role_id,
        role_query=result.role_query,
        location_query=result.location_query,
        fetched_at=result.fetched_at,
        listings=[
            JobListingResponse(
                provider_id=listing.provider_id,
                title=listing.title,
                company=listing.company,
                location=listing.location,
                description=listing.description,
                redirect_url=listing.redirect_url,
                salary_min=listing.salary_min,
                salary_max=listing.salary_max,
                contract_type=listing.contract_type,
                category=listing.category,
                posted_at=listing.posted_at,
            )
            for listing in result.listings
        ],
    )


@router.get("/opportunities/jobs", response_model=JobListingsResponse)
async def get_job_listings(
    target_role_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: JobListingService = Depends(get_job_listing_service),
) -> JobListingsResponse:
    result = await service.get_for_target_role(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
    )
    return _job_listings_response(result)


def _cikg_role_summary(role: CikgRole) -> CikgRoleSummary:
    return CikgRoleSummary(
        id=role.id,
        title=role.title,
        description=role.description,
        experience_level=role.experience_level,
    )


def _career_path_response(result: CareerPathResult) -> CareerPathResponse:
    return CareerPathResponse(
        resolved=result.resolved,
        matched_role=_cikg_role_summary(result.matched_role) if result.matched_role else None,
        match_type=result.match_type,
        upstream=[_cikg_role_summary(r) for r in result.upstream],
        downstream=[_cikg_role_summary(r) for r in result.downstream],
    )


@router.get("/opportunities/career-path", response_model=CareerPathResponse)
async def get_career_path(
    target_role_id: UUID,
    identity: IdentityClaims = Depends(get_current_identity),
    service: CareerPathService = Depends(get_career_path_service),
) -> CareerPathResponse:
    result = await service.get_career_path(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        target_role_id=target_role_id,
    )
    return _career_path_response(result)


def _preference_response(preference: JobSearchPreference) -> JobSearchPreferenceResponse:
    return JobSearchPreferenceResponse(
        location=preference.location,
        max_days_old=preference.max_days_old,
        distance_miles=preference.distance_miles,
        employment_time=preference.employment_time,
        employment_type=preference.employment_type,
    )


@router.get("/opportunities/job-search-preference", response_model=JobSearchPreferenceResponse)
async def get_job_search_preference(
    identity: IdentityClaims = Depends(get_current_identity),
    service: JobSearchPreferenceService = Depends(get_job_search_preference_service),
) -> JobSearchPreferenceResponse:
    preference = await service.get(
        tenant_id=UUID(identity.tenant_id), user_id=UUID(identity.user_id)
    )
    return _preference_response(preference)


@router.patch("/opportunities/job-search-preference", response_model=JobSearchPreferenceResponse)
async def update_job_search_preference(
    request: JobSearchPreferenceRequest,
    identity: IdentityClaims = Depends(get_current_identity),
    service: JobSearchPreferenceService = Depends(get_job_search_preference_service),
) -> JobSearchPreferenceResponse:
    preference = await service.update(
        tenant_id=UUID(identity.tenant_id),
        user_id=UUID(identity.user_id),
        location=request.location,
        max_days_old=request.max_days_old,
        distance_miles=request.distance_miles,
        employment_time=request.employment_time,
        employment_type=request.employment_type,
    )
    return _preference_response(preference)
