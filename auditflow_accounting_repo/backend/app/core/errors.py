from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


def register_exception_handlers(application: FastAPI) -> None:
    application.add_exception_handler(
        StarletteHTTPException,
        http_exception_handler,
    )
    application.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,
    )
    application.add_exception_handler(Exception, unhandled_exception_handler)


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    message = str(exc.detail)
    return _error_response(
        request=request,
        status_code=exc.status_code,
        code=_http_error_code(exc.status_code),
        message=message,
        detail=exc.detail,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    details = jsonable_encoder(exc.errors())
    return _error_response(
        request=request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="validation_error",
        message="Request validation failed.",
        detail=details,
        details=details,
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.error(
        "Unhandled request error",
        extra={
            "structured_fields": {
                "request_id": _request_id(request),
                "method": request.method,
                "path": request.url.path,
                "error_type": exc.__class__.__name__,
            }
        },
    )
    return _error_response(
        request=request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="internal_server_error",
        message="Internal server error.",
        detail="Internal server error.",
    )


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    detail: Any,
    details: Any | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(
            {
                "detail": detail,
                "error": {
                    "code": code,
                    "message": message,
                    "request_id": request_id,
                    "details": details,
                },
            }
        ),
        headers={"X-Request-ID": request_id},
    )


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "")) or "unknown"


def _http_error_code(status_code: int) -> str:
    if status_code == status.HTTP_400_BAD_REQUEST:
        return "bad_request"
    if status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE:
        return "request_entity_too_large"
    if status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE:
        return "unsupported_media_type"
    if status_code == status.HTTP_404_NOT_FOUND:
        return "not_found"
    return "http_error"
