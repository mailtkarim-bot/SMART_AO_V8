from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from app.modules.dce.application.commands import RecordDceDocumentExtractionCommand
from app.modules.dce.application.extraction import (
    DceDocumentExtractionService,
    _project_document,
)
from app.modules.dce.application.handlers import RecordDceDocumentExtractionHandler
from app.modules.dce.infrastructure.models.consultation import ConsultationRecord
from app.modules.dce.infrastructure.models.dce_extraction import (
    DceDocumentExtractionFragmentRecord,
    DceDocumentExtractionRecord,
)
from app.modules.dce.infrastructure.models.dce_staging import DceStagedObjectRecord
from app.modules.dce.infrastructure.models.dce_version import DceDocumentRecord, DceVersionRecord
from app.modules.dce.infrastructure.quarantine import LocalQuarantineStorageAdapter
from app.platform.events.dispatcher import (
    CommandContext,
    CommandDispatcher,
    CommandExecutionError,
)
from app.platform.persistence.models import DomainEventRecord, OutboxMessageRecord, TenantRecord
from docx import Document
from openpyxl import Workbook
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy.orm import Session, sessionmaker

NOW = datetime(2026, 8, 13, 18, 0, tzinfo=UTC)






@pytest.fixture(autouse=True)
def isolate_extraction_records(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


async def _stream(content: bytes):
    yield content


def _seed_admitted_document(
    session_factory: sessionmaker[Session],
    *,
    storage: LocalQuarantineStorageAdapter,
    source_bytes: bytes,
    media_type: str,
) -> tuple[UUID, UUID, UUID]:
    tenant_id, consultation_id, dce_version_id, document_id, staged_object_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    storage_key = f"dce-staging/{tenant_id}/{staged_object_id}"
    digest = sha256(source_bytes).hexdigest()
    asyncio.run(
        storage.write(
            storage_key=storage_key,
            stream=_stream(source_bytes),
            max_bytes=128 * 1024 * 1024,
        )
    )
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
                functional_identity_hash="a" * 64,
                buyer_legal_name="Ville de test",
                buyer_normalized_id="VILLE-TEST",
                external_reference="AO-2026-EXTRACTION",
                object_label="Réhabilitation école",
                location_label="Lille",
                source_channel="MANUAL_UPLOAD",
                source_reference="Fixture extraction",
                source_received_at=NOW,
                lifecycle="OPEN",
                freshness="CURRENT",
                metadata_history_json=[],
                created_by_actor_id=None,
                updated_by_actor_id=None,
            )
        )
        session.add(
            DceVersionRecord(
                id=dce_version_id,
                tenant_id=tenant_id,
                aggregate_revision=1,
                consultation_id=consultation_id,
                corpus_hash="b" * 64,
                predecessor_dce_version_id=None,
                provenance_channel="MANUAL_UPLOAD",
                provenance_reference="Fixture extraction",
                provenance_url=None,
                source_received_at=NOW,
                lifecycle="ADMITTED",
                integrity="VERIFIED",
                classification_readiness="UNCLASSIFIED",
                analysis_readiness="NOT_READY",
                withdrawal_source=None,
                withdrawal_reason=None,
                superseded_at=None,
                withdrawn_at=None,
                created_by_actor_id=None,
                updated_by_actor_id=None,
            )
        )
        session.flush()
        session.add(
            DceStagedObjectRecord(
                id=staged_object_id,
                tenant_id=tenant_id,
                consultation_id=consultation_id,
                storage_key=storage_key,
                original_filename="reglement-consultation",
                expected_byte_size=len(source_bytes),
                actual_byte_size=len(source_bytes),
                sha256=digest,
                media_type=media_type,
                source_channel="MANUAL_UPLOAD",
                state="CONSUMED",
                scan_verdict="CLEAN",
                scanner_name="test-clamd",
                scanner_signature_version="test-signatures",
                scanned_at=NOW,
                rejection_code=None,
                expires_at=NOW + timedelta(days=1),
                consumed_by_dce_version_id=dce_version_id,
                consumed_at=NOW,
                created_by_actor_id=None,
                updated_by_actor_id=None,
            )
        )
        session.add(
            DceDocumentRecord(
                id=document_id,
                tenant_id=tenant_id,
                dce_version_id=dce_version_id,
                storage_object_id=staged_object_id,
                storage_key=storage_key,
                original_filename="reglement-consultation",
                media_type=media_type,
                byte_size=len(source_bytes),
                sha256=digest,
                received_from="MANUAL_UPLOAD",
            )
        )
    return tenant_id, document_id, dce_version_id


