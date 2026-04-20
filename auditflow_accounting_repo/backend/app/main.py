import time
from uuid import uuid4

from fastapi import FastAPI, Request
from starlette.responses import Response

from app.api.analysis import router as analysis_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)

OPENAPI_TAGS = [
    {"name": "health", "description": "Runtime health checks."},
    {"name": "documents", "description": "Document ingestion endpoints."},
    {
        "name": "analysis",
        "description": "Structured accounting-process analysis endpoints.",
    },
]


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.app_env)
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "Backend API for ingesting accounting-process documents and "
            "assembling structured analysis payloads for downstream consumers."
        ),
        openapi_tags=OPENAPI_TAGS,
    )

    @application.middleware("http")
    async def request_tracing_middleware(
        request: Request,
        call_next,
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        started_at = time.perf_counter()

        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "HTTP request completed",
            extra={
                "structured_fields": {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                }
            },
        )
        return response

    register_exception_handlers(application)
    application.include_router(health_router)
    application.include_router(documents_router)
    application.include_router(analysis_router)
    return application


app = create_app()
