# Backend Architecture — Career Compass AI

## Layering Rules

| Layer | May depend on | Must NOT depend on | Contains |
|---|---|---|---|
| `api/` | `application/`, `core/` | `domain/` internals directly, `adapters/`, DB | Routers, request/response Pydantic models, middleware wiring |
| `application/` | `domain/`, repository *interfaces* | concrete adapters, DB driver, FastAPI | Use-case orchestration, transaction boundaries |
| `domain/` | nothing framework-related | FastAPI, SQLAlchemy, Pydantic (uses plain dataclasses or attrs) | Business rules, invariants, domain exceptions |
| `adapters/` | `domain/` port interfaces, external SDKs | `api/`, `application/` | SQLAlchemy repositories, Redis client, S3 client, AI provider SDKs, IdP SDKs |
| `core/` | nothing above | — | Config, logging, security primitives, cross-cutting interfaces |

The dependency arrow always points **down**. `domain/` is the one folder with zero framework imports — this is what keeps business rules testable without spinning up a database or an HTTP server.

## Why FastAPI

Native async support, automatic OpenAPI generation (which the frontend's typed API client is generated from), and Pydantic v2 integration for request/response validation at the boundary. Routers stay thin: parse input, call one application service method, return its result. No `if`/`else` business logic in a router — that's a signal it belongs in an application or domain service.

## Dependency Injection

FastAPI's `Depends()` system wires concrete adapters into application services at the API layer, so application services and domain services only ever see interfaces:

```python
# api layer wires the concrete adapter in
def get_user_repository(session: AsyncSession = Depends(get_db_session)) -> UserRepository:
    return SqlAlchemyUserRepository(session)

# application service only knows the interface
class RegisterUserService:
    def __init__(self, users: UserRepository):
        self._users = users
```

This keeps `application/` and `domain/` testable with fakes/mocks and free of any FastAPI import.

## Configuration

`app/core/config.py` uses `pydantic-settings` to load from environment variables (`.env` locally, real environment in deployed environments), validated at startup — a missing or malformed required setting fails fast rather than surfacing as a runtime error mid-request.

## Logging

Structured JSON logging (`app/core/logging.py`) so log lines are machine-parseable in production. Every log line Phase-0-onward includes a request ID; tenant ID and user ID are added once the tenant/auth middleware exists (Phase 1).

## Exception Handling

`app/core/exceptions.py` defines a small hierarchy of domain-safe exceptions (`NotFoundError`, `ValidationError`, `ConflictError`, `UnauthorizedError`, `ForbiddenError`) that domain/application code raises without knowing about HTTP. A FastAPI exception handler in `app/api/middleware/error_handling.py` maps each to the appropriate HTTP status and a consistent JSON error shape. This keeps `domain/` free of any concept of "HTTP 404."

## Type Checking

`mypy --strict` is the project-wide default and applies in full to `domain/`, `application/`, `api/`, `ai_platform/`, and `core/`. One narrowly-scoped override exists for `app.adapters.db.*`, where SQLAlchemy's ORM layer (`relationship()`, hybrid properties, session-bound query results) makes full strict-mode compliance impractical without annotation overhead that doesn't correspond to real type-safety gains. No other adapter package is exempted — `adapters/identity_providers/` and `adapters/ai_providers/` run under full strict mode, since they don't share SQLAlchemy's dynamic-typing constraints. See `backend/pyproject.toml`'s `[[tool.mypy.overrides]]` block for the exact scope.

## Testing Strategy

- **`tests/unit/`** — domain and application services tested with in-memory fakes, no DB, no network. Fast, run on every save.
- **`tests/integration/`** — API endpoints tested against a real (test) database and the FastAPI `TestClient`/`httpx.AsyncClient`, verifying wiring end-to-end within the backend.
- **`tests/e2e/`** — reserved for full-stack flows once the frontend exists; empty scaffold in Phase 0.

## Phase 0 Contents

Only the skeleton: `core/`, health-check router, middleware scaffolding, the identity-provider and LLM-provider *interfaces* (no implementations beyond an in-memory/stub used for tests), and the test harness itself. Real domain entities, repositories, and business logic begin in Phase 1.
