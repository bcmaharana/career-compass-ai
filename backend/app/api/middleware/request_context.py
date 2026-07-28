"""Request context middleware.

Phase 0 responsibility: bind a request ID to every request so log lines
can be correlated, and expose a request-scoped context object other
middleware can populate.

Phase 1 will extend this middleware to also extract and validate
`tenant_id` from the caller's JWT and bind it into the same context (see
docs/architecture/multi-tenancy-design.md) — the seam is established now
so that change is additive, not a rewrite.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Binds a request ID (generated or forwarded) to structlog's
    contextvars for the duration of the request, and echoes it back in
    the response headers so a client can correlate a request with a
    support ticket.

    Also sets `Cache-Control: no-store` on every response. This is an
    entirely dynamic, per-tenant API — nothing it returns should ever be
    served from a browser or intermediary cache instead of a real
    request. Paired with the frontend's `cache: "no-store"` fetch option
    (belt-and-suspenders: either one alone should be sufficient, but
    this closes the possibility from the server side too, regardless of
    what any given client does).
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid.uuid4()))

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        request.state.request_id = request_id
        # Phase 1 adds: request.state.tenant_id = <validated tenant_id>

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers["Cache-Control"] = "no-store"
        return response
