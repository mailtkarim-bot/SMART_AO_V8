from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from app.modules.dce.application.classification import (
    ClassificationDocument,
    DceDocumentClassificationService,
    _recording_command,
    project_dce_classification,
)
from app.modules.dce.application.commands import RecordDceDocumentClassificationRunCommand
from app.modules.dce.application.handlers import (
    RecordDceDocumentClassificationRunHandler,
    _validate_classification_command,
)
from app.modules.dce.infrastructure.models.consultation import ConsultationRecord
from app.modules.dce.infrastructure.models.dce_classification import (
    DceDocumentClassificationEvidenceRecord,
    DceDocumentClassificationResultRecord,
    DceDocumentClassificationRunRecord,
)
from app.modules.dce.infrastructure.models.dce_extraction import (
    DceDocumentExtractionFragmentRecord,
    DceDocumentExtractionRecord,
)
from app.modules.dce.infrastructure.models.dce_staging import DceStagedObjectRecord
from app.modules.dce.infrastructure.models.dce_version import (
    DceDocumentClassificationRecord,
    DceDocumentRecord,
    DceVersionRecord,
)
from app.platform.events.dispatcher import CommandContext, CommandDispatcher, CommandExecutionError
from app.platform.persistence.models import DomainEventRecord, OutboxMessageRecord, TenantRecord
from sqlalchemy.orm import Session, sessionmaker

NOW = datetime(2026, 8, 14, 10, 0, tzinfo=UTC)






