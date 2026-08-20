from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from app.modules.dce.application.commands import (
    ClaimDceStagedObjectUploadCommand,
    ExpireDceStagedObjectCommand,
    PrepareDceStagingCommand,
    RecordDceStagedObjectQuarantineCommand,
    RecordDceStagedObjectScanCommand,
)
from app.modules.dce.application.handlers import (
    ClaimDceStagedObjectUploadHandler,
    ExpireDceStagedObjectHandler,
    PrepareDceStagingHandler,
    RecordDceStagedObjectQuarantineHandler,
    RecordDceStagedObjectScanHandler,
)
from app.modules.dce.infrastructure.models.consultation import ConsultationRecord
from app.modules.dce.infrastructure.models.dce_staging import DceStagedObjectRecord
from app.platform.events.dispatcher import CommandContext, CommandDispatcher, CommandExecutionError
from app.platform.persistence.models import (
    CommandReceiptRecord,
    DomainEventRecord,
    OutboxMessageRecord,
    TenantRecord,
)
from sqlalchemy.orm import Session, sessionmaker

NOW = datetime(2026, 8, 13, 14, 0, tzinfo=UTC)






@pytest.fixture(autouse=True)
def isolate_dce_staging_records(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


def _seed_consultation(session_factory: sessionmaker[Session]) -> tuple[UUID, UUID]:
    tenant_id, consultation_id = uuid4(), uuid4()
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
                functional_identity_hash="e" * 64,
                buyer_legal_name="Ville de test",
                buyer_normalized_id="VILLE-TEST",
                external_reference="AO-2026-STAGING",
                object_label="Réhabilitation école",
                location_label="Lille",
                source_channel="MANUAL_UPLOAD",
                source_reference="Fixture staging",
                source_received_at=NOW,
                lifecycle="OPEN",
                freshness="CURRENT",
                metadata_history_json=[],
                created_by_actor_id=None,
                updated_by_actor_id=None,
            )
        )
    return tenant_id, consultation_id


def _prepare_command(
    *,
    consultation_id: UUID,
    expires_at: datetime | None = None,
) -> PrepareDceStagingCommand:
    return PrepareDceStagingCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        storage_object_id=uuid4(),
        consultation_id=consultation_id,
        consultation_revision=4,
        original_filename="Reglement-consultation.pdf",
        expected_byte_size=100,
        source_channel="MANUAL_UPLOAD",
        expires_at=expires_at or NOW + timedelta(hours=1),
    )


def _claim_command(*, storage_object_id: UUID) -> ClaimDceStagedObjectUploadCommand:
    return ClaimDceStagedObjectUploadCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        storage_object_id=storage_object_id,
    )


def _quarantine_command(
    *,
    storage_object_id: UUID,
    actual_byte_size: int = 100,
    content_allowed: bool = True,
) -> RecordDceStagedObjectQuarantineCommand:
    return RecordDceStagedObjectQuarantineCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        storage_object_id=storage_object_id,
        actual_byte_size=actual_byte_size,
        sha256="b" * 64,
        media_type="application/pdf",
        content_allowed=content_allowed,
    )


def _expire_command(*, storage_object_id: UUID) -> ExpireDceStagedObjectCommand:
    return ExpireDceStagedObjectCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        storage_object_id=storage_object_id,
    )


def _scan_command(
    *,
    storage_object_id: UUID,
    verdict: str = "CLEAN",
) -> RecordDceStagedObjectScanCommand:
    return RecordDceStagedObjectScanCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        storage_object_id=storage_object_id,
        actual_byte_size=100,
        sha256="a" * 64,
        media_type="application/pdf",
        scan_verdict=verdict,
        scanner_name="clamav",
        scanner_signature_version="main-20260813",
        scanned_at=NOW,
    )


def _dispatcher(session_factory: sessionmaker[Session]) -> CommandDispatcher:
    return CommandDispatcher(
        session_factory=session_factory,
        handlers={
            "ClaimDceStagedObjectUpload": ClaimDceStagedObjectUploadHandler(),
            "ExpireDceStagedObject": ExpireDceStagedObjectHandler(),
            "PrepareDceStaging": PrepareDceStagingHandler(),
            "RecordDceStagedObjectQuarantine": RecordDceStagedObjectQuarantineHandler(),
            "RecordDceStagedObjectScan": RecordDceStagedObjectScanHandler(),
        },
    )


