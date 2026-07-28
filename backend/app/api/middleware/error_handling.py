"""Exception handling.

Maps the domain-safe exception hierarchy (app/core/exceptions.py) to a
consistent JSON error shape and the correct HTTP status code. Domain and
application code never needs to know about HTTP status codes — that
mapping lives entirely here, in the one place the API layer is allowed
to make that decision.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.adapters.storage.s3_object_storage import ObjectStorageError
from app.core.exceptions import (
    CareerCompassError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

_STATUS_BY_EXCEPTION: dict[type[CareerCompassError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ValidationError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ConflictError: status.HTTP_409_CONFLICT,
    UnauthorizedError: status.HTTP_401_UNAUTHORIZED,
    ForbiddenError: status.HTTP_403_FORBIDDEN,
    # Not a malformed request — the client did everything right, an
    # infrastructure dependency (MinIO/S3) is unavailable or misconfigured.
    ObjectStorageError: status.HTTP_503_SERVICE_UNAVAILABLE,
}


def _error_body(*, code: str, message: str, request_id: str | None) -> dict[str, object]:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the given FastAPI app instance."""

    @app.exception_handler(CareerCompassError)
    async def handle_career_compass_error(
        request: Request, exc: CareerCompassError
    ) -> JSONResponse:
        http_status = _STATUS_BY_EXCEPTION.get(type(exc), status.HTTP_400_BAD_REQUEST)
        request_id = getattr(request.state, "request_id", None)

        logger.info(
            "handled_exception",
            error_code=exc.code,
            http_status=http_status,
            request_id=request_id,
        )

        return JSONResponse(
            status_code=http_status,
            content=_error_body(code=exc.code, message=exc.message, request_id=request_id),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)

        # Unexpected exceptions are logged with full detail server-side,
        # but never leaked to the client — the response body is
        # intentionally generic.
        logger.error(
            "unhandled_exception",
            error_type=type(exc).__name__,
            request_id=request_id,
            exc_info=exc,
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred.",
                request_id=request_id,
            ),
        )
