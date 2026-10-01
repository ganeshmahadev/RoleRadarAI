from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import AppError


async def app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Structured errors: {detail: {code, message, retryable}} (PRD §65)."""
    assert isinstance(exc, AppError)
    return JSONResponse(
        status_code=exc.http_status,
        content={"detail": {"code": exc.code, "message": exc.message, "retryable": exc.retryable}},
    )


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="RoleRadarAI API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(api_router)
    return app


app = create_app()
