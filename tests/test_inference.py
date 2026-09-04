"""Tests for authenticated OpenAI-compatible inference."""

from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.main import app
from app.services import deployment as deployment_service
from ml.inference.openai_api import global_inference


REQUEST_BODY = {
    "model": "tunerai/demo-slug",
    "messages": [{"role": "user", "content": "hello"}],
    "max_tokens": 64,
    "temperature": 0.1,
}


@pytest.fixture
def client():
    async def override_get_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    test_client.close()
    app.dependency_overrides.clear()


def test_chat_completions_missing_authorization_returns_401(client):
    response = client.post("/v1/chat/completions", json=REQUEST_BODY)

    assert response.status_code == 401
    assert response.json() == {"detail": "Missing or invalid API key"}


def test_chat_completions_invalid_api_key_returns_401(client, monkeypatch):
    verify_api_key = AsyncMock(return_value=None)
    monkeypatch.setattr(deployment_service, "verify_api_key", verify_api_key)

    response = client.post(
        "/v1/chat/completions",
        json=REQUEST_BODY,
        headers={"Authorization": "Bearer tai_invalid"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid API key"}
    verify_api_key.assert_awaited_once()


def test_chat_completions_model_without_tunerai_prefix_returns_400(client, monkeypatch):
    api_key = SimpleNamespace(organization_id=uuid4())
    monkeypatch.setattr(
        deployment_service, "verify_api_key", AsyncMock(return_value=api_key)
    )

    response = client.post(
        "/v1/chat/completions",
        json={**REQUEST_BODY, "model": "demo-slug"},
        headers={"Authorization": "Bearer tai_valid"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Unknown model. Use tunerai/<endpoint_slug>."}


def test_chat_completions_unknown_or_other_org_deployment_returns_404(client, monkeypatch):
    organization_id = uuid4()
    api_key = SimpleNamespace(organization_id=organization_id)
    get_deployment_by_slug = AsyncMock(return_value=None)
    monkeypatch.setattr(
        deployment_service, "verify_api_key", AsyncMock(return_value=api_key)
    )
    monkeypatch.setattr(
        deployment_service, "get_deployment_by_slug", get_deployment_by_slug
    )

    response = client.post(
        "/v1/chat/completions",
        json=REQUEST_BODY,
        headers={"Authorization": "Bearer tai_valid"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Deployment not found"}
    get_deployment_by_slug.assert_awaited_once_with(
        ANY, organization_id, "demo-slug"
    )


def test_chat_completions_success_returns_200_and_calls_generate(client, monkeypatch):
    api_key = SimpleNamespace(organization_id=uuid4())
    deployment = SimpleNamespace()
    response_payload = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
    register_mock = MagicMock()
    generate = MagicMock(return_value=response_payload)
    monkeypatch.setattr(
        deployment_service, "verify_api_key", AsyncMock(return_value=api_key)
    )
    monkeypatch.setattr(
        deployment_service, "get_deployment_by_slug", AsyncMock(return_value=deployment)
    )
    monkeypatch.setattr(global_inference, "register_mock", register_mock)
    monkeypatch.setattr(global_inference, "generate", generate)

    response = client.post(
        "/v1/chat/completions",
        json=REQUEST_BODY,
        headers={"Authorization": "Bearer tai_valid"},
    )

    assert response.status_code == 200
    assert response.json() == response_payload
    register_mock.assert_called_once_with("tunerai/demo-slug")
    generate.assert_called_once_with(
        "tunerai/demo-slug",
        [{"role": "user", "content": "hello"}],
        max_tokens=64,
        temperature=0.1,
    )