def _context(
    tenant_id: UUID,
    *,
    actor_kind: str = "PATRON_ADMIN",
    received_at: datetime = NOW,
) -> CommandContext:
    return CommandContext(
        tenant_id=str(tenant_id),
        actor_id=str(uuid4()),
        actor_kind=actor_kind,
        received_at=received_at,
    )


def _move_to_quarantine(session_factory: sessionmaker[Session], *, storage_object_id: UUID) -> None:
    with session_factory.begin() as session:
        staged_object = session.get(DceStagedObjectRecord, storage_object_id)
        assert staged_object is not None
        staged_object.state = "UPLOADING"
        session.flush()
        staged_object.state = "QUARANTINED"


@pytest.mark.db
@pytest.mark.integration
def test_prepare_dce_staging_creates_private_tenant_scoped_intent_and_durable_event(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, consultation_id = _seed_consultation(session_factory)
    command = _prepare_command(consultation_id=consultation_id)

    result = _dispatcher(session_factory).dispatch(command=command, context=_context(tenant_id))

    assert result.result_code == "DCE_STAGING_PREPARED"
    with session_factory() as session:
        staged_object = session.get(DceStagedObjectRecord, command.storage_object_id)
        events = list(session.scalars(sa.select(DomainEventRecord)))
        outbox = list(session.scalars(sa.select(OutboxMessageRecord)))
        receipts = list(session.scalars(sa.select(CommandReceiptRecord)))
    assert staged_object is not None
    assert staged_object.tenant_id == tenant_id
    assert staged_object.consultation_id == consultation_id
    assert staged_object.state == "AWAITING_UPLOAD"
    assert staged_object.storage_key == f"dce-staging/{tenant_id}/{command.storage_object_id}"
    assert [event.event_type for event in events] == ["DCE_STAGING_PREPARED"]
    assert len(outbox) == 1
    assert len(receipts) == 1


@pytest.mark.db
@pytest.mark.integration
def test_prepare_dce_staging_rejects_expired_intent_without_durable_side_effect(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, consultation_id = _seed_consultation(session_factory)
    command = _prepare_command(consultation_id=consultation_id, expires_at=NOW)

    with pytest.raises(CommandExecutionError):
        _dispatcher(session_factory).dispatch(command=command, context=_context(tenant_id))

    with session_factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(DceStagedObjectRecord)) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(CommandReceiptRecord)) == 0


