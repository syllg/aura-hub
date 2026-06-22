from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class DependencyUnavailableError(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, status_code=503)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


async def app_error_handler(request: Request, exc: Exception) -> ORJSONResponse:
    if not isinstance(exc, AppError):
        raise exc
    return ORJSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": _request_id(request),
            }
        },
    )


async def validation_error_handler(request: Request, exc: Exception) -> ORJSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    errors = exc.errors()
    code = (
        "INVALID_QUESTION"
        if any(error.get("loc", ())[-1:] == ("question",) for error in errors)
        else "REQUEST_VALIDATION_ERROR"
    )
    return ORJSONResponse(
        status_code=422,
        content={
            "error": {
                "code": code,
                "message": "Request tidak valid.",
                "details": {"errors": errors},
                "request_id": _request_id(request),
            }
        },
    )


async def unexpected_error_handler(request: Request, exc: Exception) -> ORJSONResponse:
    logger.exception(
        "unexpected_error request_id=%s exception_type=%s",
        _request_id(request),
        type(exc).__name__,
    )
    return ORJSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Terjadi kesalahan internal.",
                "details": {},
                "request_id": _request_id(request),
            }
        },
    )
