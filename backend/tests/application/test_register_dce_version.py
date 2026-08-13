from __future__ import annotations

import os
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from app.modules.dce.application.commands import RegisterDceVersionCommand
from app.modules.dce.application.handlers import RegisterDceVersionHandler
from app.modules.dce.infrastructure.models.consultation import ConsultationRecord
from app.modules.dce.infrastructure.models.dce_version import DceDocumentRecord, DceVersionRecord
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
NOW = datetime(2026, 8, 13, 13, 0, tzinfo=UTC)


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
def isolate_dce_admission_records(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


def _hash_manifest(*document_hashes: str) -> str:
    canonical_manifest = "\n".join(sorted(document_hashes))
    return sha256(canonical_manifest.encode("ascii")).hexdigest()


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
                functional_identity_hash="a" * 64,
                buyer_legal_name="Ville de test",
                buyer_normalized_id="VILLE-TEST",
                external_reference="AO-2026-ADMIT",
                object_label="Réhabilitation école",
                location_label="Lille",
                source_channel="MANUAL_UPLOAD",
                source_reference="Fixture",
                source_received_at=NOW,
                lifecycle="OPEN",
                freshness="CURRENT",
                metadata_history_json=[],
                created_by_actor_id=None,
                updated_by_actor_id=None,
            )
        )
    return tenant_id, consultation_id


def _command(*, consultation_id: UUID, consultation_revision: int = 4) -> RegisterDceVersionCommand:
    first_hash, second_hash = "b" * 64, "c" * 64
    return RegisterDceVersionCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        dce_version_id=uuid4(),
        consultation_id=consultation_id,
        consultation_revision=consultation_revision,
        corpus_hash=_hash_manifest(first_hash, second_hash),
        provenance_channel="MANUAL_UPLOAD",
        provenance_reference="Admission test",
        provenance_url=None,
        source_received_at=NOW,
        documents=[
            {
                "document_id": uuid4(),
                "storage_object_id": uuid4(),
                "storage_key": "staging/dce/second.pdf",
                "original_filename": "second.pdf",
                "media_type": "application/pdf",
                "byte_size": 200,
                "sha256": second_hash,
                "received_from": "MANUAL_UPLOAD",
            },
            {
                "document_id": uuid4(),
                "storage_object_id": uuid4(),
                "storage_key": "staging/dce/first.pdf",
                "original_filename": "first.pdf",
                "media_type": "application/pdf",
                "byte_size": 100,
                "sha256": first_hash,
                "received_from": "MANUAL_UPLOAD",
            },
        ],
    )


def _dispatcher(session_factory: sessionmaker[Session]) -> CommandDispatcher:
    return CommandDispatcher(
        session_factory=session_factory,
        handlers={"RegisterDceVersion": RegisterDceVersionHandler()},
    )


def _context(tenant_id: UUID) -> CommandContext:
    return CommandContext(
        tenant_id=str(tenant_id),
        actor_id=str(uuid4()),
        actor_kind="PATRON_ADMIN",
        received_at=NOW,
    )


@pytest.mark.db
@pytest.mark.integration
def test_register_dce_version_commits_root_documents_event_outbox_and_receipt_atomically(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, consultation_id = _seed_consultation(session_factory)
    command = _command(consultation_id=consultation_id)

    result = _dispatcher(session_factory).dispatch(command=command, context=_context(tenant_id))

    assert result.result_code == "DCE_VERSION_REGISTERED"
    with session_factory() as session:
        root = session.get(DceVersionRecord, command.dce_version_id)
        documents = list(
            session.scalars(
                sa.select(DceDocumentRecord).where(
                    DceDocumentRecord.tenant_id == tenant_id,
                    DceDocumentRecord.dce_version_id == command.dce_version_id,
                )
            )
        )
        events = list(session.scalars(sa.select(DomainEventRecord)))
        outbox = list(session.scalars(sa.select(OutboxMessageRecord)))
        receipts = list(session.scalars(sa.select(CommandReceiptRecord)))
    assert root is not None
    assert root.corpus_hash == command.corpus_hash
    assert root.aggregate_revision == 0
    assert len(documents) == 2
    assert {document.sha256 for document in documents} == {"b" * 64, "c" * 64}
    assert [event.event_type for event in events] == ["DCE_VERSION_REGISTERED"]
    assert len(outbox) == 1
    assert len(receipts) == 1


@pytest.mark.db
@pytest.mark.integration
def test_register_dce_version_replays_without_second_root_or_document(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, consultation_id = _seed_consultation(session_factory)
    command = _command(consultation_id=consultation_id)
    dispatcher = _dispatcher(session_factory)

    context = _context(tenant_id)
    first = dispatcher.dispatch(command=command, context=context)
    replay = dispatcher.dispatch(command=command, context=context)

    assert replay.replayed is True
    assert replay.event_ids == first.event_ids
    with session_factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(DceVersionRecord)) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(DceDocumentRecord)) == 2
        assert session.scalar(sa.select(sa.func.count()).select_from(DomainEventRecord)) == 1


@pytest.mark.db
@pytest.mark.integration
def test_register_dce_version_rejects_stale_consultation_without_side_effect(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, consultation_id = _seed_consultation(session_factory)
    command = _command(consultation_id=consultation_id, consultation_revision=3)

    with pytest.raises(CommandExecutionError):
        _dispatcher(session_factory).dispatch(command=command, context=_context(tenant_id))

    with session_factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(DceVersionRecord)) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(CommandReceiptRecord)) == 0


@pytest.mark.db
@pytest.mark.integration
def test_register_dce_version_rejects_noncanonical_corpus_hash_without_side_effect(
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, consultation_id = _seed_consultation(session_factory)
    command = _command(consultation_id=consultation_id).model_copy(update={"corpus_hash": "d" * 64})

    with pytest.raises(CommandExecutionError):
        _dispatcher(session_factory).dispatch(command=command, context=_context(tenant_id))

    with session_factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(DceVersionRecord)) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(DceDocumentRecord)) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(OutboxMessageRecord)) == 0
