"""Tests for health and readiness endpoints."""

import json
from unittest.mock import AsyncMock

from app.api.v1 import health


async def test_readiness_returns_200_when_database_and_redis_are_available(monkeypatch):
    monkeypatch.setattr(health, "_check_database", AsyncMock(return_value=True))
    monkeypatch.setattr(health, "_check_redis", AsyncMock(return_value=True))

    response = await health.readiness()

    assert response.status_code == 200
    assert json.loads(response.body) == {
        "status": "ready",
        "checks": {"database": "ok", "redis": "ok"},
    }


async def test_readiness_returns_503_when_database_check_fails(monkeypatch):
    monkeypatch.setattr(health, "_check_database", AsyncMock(return_value=False))
    monkeypatch.setattr(health, "_check_redis", AsyncMock(return_value=True))

    response = await health.readiness()

    assert response.status_code == 503
    assert json.loads(response.body) == {
        "status": "not_ready",
        "checks": {"database": "error", "redis": "ok"},
    }


async def test_readiness_returns_503_when_redis_check_fails(monkeypatch):
    monkeypatch.setattr(health, "_check_database", AsyncMock(return_value=True))
    monkeypatch.setattr(health, "_check_redis", AsyncMock(return_value=False))

    response = await health.readiness()

    assert response.status_code == 503
    assert json.loads(response.body) == {
        "status": "not_ready",
        "checks": {"database": "ok", "redis": "error"},
    }
