"""Domain-safe exception hierarchy.

Domain and application code raises these exceptions without knowing
anything about HTTP. A FastAPI exception handler
(app/api/middleware/error_handling.py) maps each to the appropriate HTTP
status code and a consistent JSON error shape. This keeps `app/domain/`
free of any concept of "HTTP 404" or "HTTP 409" — those are API-layer
concerns, not business-rule concerns.
"""

from __future__ import annotations


class CareerCompassError(Exception):
    """Base class for all application-defined exceptions."""

    #: Machine-readable error code surfaced in API responses.
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code


class NotFoundError(CareerCompassError):
    """Raised when a requested resource does not exist (or isn't visible
    to the caller's tenant — from the caller's perspective these are the
    same thing, and should be reported identically to avoid leaking
    cross-tenant existence information)."""

    code = "NOT_FOUND"


class ValidationError(CareerCompassError):
    """Raised when input fails a business-rule validation that goes
    beyond what Pydantic's schema validation already covers."""

    code = "VALIDATION_ERROR"


class ConflictError(CareerCompassError):
    """Raised when an operation would violate a uniqueness or state
    invariant (e.g., duplicate email within a tenant)."""

    code = "CONFLICT"


class UnauthorizedError(CareerCompassError):
    """Raised when the caller's identity could not be established or
    verified (missing/invalid/expired credentials)."""

    code = "UNAUTHORIZED"


class ForbiddenError(CareerCompassError):
    """Raised when the caller is authenticated but not permitted to
    perform the requested action (authorization failure, not
    authentication failure)."""

    code = "FORBIDDEN"
