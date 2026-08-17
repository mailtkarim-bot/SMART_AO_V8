from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from app.modules.dce.application.analysis import (
    DceRcAnalysisService,
    _project_rc_requirements,
    _recording_command,
)
from app.modules.dce.application.extraction import DceDocumentExtractionService
from app.modules.dce.application.handlers import (
    RecordDceDocumentExtractionHandler,
    RecordDceRcAnalysisHandler,
)
from app.modules.dce.infrastructure.models.consultation import ConsultationRecord
from app.modules.dce.infrastructure.models.dce_extraction import DceDocumentExtractionFragmentRecord
from app.modules.dce.infrastructure.models.dce_rc_analysis import (
    DceRcAnalysisRunRecord,
    DceRcRequirementObservationRecord,
    DceRcRequirementSourceRecord,
)
from app.modules.dce.infrastructure.models.dce_staging import DceStagedObjectRecord
from app.modules.dce.infrastructure.models.dce_version import DceDocumentRecord, DceVersionRecord
from app.modules.dce.infrastructure.quarantine import LocalQuarantineStorageAdapter
from app.platform.events.dispatcher import CommandContext, CommandDispatcher, CommandExecutionError
from app.platform.persistence.models import DomainEventRecord, OutboxMessageRecord, TenantRecord
from sqlalchemy.orm import Session, sessionmaker

NOW = datetime(2026, 8, 14, 9, 0, tzinfo=UTC)






@pytest.fixture(autouse=True)
def isolate_rc_analysis_records(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


async def _stream(content: bytes):
    yield content


def _seed_admitted_document(
    session_factory: sessionmaker[Session],
    *,
    storage: LocalQuarantineStorageAdapter,
    source_bytes: bytes,
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
                external_reference="AO-2026-RC",
                object_label="Réhabilitation école",
                location_label="Lille",
                source_channel="MANUAL_UPLOAD",
                source_reference="Fixture RC analysis",
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
                provenance_reference="Fixture RC analysis",
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
                original_filename="reglement-consultation.txt",
                expected_byte_size=len(source_bytes),
                actual_byte_size=len(source_bytes),
                sha256=digest,
                media_type="text/plain",
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
                original_filename="reglement-consultation.txt",
                media_type="text/plain",
                byte_size=len(source_bytes),
                sha256=digest,
                received_from="MANUAL_UPLOAD",
            )
        )
    return tenant_id, document_id, dce_version_id


def _extraction_service(
    *,
    session_factory: sessionmaker[Session],
    storage: LocalQuarantineStorageAdapter,
) -> DceDocumentExtractionService:
    dispatcher = CommandDispatcher(
        session_factory=session_factory,
        handlers={"RecordDceDocumentExtraction": RecordDceDocumentExtractionHandler()},
    )
    return DceDocumentExtractionService(
        session_factory=session_factory,
        dispatcher=dispatcher,
        storage=storage,
    )


def _analysis_service(*, session_factory: sessionmaker[Session]) -> DceRcAnalysisService:
    dispatcher = CommandDispatcher(
        session_factory=session_factory,
        handlers={"RecordDceRcAnalysis": RecordDceRcAnalysisHandler()},
    )
    return DceRcAnalysisService(session_factory=session_factory, dispatcher=dispatcher)


def _extract_then_analyze(
    *,
    session_factory: sessionmaker[Session],
    storage: LocalQuarantineStorageAdapter,
    tenant_id: UUID,
    document_id: UUID,
    dce_version_id: UUID,
):
    asyncio.run(
        _extraction_service(session_factory=session_factory, storage=storage).extract(
            tenant_id=tenant_id,
            dce_document_id=document_id,
            now=NOW,
        )
    )
    return _analysis_service(session_factory=session_factory).analyze(
        tenant_id=tenant_id,
        dce_version_id=dce_version_id,
        now=NOW,
    )


