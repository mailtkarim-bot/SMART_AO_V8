from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from app.modules.dce.application.commands import (
    ExpireDceStagedObjectCommand,
    PrepareDceStagingCommand,
    RecordDceStagedObjectScanCommand,
)
from app.modules.dce.application.handlers import (
    ExpireDceStagedObjectHandler,
    PrepareDceStagingHandler,
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

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPOSITORY_ROOT / "backend" / "alembic.ini"
DATABASE_URL = os.getenv(
    "SMART_AO_TEST_DATABASE_URL",
    "postgresql+psycopg://smart_ao:smart_ao@127.0.0.1:5432/smart_ao",
)
NOW = datetime(2026, 8, 13, 14, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def database_engine() -> sa.Engine:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
    command.upgrade(config, "head")
    engine = sa.create_engine(DATABASE_URL)
    try:
        yield engine
    finally:
        engine.dispose()
        command.downgrade(config, "base")


@pytest.fixture
def session_factory(database_engine: sa.Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=database_engine, expire_on_commit=False)


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
            "ExpireDceStagedObject": ExpireDceStagedObjectHandler(),
            "PrepareDceStaging": PrepareDceStagingHandler(),
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
