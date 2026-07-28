"""Application entry point.

Assembles the FastAPI app: middleware, routers, and exception handlers.
Contains no business logic — this file's only job is wiring.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.api.middleware.error_handling import register_exception_handlers
from app.api.middleware.request_context import RequestContextMiddleware
from app.api.v1.career_profile.router import router as career_profile_router
from app.api.v1.chat.router import router as chat_router
from app.api.v1.health import router as health_router
from app.api.v1.identity.router import router as identity_router
from app.api.v1.quotes.router import router as quotes_router
from app.api.v1.skill_intelligence.router import router as skill_intelligence_router
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

    logger.info("app_startup", app_env=settings.app_env)
    return app


app = create_app()
