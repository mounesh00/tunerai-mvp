"""Tests for project consistency of training and deployment inputs."""

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.schemas.deployment import DeploymentCreate
from app.schemas.training import TrainingRunCreate
from app.services import deployment as deployment_service
from app.services import training as training_service


def make_db():
    db = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    return db


async def test_create_training_run_rejects_dataset_version_from_other_project(monkeypatch):
    project = SimpleNamespace(id=uuid4(), organization_id=uuid4())
    dataset = SimpleNamespace(project_id=uuid4())
    version = SimpleNamespace(id=uuid4(), dataset_id=uuid4(), status="ready")
    db = make_db()
    monkeypatch.setattr(training_service, "get_project_for_user", AsyncMock(return_value=project))
    monkeypatch.setattr(training_service, "require_org_role", AsyncMock())
    monkeypatch.setattr(training_service, "get_version_for_user", AsyncMock(return_value=version))
    monkeypatch.setattr(training_service, "get_dataset_for_user", AsyncMock(return_value=dataset))

    with pytest.raises(ValueError, match="Dataset version does not belong to this project"):
        await training_service.create_training_run(
            db,
            uuid4(),
            TrainingRunCreate(project_id=project.id, dataset_version_id=version.id, base_model="model"),
        )

    db.add.assert_not_called()


async def test_create_training_run_accepts_dataset_version_from_same_project(monkeypatch):
    project = SimpleNamespace(id=uuid4(), organization_id=uuid4())
    dataset = SimpleNamespace(project_id=project.id)
    version = SimpleNamespace(id=uuid4(), dataset_id=uuid4(), status="ready", valid_records=10)
    db = make_db()
    run_training_job = SimpleNamespace(delay=MagicMock())
    monkeypatch.setattr(training_service, "get_project_for_user", AsyncMock(return_value=project))
    monkeypatch.setattr(training_service, "require_org_role", AsyncMock())
    monkeypatch.setattr(training_service, "get_version_for_user", AsyncMock(return_value=version))
    monkeypatch.setattr(training_service, "get_dataset_for_user", AsyncMock(return_value=dataset))
    monkeypatch.setattr(training_service, "resolve_config", MagicMock(return_value={"epochs": 3}))
    monkeypatch.setattr(
        training_service,
        "estimate_resources",
        MagicMock(return_value={"estimated_vram_gb": 1, "estimated_time_minutes": 2, "estimated_cost_usd": 3}),
    )
    monkeypatch.setitem(sys.modules, "workers.tasks", SimpleNamespace(run_training_job=run_training_job))

    run = await training_service.create_training_run(
        db,
        uuid4(),
        TrainingRunCreate(project_id=project.id, dataset_version_id=version.id, base_model="model"),
    )

    assert run.project_id == project.id
    assert run.dataset_version_id == version.id
    assert db.add.call_count == 2


async def test_create_deployment_rejects_model_version_from_other_project(monkeypatch):
    project = SimpleNamespace(id=uuid4(), organization_id=uuid4())
    model = SimpleNamespace(project_id=uuid4())
    version = SimpleNamespace(id=uuid4(), model_id=uuid4(), status="READY")
    db = make_db()
    monkeypatch.setattr(deployment_service, "get_project_for_user", AsyncMock(return_value=project))
    monkeypatch.setattr(deployment_service, "require_org_role", AsyncMock())
    monkeypatch.setattr(deployment_service, "get_model_version_for_user", AsyncMock(return_value=version))
    monkeypatch.setattr(deployment_service, "get_model_for_user", AsyncMock(return_value=model))

    with pytest.raises(ValueError, match="Model version does not belong to this project"):
        await deployment_service.create_deployment(
            db,
            uuid4(),
            DeploymentCreate(project_id=project.id, model_version_id=version.id, name="Deployment"),
        )

    db.add.assert_not_called()


async def test_create_deployment_accepts_model_version_from_same_project(monkeypatch):
    project = SimpleNamespace(id=uuid4(), organization_id=uuid4())
    model = SimpleNamespace(project_id=project.id)
    version = SimpleNamespace(id=uuid4(), model_id=uuid4(), status="READY", base_model="model")
    db = make_db()
    register_mock = MagicMock()
    monkeypatch.setattr(deployment_service, "get_project_for_user", AsyncMock(return_value=project))
    monkeypatch.setattr(deployment_service, "require_org_role", AsyncMock())
    monkeypatch.setattr(deployment_service, "get_model_version_for_user", AsyncMock(return_value=version))
    monkeypatch.setattr(deployment_service, "get_model_for_user", AsyncMock(return_value=model))
    monkeypatch.setattr(deployment_service, "_slug", MagicMock(return_value="slug"))
    monkeypatch.setattr(deployment_service.global_inference, "register_mock", register_mock)

    deployment = await deployment_service.create_deployment(
        db,
        uuid4(),
        DeploymentCreate(project_id=project.id, model_version_id=version.id, name="Deployment"),
    )

    assert deployment.project_id == project.id
    assert deployment.model_version_id == version.id
    assert db.add.call_count == 1