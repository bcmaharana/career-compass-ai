"""Exception handling.

Maps the domain-safe exception hierarchy (app/core/exceptions.py) to a
consistent JSON error shape and the correct HTTP status code. Domain and
application code never needs to know about HTTP status codes — that
mapping lives entirely here, in the one place the API layer is allowed
to make that decision.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
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

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # FastAPI validates the request body/query/path against the
        # route's Pydantic schema *before* the route (or any
        # CareerCompassError it might raise) ever runs — e.g. a request
        # exceeding a Field(max_length=...) constraint, like
        # UpdateCareerProfileRequest.core_competencies' item cap. Without
        # this handler, FastAPI's own default handler responds with its
        # raw {"detail": [...]} shape instead of this app's
        # {"error": {...}} envelope — every other error path in this app
        # (including the frontend's ApiError parsing) assumes the latter
        # unconditionally, so an unwrapped validation error doesn't just
        # look different, it crashes the frontend outright reading
        # `.error.message` off a body with no `error` key at all. This
        # was a real bug, not a theoretical one — caught via that same
        # core_competencies cap.
        request_id = getattr(request.state, "request_id", None)

        messages = []
        for error in exc.errors():
            # `loc` is e.g. ("body", "core_competencies") — drop the
            # leading request-part marker so the message reads as a
            # field name, not an implementation detail the caller has no
            # way to act on.
            field_path = ".".join(
                str(part) for part in error["loc"] if part not in ("body", "query", "path")
            )
            messages.append(f"{field_path}: {error['msg']}" if field_path else error["msg"])
        message = "; ".join(messages) or "Invalid request."

        logger.info(
            "handled_validation_error",
            http_status=status.HTTP_422_UNPROCESSABLE_CONTENT,
            request_id=request_id,
            detail=exc.errors(),
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_error_body(code="VALIDATION_ERROR", message=message, request_id=request_id),
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
