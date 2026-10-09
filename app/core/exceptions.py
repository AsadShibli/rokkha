"""Application errors and the handlers that turn every error into one JSON shape:

{"error": {"code": "...", "message": "...", "details": [...]}}
"""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "BAD_REQUEST"
    message: str = "Bad request."
    headers: dict[str, str] | None = None

    def __init__(self, message: str | None = None, details: list[dict[str, Any]] | None = None):
        self.message = message or self.message
        self.details = details or []
        super().__init__(self.message)


class InvalidCredentialsError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "INVALID_CREDENTIALS"
    message = "Phone or password is incorrect."
    headers = {"WWW-Authenticate": "Bearer"}


class InvalidTokenError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "INVALID_TOKEN"
    message = "Token is missing, invalid, expired or revoked."
    headers = {"WWW-Authenticate": "Bearer"}


class AccountDisabledError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "ACCOUNT_DISABLED"
    message = "This account is disabled."


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "FORBIDDEN"
    message = "Your role is not allowed to do this."


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"
    message = "Resource not found."


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"
    message = "Resource already exists."


class ValidationFailedError(AppError):
    """422 raised by a service (e.g. a referenced row does not exist)."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "VALIDATION_ERROR"
    message = "Some fields are invalid."


class InvalidTransitionError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "INVALID_TRANSITION"
    message = "This status change is not allowed from the current status."


class ActiveSosExistsError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "ACTIVE_SOS_EXISTS"
    message = "You already have an open SOS."


class OfficerUnavailableError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "OFFICER_UNAVAILABLE"
    message = "That officer can't take this incident (unreachable, other station, or same officer)."


class NoStationError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "NO_STATION"
    message = "No station is configured to take this incident."


class RateLimitedError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "RATE_LIMITED"
    message = "Too many SOS requests. Please wait before trying again."

    def __init__(self, retry_after: int):
        super().__init__()
        self.headers = {"Retry-After": str(retry_after)}


class OfficerBusyError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "OFFICER_BUSY"
    message = "Officer is busy with an incident; resolve it or ask the station to reassign."


def error_body(code: str, message: str, details: list[dict[str, Any]] | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or []}}


def _field_name(err: dict) -> str:
    # ("body", "phone") -> "phone"; ("query", "page") -> "page"; ("body",) -> "body"
    loc = err["loc"]
    if err["type"] == "json_invalid" or len(loc) == 1:
        return str(loc[0])
    return ".".join(str(p) for p in loc[1:])


def _clean_message(msg: str) -> str:
    # Pydantic prefixes messages from custom validators with "Value error, ".
    return msg.removeprefix("Value error, ")


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        error_body(exc.code, exc.message, exc.details),
        status_code=exc.status_code,
        headers=exc.headers,
    )


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {"field": _field_name(err), "message": _clean_message(err["msg"])} for err in exc.errors()
    ]
    return JSONResponse(
        error_body("VALIDATION_ERROR", "Some fields are invalid.", details),
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )


async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    # Framework-raised errors (unknown route, wrong method, ...) keep the same shape.
    phrase = HTTPStatus(exc.status_code).phrase
    code = phrase.upper().replace(" ", "_").replace("-", "_")
    message = exc.detail if isinstance(exc.detail, str) else phrase
    return JSONResponse(error_body(code, message), status_code=exc.status_code, headers=exc.headers)


async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error", exc_info=exc)
    return JSONResponse(
        error_body("INTERNAL_ERROR", "Something went wrong."),
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
