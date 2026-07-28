"""Health check endpoint.

Deliberately simple and dependency-free at Phase 0: it confirms the
process is up and configuration loaded successfully. Once Phase 1 adds a
real database, this is the natural place to add a `/health/ready`
variant that also checks DB/Redis connectivity, kept separate from this
liveness check so a slow dependency doesn't cause an orchestrator to
kill a healthy process.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    app_name: str
    app_env: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Liveness check: process is running and settings loaded."""
    settings = get_settings()
    return HealthResponse(status="ok", app_name=settings.app_name, app_env=settings.app_env)
