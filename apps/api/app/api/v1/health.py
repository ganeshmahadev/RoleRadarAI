from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import SessionDep
from app.core.errors import AppError
from app.providers.decision import DecisionProvider
from app.providers.factory import get_decision_provider

router = APIRouter(prefix="/health", tags=["health"])


class HealthStatus(BaseModel):
    status: str
    detail: str | None = None


@router.get("", response_model=HealthStatus)
async def health() -> HealthStatus:
    return HealthStatus(status="ok")


@router.get("/database", response_model=HealthStatus)
async def health_database(session: SessionDep, response: Response) -> HealthStatus:
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthStatus(status="unavailable", detail=type(exc).__name__)
    return HealthStatus(status="ok")


@router.get("/openjev", response_model=HealthStatus)
async def health_openjev(
    provider: Annotated[DecisionProvider, Depends(get_decision_provider)], response: Response
) -> HealthStatus:
    try:
        info = await provider.model_info()
    except AppError as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthStatus(status="unavailable", detail=exc.message)
    return HealthStatus(status="ok", detail=info.revision)
