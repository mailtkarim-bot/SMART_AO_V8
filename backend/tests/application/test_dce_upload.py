from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from app.modules.dce.application.handlers import (
    ClaimDceStagedObjectUploadHandler,
    RecordDceStagedObjectQuarantineHandler,
    RecordDceStagedObjectScanHandler,
    RejectDceStagedObjectUploadHandler,
)
from app.modules.dce.application.upload import (
    DceUploadAlreadyClaimedError,
    DceUploadRejectedError,
    DceUploadService,
    MalwareScanResult,
)
from app.modules.dce.infrastructure.models.consultation import ConsultationRecord
from app.modules.dce.infrastructure.models.dce_staging import DceStagedObjectRecord
from app.modules.dce.infrastructure.quarantine import (
    LocalQuarantineStorageAdapter,
    PythonMagicContentInspectionAdapter,
)
from app.platform.events.dispatcher import CommandDispatcher
from app.platform.persistence.models import TenantRecord
from sqlalchemy.orm import Session, sessionmaker

NOW = datetime.now(tz=UTC)


class StaticInspector:
    def __init__(self, *, media_type: str) -> None:
        self._media_type = media_type

    async def detect_media_type(self, *, storage_key: str) -> str:
        return self._media_type


class StaticScanner:
    def __init__(self, *, verdict: str) -> None:
        self._verdict = verdict
        self.calls = 0

    async def scan(self, *, storage_key: str) -> MalwareScanResult:
        self.calls += 1
        return MalwareScanResult(
            verdict=self._verdict,
            scanner_name="test-clamd",
            scanner_signature_version="test-signatures",
            scanned_at=NOW,
        )






