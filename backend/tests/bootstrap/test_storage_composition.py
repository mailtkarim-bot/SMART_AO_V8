from __future__ import annotations

from pathlib import Path

import pytest
from app.bootstrap import application
from app.modules.preparation.infrastructure.document_storage import (
    LocalGeneratedDocumentStorage,
)


def test_app_runtime_uses_local_storage_by_default(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("SMART_AO_OBJECT_STORAGE_ENABLED", raising=False)
    monkeypatch.setenv("SMART_AO_DCE_QUARANTINE_ROOT", str(tmp_path))

    storage = application._build_preparation_storage()

    assert isinstance(storage, LocalGeneratedDocumentStorage)


def test_app_runtime_requires_bucket_when_object_storage_enabled(monkeypatch) -> None:
    monkeypatch.setenv("SMART_AO_OBJECT_STORAGE_ENABLED", "1")
    monkeypatch.delenv("SMART_AO_OBJECT_STORAGE_BUCKET", raising=False)

    with pytest.raises(RuntimeError, match="BUCKET"):
        application._build_preparation_storage()


def test_app_runtime_builds_s3_storage_only_when_enabled(monkeypatch) -> None:
    class FakeS3Storage:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    monkeypatch.setenv("SMART_AO_OBJECT_STORAGE_ENABLED", "1")
    monkeypatch.setenv("SMART_AO_OBJECT_STORAGE_BUCKET", "private-documents")
    monkeypatch.setenv("SMART_AO_OBJECT_STORAGE_ENDPOINT_URL", "http://minio:9000")
    monkeypatch.setenv("SMART_AO_OBJECT_STORAGE_REGION", "eu-west-1")
    monkeypatch.setattr(application, "S3PrivateObjectStorage", FakeS3Storage)

    storage = application._build_preparation_storage()

    assert isinstance(storage, FakeS3Storage)
    assert storage.kwargs == {
        "bucket": "private-documents",
        "endpoint_url": "http://minio:9000",
        "region_name": "eu-west-1",
        "server_side_encryption": "AES256",
    }
