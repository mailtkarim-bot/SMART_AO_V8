from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from app.modules.dce.application.commands import CreateConsultationCommand
from app.modules.dce.application.handlers import CreateConsultationHandler
from app.platform.events.dispatcher import (
    CommandContext,
    CommandDispatcher,
    CommandExecutionError,
    IdempotencyKeyReusedError,
)
from app.platform.persistence.models import (
    CommandReceiptRecord,
    DomainEventRecord,
    OutboxMessageRecord,
)
from sqlalchemy.orm import Session, sessionmaker

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPOSITORY_ROOT / "backend" / "alembic.ini"
DATABASE_URL = os.getenv(
    "SMART_AO_TEST_DATABASE_URL",
    "postgresql+psycopg://smart_ao:smart_ao@127.0.0.1:5432/smart_ao",
)


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


def _insert_tenant(engine: sa.Engine) -> str:
    tenant_id = str(uuid4())
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO tenants (id, slug, lifecycle) VALUES (:id, :slug, 'ACTIVE')"
            ),
            {"id": tenant_id, "slug": f"tenant-{tenant_id}"},
        )
    return tenant_id


def _command(
    *,
    command_id: str | None = None,
    idempotency_key: str | None = None,
) -> CreateConsultationCommand:
    return CreateConsultationCommand(
        command_id=command_id or str(uuid4()),
        idempotency_key=idempotency_key or str(uuid4()),
        correlation_id=str(uuid4()),
        consultation_id=str(uuid4()),
        buyer_legal_name="Ville de test",
        buyer_normalized_id="VILLE-TEST",
        external_reference="AO-2026-001",
        object_label="Réhabilitation école",
        location_label="Lille",
        source_channel="MANUAL_UPLOAD",
        source_reference="Import pilote",
        source_received_at=datetime(2026, 8, 13, 10, 0, tzinfo=UTC),
    )


def _context(tenant_id: str) -> CommandContext:
    return CommandContext(
        tenant_id=tenant_id,
        actor_id=str(uuid4()),
        actor_kind="PATRON",
        received_at=datetime(2026, 8, 13, 10, 1, tzinfo=UTC),
    )


@pytest.mark.db
def test_dispatcher_commits_consultation_event_outbox_and_receipt_together(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id = _insert_tenant(database_engine)
    dispatcher = CommandDispatcher(
        session_factory=session_factory,
        handlers={"CreateConsultation": CreateConsultationHandler()},
    )
    result = dispatcher.dispatch(command=_command(), context=_context(tenant_id))

    assert result.status == "SUCCEEDED"
    assert result.replayed is False
    assert result.result_code == "CONSULTATION_CREATED"
    assert len(result.event_ids) == 1

    with Session(database_engine) as session:
        assert session.query(CommandReceiptRecord).filter_by(tenant_id=tenant_id).count() == 1
        assert session.query(DomainEventRecord).filter_by(tenant_id=tenant_id).count() == 1
        assert session.query(OutboxMessageRecord).filter_by(tenant_id=tenant_id).count() == 1
        assert session.execute(
            sa.text("SELECT count(*) FROM consultations WHERE tenant_id = :tenant_id"),
            {"tenant_id": tenant_id},
        ).scalar_one() == 1


@pytest.mark.db
def test_dispatcher_replays_success_without_second_mutation(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id = _insert_tenant(database_engine)
    context = _context(tenant_id)
    initial_command = _command()
    dispatcher = CommandDispatcher(
        session_factory=session_factory,
        handlers={"CreateConsultation": CreateConsultationHandler()},
    )

    first = dispatcher.dispatch(command=initial_command, context=context)
    replay = dispatcher.dispatch(command=initial_command, context=context)

    assert first.replayed is False
    assert replay.replayed is True
    assert replay.event_ids == first.event_ids
    with Session(database_engine) as session:
        assert session.query(CommandReceiptRecord).filter_by(tenant_id=tenant_id).count() == 1
        assert session.query(DomainEventRecord).filter_by(tenant_id=tenant_id).count() == 1
        assert session.query(OutboxMessageRecord).filter_by(tenant_id=tenant_id).count() == 1
        assert session.execute(
            sa.text("SELECT count(*) FROM consultations WHERE tenant_id = :tenant_id"),
            {"tenant_id": tenant_id},
        ).scalar_one() == 1


@pytest.mark.db
def test_dispatcher_rejects_reused_key_when_request_hash_differs(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id = _insert_tenant(database_engine)
    context = _context(tenant_id)
    initial_command = _command()
    dispatcher = CommandDispatcher(
        session_factory=session_factory,
        handlers={"CreateConsultation": CreateConsultationHandler()},
    )
    dispatcher.dispatch(command=initial_command, context=context)
    conflicting_command = CreateConsultationCommand(
        **{
            **initial_command.__dict__,
            "object_label": "Objet différent",
        }
    )

    with pytest.raises(IdempotencyKeyReusedError):
        dispatcher.dispatch(command=conflicting_command, context=context)

    with Session(database_engine) as session:
        assert session.query(CommandReceiptRecord).filter_by(tenant_id=tenant_id).count() == 1
        assert session.query(DomainEventRecord).filter_by(tenant_id=tenant_id).count() == 1
        assert session.query(OutboxMessageRecord).filter_by(tenant_id=tenant_id).count() == 1
        assert session.execute(
            sa.text("SELECT count(*) FROM consultations WHERE tenant_id = :tenant_id"),
            {"tenant_id": tenant_id},
        ).scalar_one() == 1


class FailingHandler:
    def execute(self, *, session: Session, command, context):  # type: ignore[no-untyped-def]
        del session, command, context
        raise RuntimeError("simulated crash before commit")


@pytest.mark.db
def test_dispatcher_rolls_back_receipt_and_side_effects_before_commit(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id = _insert_tenant(database_engine)
    dispatcher = CommandDispatcher(
        session_factory=session_factory,
        handlers={"CreateConsultation": FailingHandler()},
    )

    with pytest.raises(CommandExecutionError):
        dispatcher.dispatch(command=_command(), context=_context(tenant_id))

    with Session(database_engine) as session:
        assert session.query(CommandReceiptRecord).filter_by(tenant_id=tenant_id).count() == 0
        assert session.query(DomainEventRecord).filter_by(tenant_id=tenant_id).count() == 0
        assert session.query(OutboxMessageRecord).filter_by(tenant_id=tenant_id).count() == 0
        assert session.execute(
            sa.text("SELECT count(*) FROM consultations WHERE tenant_id = :tenant_id"),
            {"tenant_id": tenant_id},
        ).scalar_one() == 0