@pytest.fixture(autouse=True)
def isolate_dce_upload_records(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


def _seed_awaiting_staged_object(
    session_factory: sessionmaker[Session],
    *,
    expected_byte_size: int,
) -> tuple[UUID, UUID, UUID, str]:
    tenant_id, consultation_id, storage_object_id = uuid4(), uuid4(), uuid4()
    storage_key = f"dce-staging/{tenant_id}/{storage_object_id}"
    with session_factory.begin() as session:
        session.add(
            TenantRecord(
                id=tenant_id,
                slug=f"tenant-{tenant_id.hex[:12]}",
                lifecycle="ACTIVE",
            )
        )
        session.flush()
        session.add(
            ConsultationRecord(
                id=consultation_id,
                tenant_id=tenant_id,
                aggregate_revision=4,
                functional_identity_hash="f" * 64,
                buyer_legal_name="Ville de test",
                buyer_normalized_id="VILLE-TEST",
                external_reference="AO-2026-UPLOAD",
                object_label="Réhabilitation école",
                location_label="Lille",
                source_channel="MANUAL_UPLOAD",
                source_reference="Fixture upload",
                source_received_at=NOW,
                lifecycle="OPEN",
                freshness="CURRENT",
                metadata_history_json=[],
                created_by_actor_id=None,
                updated_by_actor_id=None,
            )
        )
        session.add(
            DceStagedObjectRecord(
                id=storage_object_id,
                tenant_id=tenant_id,
                consultation_id=consultation_id,
                storage_key=storage_key,
                original_filename="Reglement-consultation.pdf",
                expected_byte_size=expected_byte_size,
                actual_byte_size=None,
                sha256=None,
                media_type=None,
                source_channel="MANUAL_UPLOAD",
                state="AWAITING_UPLOAD",
                scan_verdict=None,
                scanner_name=None,
                scanner_signature_version=None,
                scanned_at=None,
                rejection_code=None,
                expires_at=NOW + timedelta(days=1),
                consumed_by_dce_version_id=None,
                consumed_at=None,
                created_by_actor_id=None,
                updated_by_actor_id=None,
            )
        )
    return tenant_id, consultation_id, storage_object_id, storage_key


def _dispatcher(session_factory: sessionmaker[Session]) -> CommandDispatcher:
    return CommandDispatcher(
        session_factory=session_factory,
        handlers={
            "ClaimDceStagedObjectUpload": ClaimDceStagedObjectUploadHandler(),
            "RecordDceStagedObjectQuarantine": RecordDceStagedObjectQuarantineHandler(),
            "RecordDceStagedObjectScan": RecordDceStagedObjectScanHandler(),
            "RejectDceStagedObjectUpload": RejectDceStagedObjectUploadHandler(),
        },
    )


def _service(
    *,
    session_factory: sessionmaker[Session],
    root: Path,
    inspector: StaticInspector,
    scanner: StaticScanner,
    max_bytes: int = 2_000_000_000,
) -> DceUploadService:
    storage = LocalQuarantineStorageAdapter(root=root)
    return DceUploadService(
        dispatcher=_dispatcher(session_factory),
        storage=storage,
        inspector=inspector,
        scanner=scanner,
        allowed_media_types=frozenset({"application/pdf"}),
        max_bytes=max_bytes,
    )


async def _stream(*chunks: bytes) -> AsyncIterable[bytes]:
    for chunk in chunks:
        yield chunk


def test_python_magic_detects_pdf_signature_without_extension(tmp_path: Path) -> None:
    storage = LocalQuarantineStorageAdapter(root=tmp_path)
    storage_key = "dce-staging/opaque-object"
    asyncio.run(
        storage.write(
            storage_key=storage_key,
            stream=_stream(b"%PDF-1.7\\nDCE de test\\n"),
            max_bytes=2_000_000_000,
        )
    )

    inspector = PythonMagicContentInspectionAdapter(storage=storage)
    media_type = asyncio.run(inspector.detect_media_type(storage_key=storage_key))

    assert media_type == "application/pdf"


@pytest.mark.db
@pytest.mark.integration
def test_upload_streams_private_content_hashes_and_marks_clean_after_scan(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    content = b"%PDF-1.7\nDCE de test\n"
    tenant_id, _, storage_object_id, storage_key = _seed_awaiting_staged_object(
        session_factory,
        expected_byte_size=len(content),
    )
    scanner = StaticScanner(verdict="CLEAN")
    service = _service(
        session_factory=session_factory,
        root=tmp_path,
        inspector=StaticInspector(media_type="application/pdf"),
        scanner=scanner,
    )

    result = asyncio.run(
        service.upload(
            tenant_id=tenant_id,
            actor_id=uuid4(),
            actor_kind="PATRON_ADMIN",
            storage_object_id=storage_object_id,
            storage_key=storage_key,
            expected_byte_size=len(content),
            idempotency_key=uuid4(),
            stream=_stream(content[:7], content[7:]),
            content_length=None,
        )
    )

    assert result.state == "CLEAN"
    with session_factory() as session:
        staged_object = session.get(DceStagedObjectRecord, storage_object_id)
    assert staged_object is not None
    assert staged_object.state == "CLEAN"
    assert staged_object.actual_byte_size == len(content)
    assert staged_object.sha256 == sha256(content).hexdigest()
    assert staged_object.media_type == "application/pdf"
    assert staged_object.scan_verdict == "CLEAN"
    assert scanner.calls == 1
    assert (tmp_path / storage_key).read_bytes() == content


@pytest.mark.db
@pytest.mark.integration
def test_upload_enforces_incremental_limit_and_removes_partial_quarantine_file(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    tenant_id, _, storage_object_id, storage_key = _seed_awaiting_staged_object(
        session_factory,
        expected_byte_size=8,
    )
    service = _service(
        session_factory=session_factory,
        root=tmp_path,
        inspector=StaticInspector(media_type="application/pdf"),
        scanner=StaticScanner(verdict="CLEAN"),
        max_bytes=4,
    )

    with pytest.raises(DceUploadRejectedError) as error:
        asyncio.run(
            service.upload(
                tenant_id=tenant_id,
                actor_id=uuid4(),
                actor_kind="PATRON_ADMIN",
                storage_object_id=storage_object_id,
                storage_key=storage_key,
                expected_byte_size=8,
                idempotency_key=uuid4(),
                stream=_stream(b"abc", b"defgh"),
                content_length=None,
            )
        )

    assert error.value.status_code == 413
    with session_factory() as session:
        staged_object = session.get(DceStagedObjectRecord, storage_object_id)
    assert staged_object is not None
    assert staged_object.state == "REJECTED"
    assert staged_object.rejection_code == "UPLOAD_LIMIT_EXCEEDED"
    assert not (tmp_path / storage_key).exists()


@pytest.mark.db
@pytest.mark.integration
def test_upload_rejects_signature_type_outside_allow_list_without_scanning(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    content = b"MZ fake executable"
    tenant_id, _, storage_object_id, storage_key = _seed_awaiting_staged_object(
        session_factory,
        expected_byte_size=len(content),
    )
    scanner = StaticScanner(verdict="CLEAN")
    service = _service(
        session_factory=session_factory,
        root=tmp_path,
        inspector=StaticInspector(media_type="application/x-dosexec"),
        scanner=scanner,
    )

    with pytest.raises(DceUploadRejectedError):
        asyncio.run(
            service.upload(
                tenant_id=tenant_id,
                actor_id=uuid4(),
                actor_kind="PATRON_ADMIN",
                storage_object_id=storage_object_id,
                storage_key=storage_key,
                expected_byte_size=len(content),
                idempotency_key=uuid4(),
                stream=_stream(content),
                content_length=len(content),
            )
        )

    with session_factory() as session:
        staged_object = session.get(DceStagedObjectRecord, storage_object_id)
    assert staged_object is not None
    assert staged_object.state == "REJECTED"
    assert staged_object.rejection_code == "MEDIA_TYPE_NOT_ALLOWED"
    assert scanner.calls == 0
    assert not (tmp_path / storage_key).exists()


@pytest.mark.db
@pytest.mark.integration
def test_upload_fails_closed_when_clamav_returns_error(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    content = b"%PDF-1.7\nDCE de test\n"
    tenant_id, _, storage_object_id, storage_key = _seed_awaiting_staged_object(
        session_factory,
        expected_byte_size=len(content),
    )
    service = _service(
        session_factory=session_factory,
        root=tmp_path,
        inspector=StaticInspector(media_type="application/pdf"),
        scanner=StaticScanner(verdict="ERROR"),
    )

    with pytest.raises(DceUploadRejectedError):
        asyncio.run(
            service.upload(
                tenant_id=tenant_id,
                actor_id=uuid4(),
                actor_kind="PATRON_ADMIN",
                storage_object_id=storage_object_id,
                storage_key=storage_key,
                expected_byte_size=len(content),
                idempotency_key=uuid4(),
                stream=_stream(content),
                content_length=len(content),
            )
        )

    with session_factory() as session:
        staged_object = session.get(DceStagedObjectRecord, storage_object_id)
    assert staged_object is not None
    assert staged_object.state == "REJECTED"
    assert staged_object.rejection_code == "SCAN_ERROR"
    assert not (tmp_path / storage_key).exists()


@pytest.mark.db
@pytest.mark.integration
def test_uploaded_object_cannot_be_claimed_for_a_second_byte_stream(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    content = b"%PDF-1.7\nDCE de test\n"
    tenant_id, _, storage_object_id, storage_key = _seed_awaiting_staged_object(
        session_factory,
        expected_byte_size=len(content),
    )
    service = _service(
        session_factory=session_factory,
        root=tmp_path,
        inspector=StaticInspector(media_type="application/pdf"),
        scanner=StaticScanner(verdict="CLEAN"),
    )
    idempotency_key = uuid4()
    asyncio.run(
        service.upload(
            tenant_id=tenant_id,
            actor_id=uuid4(),
            actor_kind="PATRON_ADMIN",
            storage_object_id=storage_object_id,
            storage_key=storage_key,
            expected_byte_size=len(content),
            idempotency_key=idempotency_key,
            stream=_stream(content),
            content_length=len(content),
        )
    )

    with pytest.raises(DceUploadAlreadyClaimedError):
        asyncio.run(
            service.upload(
                tenant_id=tenant_id,
                actor_id=uuid4(),
                actor_kind="PATRON_ADMIN",
                storage_object_id=storage_object_id,
                storage_key=storage_key,
                expected_byte_size=len(content),
                idempotency_key=idempotency_key,
                stream=_stream(b"not accepted"),
                content_length=12,
            )
        )

    assert (tmp_path / storage_key).read_bytes() == content