@pytest.mark.db
@pytest.mark.integration
def test_claim_staged_object_rejects_expired_or_already_claimed_objects(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, consultation_id = _seed_consultation(session_factory)
    dispatcher = _dispatcher(session_factory)
    active = _prepare_command(consultation_id=consultation_id)
    dispatcher.dispatch(command=active, context=_context(tenant_id))

    claimed = dispatcher.dispatch(
        command=_claim_command(storage_object_id=active.storage_object_id),
        context=_context(tenant_id),
    )
    assert claimed.result_code == "DCE_STAGING_UPLOAD_CLAIMED"
    with pytest.raises(CommandExecutionError) as repeated:
        dispatcher.dispatch(
            command=_claim_command(storage_object_id=active.storage_object_id),
            context=_context(tenant_id),
        )
    assert str(repeated.value.__cause__) == "DCE_STAGED_OBJECT_NOT_AWAITING_UPLOAD"

    expired = _prepare_command(
        consultation_id=consultation_id,
        expires_at=NOW + timedelta(minutes=1),
    )
    dispatcher.dispatch(command=expired, context=_context(tenant_id))
    with pytest.raises(CommandExecutionError) as expired_failure:
        dispatcher.dispatch(
            command=_claim_command(storage_object_id=expired.storage_object_id),
            context=_context(tenant_id, received_at=NOW + timedelta(minutes=1)),
        )
    assert str(expired_failure.value.__cause__) == "DCE_STAGED_OBJECT_EXPIRED"


@pytest.mark.db
@pytest.mark.integration
def test_quarantine_rejects_size_or_media_and_requires_system_actor(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, consultation_id = _seed_consultation(session_factory)
    dispatcher = _dispatcher(session_factory)

    mismatch = _prepare_command(consultation_id=consultation_id)
    dispatcher.dispatch(command=mismatch, context=_context(tenant_id))
    dispatcher.dispatch(
        command=_claim_command(storage_object_id=mismatch.storage_object_id),
        context=_context(tenant_id),
    )
    with pytest.raises(CommandExecutionError) as actor_failure:
        dispatcher.dispatch(
            command=_quarantine_command(storage_object_id=mismatch.storage_object_id),
            context=_context(tenant_id),
        )
    assert str(actor_failure.value.__cause__) == "DCE_STAGING_SYSTEM_ACTOR_REQUIRED"
    mismatch_result = dispatcher.dispatch(
        command=_quarantine_command(
            storage_object_id=mismatch.storage_object_id, actual_byte_size=99
        ),
        context=_context(tenant_id, actor_kind="SYSTEM"),
    )
    assert mismatch_result.result_code == "DCE_STAGING_QUARANTINE_RECORDED"

    media = _prepare_command(consultation_id=consultation_id)
    dispatcher.dispatch(command=media, context=_context(tenant_id))
    dispatcher.dispatch(
        command=_claim_command(storage_object_id=media.storage_object_id),
        context=_context(tenant_id),
    )
    dispatcher.dispatch(
        command=_quarantine_command(
            storage_object_id=media.storage_object_id, content_allowed=False
        ),
        context=_context(tenant_id, actor_kind="SYSTEM"),
    )
    with session_factory() as session:
        mismatch_object = session.get(DceStagedObjectRecord, mismatch.storage_object_id)
        media_object = session.get(DceStagedObjectRecord, media.storage_object_id)
    assert mismatch_object is not None
    assert media_object is not None
    assert mismatch_object.rejection_code == "BYTE_SIZE_MISMATCH"
    assert media_object.rejection_code == "MEDIA_TYPE_NOT_ALLOWED"


@pytest.mark.db
@pytest.mark.integration
def test_expire_staged_object_rejects_future_and_already_expired_objects(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, consultation_id = _seed_consultation(session_factory)
    dispatcher = _dispatcher(session_factory)
    prepare = _prepare_command(consultation_id=consultation_id)
    dispatcher.dispatch(command=prepare, context=_context(tenant_id))

    with pytest.raises(CommandExecutionError) as future_failure:
        dispatcher.dispatch(
            command=_expire_command(storage_object_id=prepare.storage_object_id),
            context=_context(tenant_id, actor_kind="SYSTEM"),
        )
    assert str(future_failure.value.__cause__) == "DCE_STAGED_OBJECT_NOT_EXPIRED"
    dispatcher.dispatch(
        command=_expire_command(storage_object_id=prepare.storage_object_id),
        context=_context(tenant_id, actor_kind="SYSTEM", received_at=NOW + timedelta(hours=2)),
    )
    with pytest.raises(CommandExecutionError) as repeated_failure:
        dispatcher.dispatch(
            command=_expire_command(storage_object_id=prepare.storage_object_id),
            context=_context(tenant_id, actor_kind="SYSTEM", received_at=NOW + timedelta(hours=2)),
        )
    assert str(repeated_failure.value.__cause__) == "DCE_STAGED_OBJECT_NOT_EXPIRABLE"


@pytest.mark.db
@pytest.mark.integration
def test_scan_rejects_size_mismatch_and_infected_content(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, consultation_id = _seed_consultation(session_factory)
    dispatcher = _dispatcher(session_factory)
    mismatch = _prepare_command(consultation_id=consultation_id)
    dispatcher.dispatch(command=mismatch, context=_context(tenant_id))
    _move_to_quarantine(session_factory, storage_object_id=mismatch.storage_object_id)
    dispatcher.dispatch(
        command=_scan_command(storage_object_id=mismatch.storage_object_id).model_copy(
            update={"actual_byte_size": 99}
        ),
        context=_context(tenant_id, actor_kind="SYSTEM"),
    )

    infected = _prepare_command(consultation_id=consultation_id)
    dispatcher.dispatch(command=infected, context=_context(tenant_id))
    _move_to_quarantine(session_factory, storage_object_id=infected.storage_object_id)
    dispatcher.dispatch(
        command=_scan_command(storage_object_id=infected.storage_object_id, verdict="INFECTED"),
        context=_context(tenant_id, actor_kind="SYSTEM"),
    )
    with session_factory() as session:
        mismatch_object = session.get(DceStagedObjectRecord, mismatch.storage_object_id)
        infected_object = session.get(DceStagedObjectRecord, infected.storage_object_id)
    assert mismatch_object is not None
    assert infected_object is not None
    assert mismatch_object.rejection_code == "BYTE_SIZE_MISMATCH"
    assert infected_object.rejection_code == "MALWARE_DETECTED"


@pytest.mark.db
@pytest.mark.integration
def test_record_clean_scan_requires_system_actor_and_transitions_quarantine_to_clean(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, consultation_id = _seed_consultation(session_factory)
    prepare = _prepare_command(consultation_id=consultation_id)
    dispatcher = _dispatcher(session_factory)
    dispatcher.dispatch(command=prepare, context=_context(tenant_id))
    _move_to_quarantine(session_factory, storage_object_id=prepare.storage_object_id)

    with pytest.raises(CommandExecutionError):
        dispatcher.dispatch(
            command=_scan_command(storage_object_id=prepare.storage_object_id),
            context=_context(tenant_id),
        )

    result = dispatcher.dispatch(
        command=_scan_command(storage_object_id=prepare.storage_object_id),
        context=_context(tenant_id, actor_kind="SYSTEM"),
    )

    assert result.result_code == "DCE_STAGING_SCAN_RECORDED"
    with session_factory() as session:
        staged_object = session.get(DceStagedObjectRecord, prepare.storage_object_id)
    assert staged_object is not None
    assert staged_object.state == "CLEAN"
    assert staged_object.sha256 == "a" * 64
    assert staged_object.scan_verdict == "CLEAN"
    assert staged_object.consumed_by_dce_version_id is None


@pytest.mark.db
@pytest.mark.integration
def test_scan_error_is_fail_closed_and_marks_staged_object_rejected(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, consultation_id = _seed_consultation(session_factory)
    prepare = _prepare_command(consultation_id=consultation_id)
    dispatcher = _dispatcher(session_factory)
    dispatcher.dispatch(command=prepare, context=_context(tenant_id))
    _move_to_quarantine(session_factory, storage_object_id=prepare.storage_object_id)

    dispatcher.dispatch(
        command=_scan_command(storage_object_id=prepare.storage_object_id, verdict="ERROR"),
        context=_context(tenant_id, actor_kind="SYSTEM"),
    )

    with session_factory() as session:
        staged_object = session.get(DceStagedObjectRecord, prepare.storage_object_id)
    assert staged_object is not None
    assert staged_object.state == "REJECTED"
    assert staged_object.rejection_code == "SCAN_ERROR"
    assert staged_object.scan_verdict == "ERROR"


@pytest.mark.db
@pytest.mark.integration
def test_expire_staged_object_requires_system_and_emits_retention_outbox(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, consultation_id = _seed_consultation(session_factory)
    prepare = _prepare_command(consultation_id=consultation_id)
    dispatcher = _dispatcher(session_factory)
    dispatcher.dispatch(command=prepare, context=_context(tenant_id))

    with pytest.raises(CommandExecutionError):
        dispatcher.dispatch(
            command=_expire_command(storage_object_id=prepare.storage_object_id),
            context=_context(tenant_id, received_at=NOW + timedelta(hours=2)),
        )

    result = dispatcher.dispatch(
        command=_expire_command(storage_object_id=prepare.storage_object_id),
        context=_context(
            tenant_id,
            actor_kind="SYSTEM",
            received_at=NOW + timedelta(hours=2),
        ),
    )

    assert result.result_code == "DCE_STAGING_EXPIRED"
    with session_factory() as session:
        staged_object = session.get(DceStagedObjectRecord, prepare.storage_object_id)
        outbox = list(session.scalars(sa.select(OutboxMessageRecord)))
    assert staged_object is not None
    assert staged_object.state == "EXPIRED"
    assert [message.topic for message in outbox] == [
        "cockpit_projection",
        "dce_staging_retention",
    ]


@pytest.mark.db
@pytest.mark.integration
def test_staged_object_database_trigger_rejects_invalid_state_transition(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, consultation_id = _seed_consultation(session_factory)
    prepare = _prepare_command(consultation_id=consultation_id)
    _dispatcher(session_factory).dispatch(command=prepare, context=_context(tenant_id))

    with pytest.raises(sa.exc.DBAPIError), session_factory.begin() as session:
        staged_object = session.get(DceStagedObjectRecord, prepare.storage_object_id)
        assert staged_object is not None
        staged_object.state = "CLEAN"
