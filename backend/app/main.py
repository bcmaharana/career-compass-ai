"""Application entry point.

Assembles the FastAPI app: middleware, routers, and exception handlers.
Contains no business logic — this file's only job is wiring.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.api.middleware.error_handling import register_exception_handlers
from app.api.middleware.request_context import RequestContextMiddleware
from app.api.v1.ai_platform.router import router as ai_platform_router
from app.api.v1.career_intelligence.router import router as career_intelligence_router
from app.api.v1.career_profile.router import router as career_profile_router
from app.api.v1.chat.router import router as chat_router
from app.api.v1.health import router as health_router
from app.api.v1.identity.router import router as identity_router
from app.api.v1.interview_prep.router import router as interview_prep_router
from app.api.v1.jd_tailoring.router import router as jd_tailoring_router
from app.api.v1.job_application_tracking.router import router as job_application_tracking_router
from app.api.v1.learning_intelligence.router import router as learning_intelligence_router
from app.api.v1.opportunity_intelligence.router import router as opportunity_intelligence_router
from app.api.v1.platform_admin.router import router as platform_admin_router
from app.api.v1.public_sharing.router import router as public_sharing_router
from app.api.v1.quotes.router import router as quotes_router
from app.api.v1.recruiter_contacts.router import router as recruiter_contacts_router
from app.api.v1.resume_intelligence.router import router as resume_intelligence_router
from app.api.v1.showcase_page.router import router as showcase_page_router
from app.api.v1.skill_intelligence.router import router as skill_intelligence_router
from app.api.v1.system_status.router import router as system_status_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Career Compass AI API",
        version="0.1.0",
        description="Enterprise AI-native career intelligence platform — Phase 2 foundation.",
        debug=settings.debug,
    )

    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(identity_router, prefix="/api/v1")
    app.include_router(career_profile_router, prefix="/api/v1")
    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(quotes_router, prefix="/api/v1")
    app.include_router(skill_intelligence_router, prefix="/api/v1")
    app.include_router(ai_platform_router, prefix="/api/v1")
    app.include_router(career_intelligence_router, prefix="/api/v1")
    app.include_router(resume_intelligence_router, prefix="/api/v1")
    app.include_router(system_status_router, prefix="/api/v1")
    app.include_router(platform_admin_router, prefix="/api/v1")
    app.include_router(opportunity_intelligence_router, prefix="/api/v1")
    app.include_router(learning_intelligence_router, prefix="/api/v1")
    app.include_router(interview_prep_router, prefix="/api/v1")
    app.include_router(jd_tailoring_router, prefix="/api/v1")
    app.include_router(job_application_tracking_router, prefix="/api/v1")
    app.include_router(recruiter_contacts_router, prefix="/api/v1")
    app.include_router(showcase_page_router, prefix="/api/v1")
    app.include_router(public_sharing_router, prefix="/api/v1")

    logger.info("app_startup", app_env=settings.app_env)
    return app


app = create_app()
