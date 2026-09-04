"""Health check endpoints."""

import asyncio

import redis.asyncio as redis
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import _get_engine
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


async def _check_database() -> bool:
    async def query_database() -> None:
        async with _get_engine().connect() as connection:
            await connection.execute(text("SELECT 1"))

    try:
        await asyncio.wait_for(query_database(), timeout=5)
    except Exception:
        return False
    return True


async def _check_redis() -> bool:
    client = redis.from_url(get_settings().redis_url, socket_connect_timeout=5)
    try:
        await asyncio.wait_for(client.ping(), timeout=5)
    except Exception:
        return False
    finally:
        await client.aclose()
    return True


@router.get("/ready")
async def readiness() -> JSONResponse:
    database_ok, redis_ok = await asyncio.gather(_check_database(), _check_redis())
    checks = {
        "database": "ok" if database_ok else "error",
        "redis": "ok" if redis_ok else "error",
    }
    if database_ok and redis_ok:
        return JSONResponse(status_code=200, content={"status": "ready", "checks": checks})
    return JSONResponse(
        status_code=503,
        content={"status": "not_ready", "checks": checks},
    )
