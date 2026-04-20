from fastapi import FastAPI

from app.api.analysis import router as analysis_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title=settings.app_name)
    application.include_router(health_router)
    application.include_router(documents_router)
    application.include_router(analysis_router)
    return application


app = create_app()
