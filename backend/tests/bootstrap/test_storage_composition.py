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


def test_app_runtime_keeps_insee_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("SMART_AO_INSEE_ENABLED", raising=False)
    monkeypatch.delenv("SMART_AO_INSEE_API_TOKEN", raising=False)

    assert application._build_company_registry() is None


def test_app_runtime_requires_insee_token_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("SMART_AO_INSEE_ENABLED", "1")
    monkeypatch.delenv("SMART_AO_INSEE_API_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="INSEE_API_TOKEN"):
        application._build_company_registry()


def test_app_runtime_builds_insee_registry_when_explicitly_enabled(monkeypatch) -> None:
    class FakeRegistry:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    monkeypatch.setenv("SMART_AO_INSEE_ENABLED", "1")
    monkeypatch.setenv("SMART_AO_INSEE_API_TOKEN", "runtime-secret")
    monkeypatch.setattr(application, "InseeSireneRegistry", FakeRegistry)

    registry = application._build_company_registry()

    assert isinstance(registry, FakeRegistry)
    assert registry.kwargs == {
        "token": "runtime-secret",
        "base_url": "https://api.insee.fr/api-sirene/3.11",
        "timeout_seconds": 5.0,
    }


def test_app_runtime_keeps_smtp_notifications_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("SMART_AO_SMTP_ENABLED", raising=False)
    monkeypatch.delenv("SMART_AO_SMTP_HOST", raising=False)
    monkeypatch.delenv("SMART_AO_SMTP_FROM", raising=False)

    assert application._build_submission_export_notifier() is None


def test_app_runtime_requires_smtp_host_and_sender_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("SMART_AO_SMTP_ENABLED", "1")
    monkeypatch.delenv("SMART_AO_SMTP_HOST", raising=False)
    monkeypatch.delenv("SMART_AO_SMTP_FROM", raising=False)

    with pytest.raises(RuntimeError, match="SMTP_HOST"):
        application._build_submission_export_notifier()

    monkeypatch.setenv("SMART_AO_SMTP_HOST", "smtp.example.test")
    with pytest.raises(RuntimeError, match="SMTP_FROM"):
        application._build_submission_export_notifier()


def test_app_runtime_builds_smtp_notifier_when_explicitly_enabled(monkeypatch) -> None:
    class FakeNotifier:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    monkeypatch.setenv("SMART_AO_SMTP_ENABLED", "1")
    monkeypatch.setenv("SMART_AO_SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMART_AO_SMTP_FROM", "no-reply@example.test")
    monkeypatch.setenv("SMART_AO_SMTP_PORT", "465")
    monkeypatch.setenv("SMART_AO_SMTP_USE_TLS", "1")
    monkeypatch.setenv("SMART_AO_SMTP_START_TLS", "")
    monkeypatch.setattr(application, "AioSmtpSubmissionExportNotifier", FakeNotifier)

    notifier = application._build_submission_export_notifier()

    assert isinstance(notifier, FakeNotifier)
    assert notifier.kwargs == {
        "hostname": "smtp.example.test",
        "port": 465,
        "sender": "no-reply@example.test",
        "username": None,
        "password": None,
        "use_tls": True,
        "start_tls": None,
        "timeout_seconds": 10.0,
    }


def test_app_runtime_keeps_calendar_export_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("SMART_AO_CALENDAR_ENABLED", raising=False)

    assert application._build_submission_deadline_calendar() is None


def test_app_runtime_builds_calendar_export_when_explicitly_enabled(monkeypatch) -> None:
    class FakeCalendar:
        pass

    monkeypatch.setenv("SMART_AO_CALENDAR_ENABLED", "1")
    monkeypatch.setattr(application, "IcsSubmissionDeadlineCalendar", FakeCalendar)

    calendar = application._build_submission_deadline_calendar()

    assert isinstance(calendar, FakeCalendar)


def test_app_runtime_keeps_boamp_search_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("SMART_AO_BOAMP_ENABLED", raising=False)

    assert application._build_public_notice_search() is None


def test_app_runtime_builds_boamp_search_when_explicitly_enabled(monkeypatch) -> None:
    class FakeSearch:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    monkeypatch.setenv("SMART_AO_BOAMP_ENABLED", "1")
    monkeypatch.setenv("SMART_AO_BOAMP_BASE_URL", "https://boamp.example.test/records")
    monkeypatch.setenv("SMART_AO_BOAMP_TIMEOUT_SECONDS", "9")
    monkeypatch.setattr(application, "BoampReadOnlySearch", FakeSearch)

    search = application._build_public_notice_search()

    assert isinstance(search, FakeSearch)
    assert search.kwargs == {
        "base_url": "https://boamp.example.test/records",
        "timeout_seconds": 9.0,
    }