def _handler_dispatcher(session_factory: sessionmaker[Session]) -> CommandDispatcher:
    return CommandDispatcher(
        session_factory=session_factory,
        handlers={"RecordDceDocumentExtraction": RecordDceDocumentExtractionHandler()},
    )


def _service(
    *,
    session_factory: sessionmaker[Session],
    storage: LocalQuarantineStorageAdapter,
) -> DceDocumentExtractionService:
    return DceDocumentExtractionService(
        session_factory=session_factory,
        dispatcher=_handler_dispatcher(session_factory),
        storage=storage,
    )


def _failed_extraction_command(
    *,
    document_id: UUID,
    input_sha256: str,
) -> RecordDceDocumentExtractionCommand:
    return RecordDceDocumentExtractionCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        extraction_id=uuid4(),
        dce_document_id=document_id,
        input_sha256=input_sha256,
        extractor_id="fixture",
        extractor_version="1",
        status="FAILED_SAFE",
        extracted_char_count=0,
        failure_code="TEST_FAILURE",
        fragments=[],
    )


@pytest.mark.db
@pytest.mark.integration
def test_extraction_handler_rejects_missing_storage_and_input_hash_mismatch(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    storage = LocalQuarantineStorageAdapter(root=tmp_path)
    tenant_id, document_id, dce_version_id = _seed_admitted_document(
        session_factory,
        storage=storage,
        source_bytes=b"source document",
        media_type="text/plain",
    )
    dispatcher = _handler_dispatcher(session_factory)

    with pytest.raises(CommandExecutionError) as missing_failure:
        dispatcher.dispatch(
            command=_failed_extraction_command(document_id=uuid4(), input_sha256="a" * 64),
            context=CommandContext(
                tenant_id=tenant_id, actor_id=uuid4(), actor_kind="SYSTEM", received_at=NOW
            ),
        )
    assert str(missing_failure.value.__cause__) == "DCE_DOCUMENT_REQUIRED"

    alternate_storage_object_id = uuid4()
    alternate_document_id = uuid4()
    alternate_storage_key = f"private/{tenant_id}/{alternate_storage_object_id}"
    alternate_hash = "c" * 64
    with session_factory.begin() as session:
        session.add(
            DceStagedObjectRecord(
                id=alternate_storage_object_id,
                tenant_id=tenant_id,
                consultation_id=session.get(DceVersionRecord, dce_version_id).consultation_id,
                storage_key=alternate_storage_key,
                original_filename="alternate.txt",
                expected_byte_size=15,
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
        session.add(
            DceDocumentRecord(
                id=alternate_document_id,
                tenant_id=tenant_id,
                dce_version_id=dce_version_id,
                storage_object_id=alternate_storage_object_id,
                storage_key=alternate_storage_key,
                original_filename="alternate.txt",
                media_type="text/plain",
                byte_size=15,
                sha256=alternate_hash,
                received_from="MANUAL_UPLOAD",
            )
        )
    with pytest.raises(CommandExecutionError) as storage_failure:
        dispatcher.dispatch(
            command=_failed_extraction_command(
                document_id=alternate_document_id, input_sha256=alternate_hash
            ),
            context=CommandContext(
                tenant_id=tenant_id, actor_id=uuid4(), actor_kind="SYSTEM", received_at=NOW
            ),
        )
    assert str(storage_failure.value.__cause__) == "DOCUMENT_STORAGE_NOT_CONSUMED"


@pytest.mark.db
@pytest.mark.integration
def test_extraction_handler_rejects_input_hash_mismatch(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    storage = LocalQuarantineStorageAdapter(root=tmp_path)
    tenant_id, document_id, _ = _seed_admitted_document(
        session_factory,
        storage=storage,
        source_bytes=b"source document",
        media_type="text/plain",
    )
    with pytest.raises(CommandExecutionError) as hash_failure:
        _handler_dispatcher(session_factory).dispatch(
            command=_failed_extraction_command(document_id=document_id, input_sha256="f" * 64),
            context=CommandContext(
                tenant_id=tenant_id, actor_id=uuid4(), actor_kind="SYSTEM", received_at=NOW
            ),
        )
    assert str(hash_failure.value.__cause__) == "DOCUMENT_INPUT_HASH_REQUIRED"


@pytest.mark.db
@pytest.mark.integration
def test_extraction_handler_rejects_non_admitted_and_unverified_versions(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    storage = LocalQuarantineStorageAdapter(root=tmp_path)
    tenant_id, document_id, dce_version_id = _seed_admitted_document(
        session_factory,
        storage=storage,
        source_bytes=b"source document",
        media_type="text/plain",
    )
    command = _failed_extraction_command(
        document_id=document_id, input_sha256=sha256(b"source document").hexdigest()
    )
    dispatcher = _handler_dispatcher(session_factory)
    with session_factory.begin() as session:
        version = session.get(DceVersionRecord, dce_version_id)
        assert version is not None
        version.lifecycle = "WITHDRAWN"
        version.withdrawal_source = "TEST"
        version.withdrawal_reason = "Fixture de test"
        version.withdrawn_at = NOW
    with pytest.raises(CommandExecutionError) as lifecycle_failure:
        dispatcher.dispatch(
            command=command,
            context=CommandContext(
                tenant_id=tenant_id, actor_id=uuid4(), actor_kind="SYSTEM", received_at=NOW
            ),
        )
    assert str(lifecycle_failure.value.__cause__) == "DCE_VERSION_NOT_ADMITTED"

    with session_factory.begin() as session:
        version = session.get(DceVersionRecord, dce_version_id)
        assert version is not None
        version.lifecycle = "ADMITTED"
        version.withdrawal_source = None
        version.withdrawal_reason = None
        version.withdrawn_at = None
        version.integrity = "PARTIAL"
    with pytest.raises(CommandExecutionError) as integrity_failure:
        dispatcher.dispatch(
            command=command.model_copy(update={"command_id": uuid4(), "idempotency_key": uuid4()}),
            context=CommandContext(
                tenant_id=tenant_id, actor_id=uuid4(), actor_kind="SYSTEM", received_at=NOW
            ),
        )
    assert str(integrity_failure.value.__cause__) == "DCE_VERSION_NOT_VERIFIED"


@pytest.mark.db
@pytest.mark.integration
def test_text_extraction_is_sourced_immutable_and_replayed_without_outbox_leak(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    storage = LocalQuarantineStorageAdapter(root=tmp_path)
    tenant_id, document_id, _ = _seed_admitted_document(
        session_factory,
        storage=storage,
        source_bytes=b"Premiere condition\nSeconde condition\n",
        media_type="text/plain",
    )
    service = _service(session_factory=session_factory, storage=storage)

    first = asyncio.run(service.extract(tenant_id=tenant_id, dce_document_id=document_id, now=NOW))
    replay = asyncio.run(service.extract(tenant_id=tenant_id, dce_document_id=document_id, now=NOW))

    assert first.result_code == "DCE_DOCUMENT_EXTRACTION_RECORDED"
    assert not first.replayed
    assert replay.replayed
    with session_factory() as session:
        extractions = list(session.scalars(sa.select(DceDocumentExtractionRecord)))
        fragments = list(
            session.scalars(
                sa.select(DceDocumentExtractionFragmentRecord).order_by(
                    DceDocumentExtractionFragmentRecord.ordinal
                )
            )
        )
        events = list(session.scalars(sa.select(DomainEventRecord)))
        outbox = list(session.scalars(sa.select(OutboxMessageRecord)))
    assert len(extractions) == 1
    assert extractions[0].status == "COMPLETED"
    assert [(fragment.ordinal, fragment.locator_json["kind"]) for fragment in fragments] == [
        (1, "text_line"),
        (2, "text_line"),
    ]
    assert [fragment.text for fragment in fragments] == ["Premiere condition", "Seconde condition"]
    assert events[0].payload_json["data"].keys() == {
        "extraction_id",
        "dce_document_id",
        "status",
        "fragment_count",
        "extracted_char_count",
    }
    assert "Premiere" not in str(outbox[0].payload_json)
    assert "dce-staging/" not in str(outbox[0].payload_json)

    with pytest.raises(sa.exc.DBAPIError), session_factory.begin() as session:
        extraction = session.get(DceDocumentExtractionRecord, extractions[0].id)
        assert extraction is not None
        extraction.status = "FAILED_SAFE"


@pytest.mark.db
@pytest.mark.integration
def test_unsupported_media_is_recorded_without_fragments(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    storage = LocalQuarantineStorageAdapter(root=tmp_path)
    tenant_id, document_id, _ = _seed_admitted_document(
        session_factory,
        storage=storage,
        source_bytes=b"\x89PNG\r\n\x1a\n",
        media_type="image/png",
    )

    asyncio.run(
        _service(session_factory=session_factory, storage=storage).extract(
            tenant_id=tenant_id,
            dce_document_id=document_id,
            now=NOW,
        )
    )

    with session_factory() as session:
        extraction = session.scalar(sa.select(DceDocumentExtractionRecord))
        fragment_count = session.scalar(
            sa.select(sa.func.count()).select_from(DceDocumentExtractionFragmentRecord)
        )
    assert extraction is not None
    assert extraction.status == "UNSUPPORTED"
    assert extraction.failure_code == "MEDIA_TYPE_UNSUPPORTED"
    assert fragment_count == 0


def test_docx_and_xlsx_projection_preserve_paragraph_and_cell_provenance() -> None:
    docx_buffer = BytesIO()
    document = Document()
    document.add_paragraph("Organisation du chantier")
    document.save(docx_buffer)
    docx_projection = _project_document(
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        source_bytes=docx_buffer.getvalue(),
    )

    xlsx_buffer = BytesIO()
    workbook = Workbook()
    workbook.active.title = "DPGF"
    workbook.active["B2"] = "Montant forfaitaire"
    workbook.save(xlsx_buffer)
    xlsx_projection = _project_document(
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        source_bytes=xlsx_buffer.getvalue(),
    )

    assert docx_projection.status == "COMPLETED"
    assert docx_projection.fragments[0].locator_json["kind"] == "docx_paragraph"
    assert xlsx_projection.status == "COMPLETED"
    assert xlsx_projection.fragments[0].locator_json == {
        "kind": "xlsx_cell",
        "sheet": "DPGF",
        "cell": "B2",
        "part": 1,
    }


def test_pdf_projection_preserves_page_provenance() -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 72 720 Td (Reglement de consultation) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(content)
    pdf_buffer = BytesIO()
    writer.write(pdf_buffer)

    projection = _project_document(
        media_type="application/pdf",
        source_bytes=pdf_buffer.getvalue(),
    )

    assert projection.status == "COMPLETED"
    assert projection.fragments[0].locator_json == {"kind": "pdf_page", "page": 1, "part": 1}
    assert projection.fragments[0].text == "Reglement de consultation"


def test_pdf_and_text_limits_fail_safe_without_fragments(monkeypatch: pytest.MonkeyPatch) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    pdf_buffer = BytesIO()
    writer.write(pdf_buffer)
    pdf_projection = _project_document(
        media_type="application/pdf",
        source_bytes=pdf_buffer.getvalue(),
    )
    assert pdf_projection.status == "FAILED_SAFE"
    assert pdf_projection.fragments == ()

    monkeypatch.setattr("app.modules.dce.application.extraction.MAX_TEXT_LINES", 1)
    text_projection = _project_document(
        media_type="text/plain",
        source_bytes=b"ligne 1\nligne 2\n",
    )
    assert text_projection.status == "REJECTED_LIMIT"
    assert text_projection.fragments == ()
