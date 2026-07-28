"""Integration test for GET /api/v1/health.

Exercises the app through the ASGI interface end-to-end (middleware +
router + response model), rather than calling the router function
directly — this is what distinguishes an integration test from a unit
test in this codebase.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.integration
async def test_health_check_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app_name"] == "career-compass-ai"


@pytest.mark.integration
async def test_health_check_response_includes_request_id_header(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/health")

    assert "x-request-id" in response.headers


@pytest.mark.integration
async def test_health_check_response_has_no_store_cache_control(client: AsyncClient) -> None:
    """Every API response must tell the browser never to cache it — this
    is a fully dynamic, per-tenant API, and a cached response here means
    a client could see stale data indefinitely. See
    app/api/middleware/request_context.py.
    """
    response = await client.get("/api/v1/health")

    assert response.headers["cache-control"] == "no-store"