@pytest.fixture(autouse=True)
def isolate_classification_records(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


def _seed_dce(
    session_factory: sessionmaker[Session],
    *,
    document_texts: list[str | None],
) -> tuple[UUID, UUID, list[UUID]]:
    tenant_id, consultation_id, dce_version_id = uuid4(), uuid4(), uuid4()
    document_ids = [uuid4() for _ in document_texts]
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
                aggregate_revision=1,
                functional_identity_hash="a" * 64,
                buyer_legal_name="Ville de test",
                buyer_normalized_id="VILLE-TEST",
                external_reference="AO-2026-CLASSIFICATION",
                object_label="Réhabilitation école",
                location_label="Lille",
                source_channel="MANUAL_UPLOAD",
                source_reference="Fixture classification",
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
                provenance_reference="Fixture classification",
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
        for document_id, text in zip(document_ids, document_texts, strict=True):
            staged_object_id = uuid4()
            storage_key = f"private/{tenant_id}/{staged_object_id}"
            document_sha256 = sha256(str(document_id).encode()).hexdigest()
            session.add(
                DceStagedObjectRecord(
                    id=staged_object_id,
                    tenant_id=tenant_id,
                    consultation_id=consultation_id,
                    storage_key=storage_key,
                    original_filename="piece-dce.txt",
                    expected_byte_size=1,
                    actual_byte_size=1,
                    sha256=document_sha256,
                    media_type="text/plain",
                    source_channel="MANUAL_UPLOAD",
                    state="CONSUMED",
                    scan_verdict="CLEAN",
                    scanner_name="fixture",
                    scanner_signature_version="1",
                    scanned_at=NOW,
                    rejection_code=None,
                    expires_at=NOW + timedelta(days=1),
                    consumed_by_dce_version_id=dce_version_id,
                    consumed_at=NOW,
                    created_by_actor_id=None,
                    updated_by_actor_id=None,
                )
            )
            session.flush()
            session.add(
                DceDocumentRecord(
                    id=document_id,
                    tenant_id=tenant_id,
                    dce_version_id=dce_version_id,
                    storage_object_id=staged_object_id,
                    storage_key=storage_key,
                    original_filename="piece-dce.txt",
                    media_type="text/plain",
                    byte_size=1,
                    sha256=document_sha256,
                    received_from="MANUAL_UPLOAD",
                )
            )
            session.flush()
            if text is None:
                continue
            extraction_id, fragment_id = uuid4(), uuid4()
            session.add(
                DceDocumentExtractionRecord(
                    id=extraction_id,
                    tenant_id=tenant_id,
                    dce_version_id=dce_version_id,
                    dce_document_id=document_id,
                    input_sha256=sha256(text.encode()).hexdigest(),
                    extractor_id="fixture",
                    extractor_version="1",
                    status="COMPLETED",
                    fragment_count=1,
                    extracted_char_count=len(text),
                    failure_code=None,
                )
            )
            session.flush()
            session.add(
                DceDocumentExtractionFragmentRecord(
                    id=fragment_id,
                    tenant_id=tenant_id,
                    extraction_id=extraction_id,
                    ordinal=1,
                    locator_json={"kind": "text_line", "line": 1, "part": 1},
                    text=text,
                    text_sha256=sha256(text.encode()).hexdigest(),
                )
            )
    return tenant_id, dce_version_id, document_ids


def test_document_classification_limit_is_terminal_without_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.dce.application import classification

    monkeypatch.setattr(classification, "MAX_DOCUMENTS", 1)
    documents = (
        ClassificationDocument(dce_document_id=uuid4(), fragments=()),
        ClassificationDocument(dce_document_id=uuid4(), fragments=()),
    )

    projection = project_dce_classification(documents=documents)

    assert projection.status == "REJECTED_LIMIT"
    assert projection.failure_code == "CLASSIFICATION_LIMIT"
    assert projection.results == ()


def _service(*, session_factory: sessionmaker[Session]) -> DceDocumentClassificationService:
    dispatcher = CommandDispatcher(
        session_factory=session_factory,
        handlers={
            "RecordDceDocumentClassificationRun": RecordDceDocumentClassificationRunHandler()
        },
    )
    return DceDocumentClassificationService(
        session_factory=session_factory,
        dispatcher=dispatcher,
    )


@pytest.mark.db
@pytest.mark.integration
def test_dce_document_classification_is_sourced_immutable_and_replayed(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, dce_version_id, _ = _seed_dce(
        session_factory,
        document_texts=[
            "Règlement de la consultation\n",
            "Cahier des clauses techniques particulières\n",
        ],
    )
    service = _service(session_factory=session_factory)

    first = service.classify(tenant_id=tenant_id, dce_version_id=dce_version_id, now=NOW)
    replay = service.classify(tenant_id=tenant_id, dce_version_id=dce_version_id, now=NOW)

    assert first.result_code == "DCE_DOCUMENT_CLASSIFICATION_RECORDED"
    assert not first.replayed
    assert replay.replayed
    with session_factory() as session:
        root = session.get(DceVersionRecord, dce_version_id)
        runs = list(session.scalars(sa.select(DceDocumentClassificationRunRecord)))
        current = list(
            session.scalars(
                sa.select(DceDocumentClassificationRecord).where(
                    DceDocumentClassificationRecord.is_current.is_(True)
                )
            )
        )
        results = list(session.scalars(sa.select(DceDocumentClassificationResultRecord)))
        evidence = session.scalar(sa.select(DceDocumentClassificationEvidenceRecord))
        fragment = session.get(DceDocumentExtractionFragmentRecord, evidence.fragment_id)
        event = session.scalar(
            sa.select(DomainEventRecord).where(
                DomainEventRecord.event_type == "DCE_DOCUMENT_CLASSIFICATION_RECORDED"
            )
        )
        outbox = list(session.scalars(sa.select(OutboxMessageRecord)))
    assert root is not None
    assert root.classification_readiness == "CLASSIFIED"
    assert root.aggregate_revision == 2
    assert len(runs) == 1
    assert {item.classification for item in current} == {"RC", "CCTP"}
    assert {item.status for item in results} == {"CLASSIFIED"}
    assert evidence is not None
    assert fragment is not None
    assert (
        fragment.text.encode()[evidence.start_byte_offset : evidence.end_byte_offset].decode()
        == evidence.excerpt
    )
    assert event is not None
    assert event.payload_json["data"].keys() == {
        "classification_run_id",
        "dce_version_id",
        "classification_readiness",
        "document_count",
        "classified_document_count",
    }
    assert "Règlement de la consultation" not in str(outbox)

    with pytest.raises(sa.exc.DBAPIError), session_factory.begin() as session:
        run = session.get(DceDocumentClassificationRunRecord, runs[0].id)
        assert run is not None
        run.status = "FAILED_SAFE"


@pytest.mark.db
@pytest.mark.integration
def test_classification_is_safe_for_absence_of_signal_or_competing_families(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, dce_version_id, _ = _seed_dce(
        session_factory,
        document_texts=["CCAP CCTP", "Texte sans famille documentaire", None],
    )

    _service(session_factory=session_factory).classify(
        tenant_id=tenant_id,
        dce_version_id=dce_version_id,
        now=NOW,
    )

    with session_factory() as session:
        root = session.get(DceVersionRecord, dce_version_id)
        results = list(
            session.scalars(
                sa.select(DceDocumentClassificationResultRecord).order_by(
                    DceDocumentClassificationResultRecord.status
                )
            )
        )
        classifications = list(session.scalars(sa.select(DceDocumentClassificationRecord)))
    assert root is not None
    assert root.classification_readiness == "UNCLASSIFIED"
    assert [result.status for result in results] == [
        "NOT_EXTRACTED",
        "REVIEW_REQUIRED",
        "UNCLASSIFIED",
    ]
    assert classifications == []


@pytest.mark.db
@pytest.mark.integration
def test_classification_rejects_non_system_actor_without_durable_effect(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, dce_version_id, _ = _seed_dce(
        session_factory,
        document_texts=["Règlement de consultation"],
    )
    service = _service(session_factory=session_factory)
    expected_revision, documents = service._load_documents(  # noqa: SLF001
        tenant_id=tenant_id,
        dce_version_id=dce_version_id,
    )
    classification_command = _recording_command(
        dce_version_id=dce_version_id,
        expected_dce_version_revision=expected_revision,
        projection=project_dce_classification(documents=documents),
    )
    dispatcher = CommandDispatcher(
        session_factory=session_factory,
        handlers={
            "RecordDceDocumentClassificationRun": RecordDceDocumentClassificationRunHandler()
        },
    )

    with pytest.raises(CommandExecutionError) as failure:
        dispatcher.dispatch(
            command=classification_command,
            context=CommandContext(
                tenant_id=tenant_id,
                actor_id=uuid4(),
                actor_kind="USER",
                received_at=NOW,
            ),
        )
    assert str(failure.value.__cause__) == "DCE_CLASSIFICATION_SYSTEM_ACTOR_REQUIRED"
    with session_factory() as session:
        run_count = session.scalar(
            sa.select(sa.func.count()).select_from(DceDocumentClassificationRunRecord)
        )
    assert run_count == 0


@pytest.mark.db
@pytest.mark.integration
def test_classification_handler_rejects_document_manifest_count_stale_and_integrity_mismatch(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, dce_version_id, _ = _seed_dce(
        session_factory,
        document_texts=["Règlement de consultation"],
    )
    service = _service(session_factory=session_factory)
    expected_revision, documents = service._load_documents(  # noqa: SLF001
        tenant_id=tenant_id,
        dce_version_id=dce_version_id,
    )
    valid_command = _recording_command(
        dce_version_id=dce_version_id,
        expected_dce_version_revision=expected_revision,
        projection=project_dce_classification(documents=documents),
    )
    dispatcher = CommandDispatcher(
        session_factory=session_factory,
        handlers={
            "RecordDceDocumentClassificationRun": RecordDceDocumentClassificationRunHandler()
        },
    )

    with pytest.raises(CommandExecutionError) as document_count_failure:
        dispatcher.dispatch(
            command=valid_command.model_copy(
                update={
                    "command_id": uuid4(),
                    "idempotency_key": uuid4(),
                    "document_count": valid_command.document_count + 1,
                }
            ),
            context=CommandContext(
                tenant_id=tenant_id, actor_id=uuid4(), actor_kind="SYSTEM", received_at=NOW
            ),
        )
    assert str(document_count_failure.value.__cause__) == (
        "DCE_CLASSIFICATION_DOCUMENT_COUNT_REQUIRED"
    )

    with pytest.raises(CommandExecutionError) as manifest_failure:
        dispatcher.dispatch(
            command=valid_command.model_copy(
                update={
                    "command_id": uuid4(),
                    "idempotency_key": uuid4(),
                    "input_manifest_sha256": "f" * 64,
                }
            ),
            context=CommandContext(
                tenant_id=tenant_id, actor_id=uuid4(), actor_kind="SYSTEM", received_at=NOW
            ),
        )
    assert str(manifest_failure.value.__cause__) == "DCE_CLASSIFICATION_INPUT_MANIFEST_REQUIRED"

    with pytest.raises(CommandExecutionError) as source_count_failure:
        dispatcher.dispatch(
            command=valid_command.model_copy(
                update={
                    "command_id": uuid4(),
                    "idempotency_key": uuid4(),
                    "source_fragment_count": valid_command.source_fragment_count + 1,
                }
            ),
            context=CommandContext(
                tenant_id=tenant_id, actor_id=uuid4(), actor_kind="SYSTEM", received_at=NOW
            ),
        )
    assert str(source_count_failure.value.__cause__) == "DCE_CLASSIFICATION_SOURCE_COUNT_REQUIRED"

    with session_factory.begin() as session:
        version = session.get(DceVersionRecord, dce_version_id)
        assert version is not None
        version.aggregate_revision += 1
    with pytest.raises(CommandExecutionError) as stale_failure:
        dispatcher.dispatch(
            command=valid_command.model_copy(
                update={"command_id": uuid4(), "idempotency_key": uuid4()}
            ),
            context=CommandContext(
                tenant_id=tenant_id, actor_id=uuid4(), actor_kind="SYSTEM", received_at=NOW
            ),
        )
    assert str(stale_failure.value.__cause__) == "DCE_VERSION_STALE"

    with session_factory.begin() as session:
        version = session.get(DceVersionRecord, dce_version_id)
        assert version is not None
        version.integrity = "PARTIAL"
    with pytest.raises(CommandExecutionError) as integrity_failure:
        dispatcher.dispatch(
            command=valid_command.model_copy(
                update={"command_id": uuid4(), "idempotency_key": uuid4()}
            ),
            context=CommandContext(
                tenant_id=tenant_id, actor_id=uuid4(), actor_kind="SYSTEM", received_at=NOW
            ),
        )
    assert str(integrity_failure.value.__cause__) == "DCE_VERSION_NOT_CLASSIFIABLE"


@pytest.mark.db
@pytest.mark.integration
def test_classification_validator_rejects_invalid_projection_and_evidence(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, dce_version_id, _ = _seed_dce(
        session_factory, document_texts=["Règlement de consultation"]
    )
    service = _service(session_factory=session_factory)
    expected_revision, documents = service._load_documents(  # noqa: SLF001
        tenant_id=tenant_id, dce_version_id=dce_version_id
    )
    projection = project_dce_classification(documents=documents)
    command = _recording_command(
        dce_version_id=dce_version_id,
        expected_dce_version_revision=expected_revision,
        projection=projection,
    )
    with session_factory() as session:
        fragment = session.scalar(sa.select(DceDocumentExtractionFragmentRecord))
    assert fragment is not None
    fragment_records = {fragment.id: fragment}

    def validate(candidate, records=fragment_records) -> None:
        _validate_classification_command(
            command=candidate,
            expected_projection=projection,
            fragment_records=records,
        )

    with pytest.raises(ValueError, match="DCE_CLASSIFICATION_PROJECTION_REQUIRED"):
        validate(command.model_copy(update={"status": "FAILED_SAFE"}))
    with pytest.raises(ValueError, match="DCE_CLASSIFICATION_RESULT_REQUIRED"):
        validate(command.model_copy(update={"results": []}))

    evidence = command.results[0].evidence[0]
    with pytest.raises(ValueError, match="DCE_CLASSIFICATION_SOURCE_FRAGMENT_REQUIRED"):
        validate(
            command.model_copy(
                update={
                    "results": [
                        command.results[0].model_copy(
                            update={
                                "evidence": [
                                    evidence.model_copy(update={"fragment_id": uuid4()})
                                ]
                            }
                        )
                    ]
                }
            )
        )
    with pytest.raises(ValueError, match="DCE_CLASSIFICATION_EVIDENCE_REQUIRED"):
        validate(
            command.model_copy(
                update={
                    "results": [
                        command.results[0].model_copy(
                            update={
                                "evidence": [
                                    evidence.model_copy(update={"rule_id": "MISMATCH_V1"})
                                ]
                            }
                        )
                    ]
                }
            )
        )
    with pytest.raises(ValueError, match="DCE_CLASSIFICATION_SOURCE_OFFSET_REQUIRED"):
        validate(
            command,
            records={fragment.id: SimpleNamespace(id=fragment.id, text="x")},
        )
    with pytest.raises(ValueError, match="DCE_CLASSIFICATION_SOURCE_EXCERPT_REQUIRED"):
        validate(
            command,
            records={
                fragment.id: SimpleNamespace(
                    id=fragment.id, text="Z" * (evidence.end_byte_offset + 1)
                )
            },
        )


@pytest.mark.db
@pytest.mark.integration
def test_classification_handler_rejects_empty_document_set(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, dce_version_id, _ = _seed_dce(session_factory, document_texts=[])
    command = RecordDceDocumentClassificationRunCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        classification_run_id=uuid4(),
        dce_version_id=dce_version_id,
        expected_dce_version_revision=1,
        input_manifest_sha256="a" * 64,
        classifier_id="fixture",
        classifier_version="1",
        status="FAILED_SAFE",
        document_count=1,
        source_fragment_count=0,
        source_char_count=0,
        failure_code="TEST_FAILURE",
        results=[],
    )
    with pytest.raises(CommandExecutionError) as failure:
        CommandDispatcher(
            session_factory=session_factory,
            handlers={
                "RecordDceDocumentClassificationRun": RecordDceDocumentClassificationRunHandler()
            },
        ).dispatch(
            command=command,
            context=CommandContext(
                tenant_id=tenant_id, actor_id=uuid4(), actor_kind="SYSTEM", received_at=NOW
            ),
        )
    assert str(failure.value.__cause__) == "DCE_DOCUMENT_REQUIRED"


@pytest.mark.db
@pytest.mark.integration
def test_classification_handler_direct_replay_is_idempotent(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, dce_version_id, _ = _seed_dce(
        session_factory, document_texts=["Règlement de consultation"]
    )
    service = _service(session_factory=session_factory)
    expected_revision, documents = service._load_documents(  # noqa: SLF001
        tenant_id=tenant_id, dce_version_id=dce_version_id
    )
    command = _recording_command(
        dce_version_id=dce_version_id,
        expected_dce_version_revision=expected_revision,
        projection=project_dce_classification(documents=documents),
    )
    dispatcher = CommandDispatcher(
        session_factory=session_factory,
        handlers={
            "RecordDceDocumentClassificationRun": RecordDceDocumentClassificationRunHandler()
        },
    )
    first = dispatcher.dispatch(
        command=command,
        context=CommandContext(
            tenant_id=tenant_id, actor_id=uuid4(), actor_kind="SYSTEM", received_at=NOW
        ),
    )
    replay = dispatcher.dispatch(
        command=command.model_copy(
            update={"command_id": uuid4(), "idempotency_key": uuid4()}
        ),
        context=CommandContext(
            tenant_id=tenant_id, actor_id=uuid4(), actor_kind="SYSTEM", received_at=NOW
        ),
    )
    assert first.result_code == "DCE_DOCUMENT_CLASSIFICATION_RECORDED"
    assert replay.result_code == "DCE_DOCUMENT_CLASSIFICATION_ALREADY_RECORDED"


@pytest.mark.db
@pytest.mark.integration
def test_new_completed_extraction_creates_a_classification_history_successor(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, dce_version_id, document_ids = _seed_dce(
        session_factory,
        document_texts=["Cahier des clauses techniques particulières"],
    )
    service = _service(session_factory=session_factory)
    service.classify(tenant_id=tenant_id, dce_version_id=dce_version_id, now=NOW)
    document_id = document_ids[0]
    second_text = "Règlement de consultation Règlement de consultation"
    with session_factory.begin() as session:
        extraction_id, fragment_id = uuid4(), uuid4()
        session.add(
            DceDocumentExtractionRecord(
                id=extraction_id,
                tenant_id=tenant_id,
                dce_version_id=dce_version_id,
                dce_document_id=document_id,
                input_sha256=sha256(second_text.encode()).hexdigest(),
                extractor_id="fixture",
                extractor_version="2",
                status="COMPLETED",
                fragment_count=1,
                extracted_char_count=len(second_text),
                failure_code=None,
            )
        )
        session.flush()
        session.add(
            DceDocumentExtractionFragmentRecord(
                id=fragment_id,
                tenant_id=tenant_id,
                extraction_id=extraction_id,
                ordinal=1,
                locator_json={"kind": "text_line", "line": 2, "part": 1},
                text=second_text,
                text_sha256=sha256(second_text.encode()).hexdigest(),
            )
        )

    service.classify(tenant_id=tenant_id, dce_version_id=dce_version_id, now=NOW)
    third_text = "Règlement de consultation Règlement de consultation"
    with session_factory.begin() as session:
        extraction_id, fragment_id = uuid4(), uuid4()
        session.add(
            DceDocumentExtractionRecord(
                id=extraction_id,
                tenant_id=tenant_id,
                dce_version_id=dce_version_id,
                dce_document_id=document_id,
                input_sha256=sha256(third_text.encode()).hexdigest(),
                extractor_id="fixture",
                extractor_version="3",
                status="COMPLETED",
                fragment_count=1,
                extracted_char_count=len(third_text),
                failure_code=None,
            )
        )
        session.flush()
        session.add(
            DceDocumentExtractionFragmentRecord(
                id=fragment_id,
                tenant_id=tenant_id,
                extraction_id=extraction_id,
                ordinal=1,
                locator_json={"kind": "text_line", "line": 3, "part": 1},
                text=third_text,
                text_sha256=sha256(third_text.encode()).hexdigest(),
            )
        )
    service.classify(tenant_id=tenant_id, dce_version_id=dce_version_id, now=NOW)

    with session_factory() as session:
        history = list(
            session.scalars(
                sa.select(DceDocumentClassificationRecord).order_by(
                    DceDocumentClassificationRecord.created_at
                )
            )
        )
        current = session.scalar(
            sa.select(DceDocumentClassificationRecord).where(
                DceDocumentClassificationRecord.is_current.is_(True)
            )
        )
    assert [record.classification for record in history] == ["CCTP", "RC"]
    assert history[0].is_current is False
    assert history[1].previous_classification_id == history[0].id
    assert current is not None
    assert current.id == history[1].id