@pytest.mark.db
@pytest.mark.integration
def test_rc_analysis_is_sourced_immutable_and_replayed_without_text_leak(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    source_text = (
        "Le dossier de candidature doit comporter le DC1 et le DC2.\n"
        "Le mémoire technique est obligatoire.\n"
        "La date limite de remise est fixée au 30 septembre 2026 à 12h00.\n"
        "Le dépôt électronique se fait sur le profil d'acheteur.\n"
        "Les critères d'attribution et leur pondération sont précisés ci-après.\n"
        "Une visite des lieux est facultative.\n"
    )
    storage = LocalQuarantineStorageAdapter(root=tmp_path)
    tenant_id, document_id, dce_version_id = _seed_admitted_document(
        session_factory,
        storage=storage,
        source_bytes=source_text.encode("utf-8"),
    )

    first = _extract_then_analyze(
        session_factory=session_factory,
        storage=storage,
        tenant_id=tenant_id,
        document_id=document_id,
        dce_version_id=dce_version_id,
    )
    replay = _analysis_service(session_factory=session_factory).analyze(
        tenant_id=tenant_id,
        dce_version_id=dce_version_id,
        now=NOW,
    )

    assert first.result_code == "DCE_RC_ANALYSIS_RECORDED"
    assert not first.replayed
    assert replay.replayed
    with session_factory() as session:
        run = session.scalar(sa.select(DceRcAnalysisRunRecord))
        observations = list(
            session.scalars(
                sa.select(DceRcRequirementObservationRecord).order_by(
                    DceRcRequirementObservationRecord.requirement_kind
                )
            )
        )
        source = session.scalar(sa.select(DceRcRequirementSourceRecord))
        events = list(
            session.scalars(
                sa.select(DomainEventRecord).where(
                    DomainEventRecord.event_type == "DCE_RC_ANALYSIS_RECORDED"
                )
            )
        )
        outbox = list(session.scalars(sa.select(OutboxMessageRecord)))
        fragment = session.get(DceDocumentExtractionFragmentRecord, source.fragment_id)
        source_observation = session.get(
            DceRcRequirementObservationRecord,
            source.observation_id,
        )
    assert run is not None
    assert run.status == "COMPLETED"
    assert len(observations) >= 6
    assert {observation.requirement_kind for observation in observations} >= {
        "RC_DOCUMENT_CANDIDATURE",
        "RC_CONTENT_OFFER",
        "RC_SUBMISSION_DEADLINE",
        "RC_RESPONSE_CHANNEL",
        "RC_AWARD_CRITERION",
        "RC_SITE_VISIT",
    }
    visit = next(
        observation
        for observation in observations
        if observation.requirement_kind == "RC_SITE_VISIT"
    )
    assert visit.directive == "OPTIONAL_SIGNAL"
    assert fragment is not None
    assert source is not None
    assert source_observation is not None
    sourced_excerpt = fragment.text.encode("utf-8")[
        source.start_byte_offset : source.end_byte_offset
    ].decode("utf-8")
    assert sourced_excerpt == source_observation.excerpt
    assert len(events) == 1
    assert events[0].payload_json["data"].keys() == {
        "analysis_id",
        "dce_version_id",
        "status",
        "source_fragment_count",
        "observation_count",
    }
    assert source_text not in str(outbox)
    assert "mémoire technique" not in str(outbox)

    with pytest.raises(sa.exc.DBAPIError), session_factory.begin() as session:
        immutable_run = session.get(DceRcAnalysisRunRecord, run.id)
        assert immutable_run is not None
        immutable_run.status = "FAILED_SAFE"


@pytest.mark.db
@pytest.mark.integration
def test_rc_analysis_records_no_marker_without_claiming_an_absence(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    storage = LocalQuarantineStorageAdapter(root=tmp_path)
    tenant_id, document_id, dce_version_id = _seed_admitted_document(
        session_factory,
        storage=storage,
        source_bytes=b"Bienvenue dans le dossier de travaux de la commune.\n",
    )

    result = _extract_then_analyze(
        session_factory=session_factory,
        storage=storage,
        tenant_id=tenant_id,
        document_id=document_id,
        dce_version_id=dce_version_id,
    )

    assert result.result_code == "DCE_RC_ANALYSIS_RECORDED"
    with session_factory() as session:
        run = session.scalar(sa.select(DceRcAnalysisRunRecord))
        observation_count = session.scalar(
            sa.select(sa.func.count()).select_from(DceRcRequirementObservationRecord)
        )
    assert run is not None
    assert run.status == "NO_RC_MARKER"
    assert run.failure_code == "NO_RC_MARKER"
    assert observation_count == 0


@pytest.mark.db
@pytest.mark.integration
def test_rc_analysis_rejects_a_non_system_actor_without_durable_effect(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    storage = LocalQuarantineStorageAdapter(root=tmp_path)
    tenant_id, document_id, dce_version_id = _seed_admitted_document(
        session_factory,
        storage=storage,
        source_bytes="Le mémoire technique est obligatoire.\n".encode(),
    )
    asyncio.run(
        _extraction_service(session_factory=session_factory, storage=storage).extract(
            tenant_id=tenant_id,
            dce_document_id=document_id,
            now=NOW,
        )
    )
    service = _analysis_service(session_factory=session_factory)
    sources = service._load_completed_fragments(  # noqa: SLF001 - system-bound service contract
        tenant_id=tenant_id,
        dce_version_id=dce_version_id,
    )
    command_to_reject = _recording_command(
        dce_version_id=dce_version_id,
        projection=_project_rc_requirements(sources=sources),
    )
    dispatcher = CommandDispatcher(
        session_factory=session_factory,
        handlers={"RecordDceRcAnalysis": RecordDceRcAnalysisHandler()},
    )

    with pytest.raises(CommandExecutionError) as failure:
        dispatcher.dispatch(
            command=command_to_reject,
            context=CommandContext(
                tenant_id=tenant_id,
                actor_id=uuid4(),
                actor_kind="USER",
                received_at=NOW,
            ),
        )
    assert str(failure.value.__cause__) == "DCE_ANALYSIS_SYSTEM_ACTOR_REQUIRED"
    with session_factory() as session:
        run_count = session.scalar(sa.select(sa.func.count()).select_from(DceRcAnalysisRunRecord))
    assert run_count == 0


@pytest.mark.db
@pytest.mark.integration
def test_rc_analysis_rejects_injected_fragment_source_without_partial_record(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    storage = LocalQuarantineStorageAdapter(root=tmp_path)
    tenant_id, document_id, dce_version_id = _seed_admitted_document(
        session_factory,
        storage=storage,
        source_bytes="Le mémoire technique est obligatoire.\n".encode(),
    )
    asyncio.run(
        _extraction_service(session_factory=session_factory, storage=storage).extract(
            tenant_id=tenant_id,
            dce_document_id=document_id,
            now=NOW,
        )
    )
    service = _analysis_service(session_factory=session_factory)
    sources = service._load_completed_fragments(  # noqa: SLF001 - system-bound service contract
        tenant_id=tenant_id,
        dce_version_id=dce_version_id,
    )
    valid_command = _recording_command(
        dce_version_id=dce_version_id,
        projection=_project_rc_requirements(sources=sources),
    )
    injected_command = valid_command.model_copy(
        update={"source_fragment_ids": [uuid4()]},
    )
    dispatcher = CommandDispatcher(
        session_factory=session_factory,
        handlers={"RecordDceRcAnalysis": RecordDceRcAnalysisHandler()},
    )

    with pytest.raises(CommandExecutionError) as failure:
        dispatcher.dispatch(
            command=injected_command,
            context=CommandContext(
                tenant_id=tenant_id,
                actor_id=uuid4(),
                actor_kind="SYSTEM",
                received_at=NOW,
            ),
        )
    assert str(failure.value.__cause__) == "DCE_ANALYSIS_SOURCE_FRAGMENT_REQUIRED"
    with session_factory() as session:
        run_count = session.scalar(sa.select(sa.func.count()).select_from(DceRcAnalysisRunRecord))
    assert run_count == 0


def test_rc_analysis_limit_is_terminal_and_contains_no_observation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.dce.application import analysis

    source = analysis.RcAnalysisSourceFragment(
        dce_document_id=uuid4(),
        extraction_id=uuid4(),
        fragment_id=uuid4(),
        ordinal=1,
        text="Le mémoire technique est obligatoire et la visite des lieux est obligatoire.",
        text_sha256="a" * 64,
    )
    monkeypatch.setattr(analysis, "MAX_OBSERVATIONS", 1)

    projection = analysis._project_rc_requirements(sources=(source,))

    assert projection.status == "REJECTED_LIMIT"
    assert projection.failure_code == "ANALYSIS_LIMIT"
    assert projection.source_fragments == (source,)
    assert projection.observations == ()
