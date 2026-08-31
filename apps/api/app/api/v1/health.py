"""Health check endpoints."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        service="tunerai-api",
        version="0.1.0",
        environment=settings.app_env,
    )


@router.get("/ready")
async def readiness() -> dict:
    # Future: check DB and Redis connectivity
    return {"status": "ready"}
