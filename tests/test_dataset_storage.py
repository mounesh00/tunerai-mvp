"""Focused tests for dataset object storage and access controls."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.api.v1 import datasets as datasets_api
from app.schemas.dataset import DatasetVersionRead
from app.services import dataset as dataset_service
from app.utils.storage import (
    calculate_content_hash,
    generate_safe_object_key,
    sanitize_filename,
)


class StorageClientContext:
    def __init__(self, client):
        self.client = client

    async def __aenter__(self):
        return self.client

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False


def make_dataset():
    return SimpleNamespace(
        id=uuid4(), organization_id=uuid4(), project_id=uuid4(), versions=[], status="uploaded"
    )


def make_db(existing_content=None, flush_error=None):
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=existing_content)
        )
    )
    db.flush = AsyncMock(side_effect=flush_error)
    db.refresh = AsyncMock()
    return db


def test_sanitize_filename_prevents_path_traversal():
    assert sanitize_filename("../../unsafe\\name?.jsonl") == "unsafe_name_.jsonl"


def test_generate_safe_object_key_uses_tenant_scope_and_sanitized_filename():
    key = generate_safe_object_key("org", "project", "dataset", "v1", "../data.jsonl")
    assert key.startswith("organizations/org/projects/project/datasets/dataset/versions/v1/")
    assert key.endswith("-data.jsonl")


def test_calculate_content_hash_uses_sha256():
    assert calculate_content_hash(b"dataset") == "b277fd623676a525c29b9eb155afc8c9010681814ceafb2d7627f47b9a232576"


def test_dataset_version_response_hides_storage_path():
    version = SimpleNamespace(
        id=uuid4(),
        dataset_id=uuid4(),
        version="v1",
        storage_path="organizations/private-key",
        original_filename="data.jsonl",
        format="instruction",
        total_records=1,
        valid_records=1,
        invalid_records=0,
        duplicate_count=0,
        duplicate_percentage=0.0,
        content_hash="abc",
        file_size_bytes=7,
        avg_tokens=1.0,
        max_tokens=1.0,
        estimated_training_tokens=1,
        train_size=1,
        validation_size=0,
        quality_score=100.0,
        quality_report={},
        warnings=[],
        status="ready",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    response = DatasetVersionRead.model_validate(version)
    assert "storage_path" not in response.model_dump()


async def test_uploads_to_r2_and_persists_safe_key(monkeypatch):
    dataset = make_dataset()
    db = make_db()
    client = SimpleNamespace(put_object=AsyncMock())
    monkeypatch.setattr(dataset_service, "get_dataset_for_user", AsyncMock(return_value=dataset))
    monkeypatch.setattr(dataset_service, "require_org_role", AsyncMock())
    monkeypatch.setattr(dataset_service, "_storage_client", lambda: StorageClientContext(client))

    version = await dataset_service.upload_and_validate(
        db, uuid4(), dataset.id, "../training.jsonl", b'{"instruction":"a","output":"b"}\n'
    )

    assert version.storage_path.endswith("-training.jsonl")
    assert version.content_hash == calculate_content_hash(b'{"instruction":"a","output":"b"}\n')
    assert version.file_size_bytes == len(b'{"instruction":"a","output":"b"}\n')
    client.put_object.assert_awaited_once()
    assert client.put_object.await_args.kwargs["Key"] == version.storage_path


async def test_upload_storage_failure_does_not_persist(monkeypatch):
    dataset = make_dataset()
    db = make_db()
    client = SimpleNamespace(
        put_object=AsyncMock(
            side_effect=ClientError({"Error": {"Code": "SlowDown"}}, "PutObject")
        )
    )
    monkeypatch.setattr(dataset_service, "get_dataset_for_user", AsyncMock(return_value=dataset))
    monkeypatch.setattr(dataset_service, "require_org_role", AsyncMock())
    monkeypatch.setattr(dataset_service, "_storage_client", lambda: StorageClientContext(client))

    with pytest.raises(dataset_service.StorageError):
        await dataset_service.upload_and_validate(
            db, uuid4(), dataset.id, "training.jsonl", b'{"instruction":"a","output":"b"}\n'
        )
    db.add.assert_not_called()


async def test_upload_cleans_up_r2_object_when_persistence_fails(monkeypatch):
    dataset = make_dataset()
    db = make_db(flush_error=RuntimeError("database unavailable"))
    client = SimpleNamespace(put_object=AsyncMock(), delete_object=AsyncMock())
    monkeypatch.setattr(dataset_service, "get_dataset_for_user", AsyncMock(return_value=dataset))
    monkeypatch.setattr(dataset_service, "require_org_role", AsyncMock())
    monkeypatch.setattr(dataset_service, "_storage_client", lambda: StorageClientContext(client))

    with pytest.raises(dataset_service.StoragePersistenceError):
        await dataset_service.upload_and_validate(
            db, uuid4(), dataset.id, "training.jsonl", b'{"instruction":"a","output":"b"}\n'
        )
    assert client.delete_object.await_args.kwargs["Key"] == client.put_object.await_args.kwargs["Key"]


async def test_upload_rejects_duplicate_content_without_uploading(monkeypatch):
    dataset = make_dataset()
    db = make_db(existing_content=uuid4())
    client = SimpleNamespace(put_object=AsyncMock())
    monkeypatch.setattr(dataset_service, "get_dataset_for_user", AsyncMock(return_value=dataset))
    monkeypatch.setattr(dataset_service, "require_org_role", AsyncMock())
    monkeypatch.setattr(dataset_service, "_storage_client", lambda: StorageClientContext(client))

    with pytest.raises(ValueError, match="already been uploaded"):
        await dataset_service.upload_and_validate(
            db, uuid4(), dataset.id, "training.jsonl", b'{"instruction":"a","output":"b"}\n'
        )
    client.put_object.assert_not_awaited()


async def test_upload_cleans_up_and_rejects_concurrent_duplicate_content(monkeypatch):
    class DuplicateViolation(Exception):
        constraint_name = "uq_dataset_versions_dataset_content_hash"

    dataset = make_dataset()
    db = make_db(
        flush_error=IntegrityError("INSERT", {}, DuplicateViolation())
    )
    client = SimpleNamespace(put_object=AsyncMock(), delete_object=AsyncMock())
    monkeypatch.setattr(dataset_service, "get_dataset_for_user", AsyncMock(return_value=dataset))
    monkeypatch.setattr(dataset_service, "require_org_role", AsyncMock())
    monkeypatch.setattr(dataset_service, "_storage_client", lambda: StorageClientContext(client))

    with pytest.raises(dataset_service.DuplicateContentError, match="already been uploaded"):
        await dataset_service.upload_and_validate(
            db, uuid4(), dataset.id, "training.jsonl", b'{"instruction":"a","output":"b"}\n'
        )

    assert client.delete_object.await_args.kwargs["Key"] == client.put_object.await_args.kwargs["Key"]


async def test_download_url_is_presigned_only_for_matching_dataset(monkeypatch):
    dataset_id = uuid4()
    version = SimpleNamespace(dataset_id=dataset_id, storage_path="organizations/private-key")
    client = SimpleNamespace(generate_presigned_url=AsyncMock(return_value="https://r2.example/signed"))
    monkeypatch.setattr(dataset_service, "get_version_for_user", AsyncMock(return_value=version))
    monkeypatch.setattr(dataset_service, "_storage_client", lambda: StorageClientContext(client))

    url = await dataset_service.get_download_url_for_user(MagicMock(), uuid4(), dataset_id, uuid4())
    assert url == "https://r2.example/signed"
    assert client.generate_presigned_url.await_args.kwargs["ExpiresIn"] == 900


async def test_download_url_rejects_unauthorized_or_mismatched_dataset(monkeypatch):
    client = SimpleNamespace(generate_presigned_url=AsyncMock())
    monkeypatch.setattr(dataset_service, "get_version_for_user", AsyncMock(return_value=None))
    monkeypatch.setattr(dataset_service, "_storage_client", lambda: StorageClientContext(client))

    assert await dataset_service.get_download_url_for_user(MagicMock(), uuid4(), uuid4(), uuid4()) is None
    client.generate_presigned_url.assert_not_awaited()


async def test_dataset_lookup_rejects_user_outside_its_organization(monkeypatch):
    dataset = make_dataset()
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=dataset))
    )
    monkeypatch.setattr(dataset_service, "user_belongs_to_org", AsyncMock(return_value=False))

    assert await dataset_service.get_dataset_for_user(db, uuid4(), dataset.id) is None


async def test_download_endpoint_returns_presigned_url_and_hides_object_key(monkeypatch):
    monkeypatch.setattr(
        dataset_service,
        "get_download_url_for_user",
        AsyncMock(return_value="https://r2.example/signed"),
    )
    response = await datasets_api.get_dataset_download_url(uuid4(), uuid4(), MagicMock(), SimpleNamespace(id=uuid4()))
    assert response == {"url": "https://r2.example/signed"}
    assert "storage_path" not in response


async def test_download_endpoint_rejects_unauthorized_version(monkeypatch):
    monkeypatch.setattr(dataset_service, "get_download_url_for_user", AsyncMock(return_value=None))

    with pytest.raises(HTTPException) as error:
        await datasets_api.get_dataset_download_url(uuid4(), uuid4(), MagicMock(), SimpleNamespace(id=uuid4()))
    assert error.value.status_code == 404