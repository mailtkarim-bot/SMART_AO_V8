from datetime import UTC, datetime
from uuid import uuid4

import pytest
import sqlalchemy as sa
from app.modules.dce.application.commands import AddFinancialReportLineCommand
from app.modules.membership.application.financial_report_lines import (
    AddFinancialReportLineHandler,
    financial_report_line_handlers,
)
from app.platform.events.dispatcher import (
    CommandContext,
    CommandDispatcher,
    CommandExecutionError,
    CommandInProgressError,
    canonical_request_hash,
)
from app.platform.persistence.models import (
    CommandReceiptRecord,
    DomainEventRecord,
    OutboxMessageRecord,
)
from app.platform.security.models import FinancialReportSnapshotRecord
from sqlalchemy.orm import Session, sessionmaker

autouse_now = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def isolate_concurrency_records(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


def _seed_draft(session_factory: sessionmaker[Session]):
    from tests.application.test_financial_report_draft_lines import _seed_draft as seed

    return seed(session_factory)


def _command(case_id, report_id, *, expected_revision: int = 0) -> AddFinancialReportLineCommand:
    return AddFinancialReportLineCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        case_id=case_id,
        report_id=report_id,
        expected_revision=expected_revision,
        category="SALES",
        label="Concurrent line",
        quantity_decimal="1",
        unit="forfait",
        amount_minor=125_000,
    )


def _context(actor, *, case_id) -> CommandContext:
    return CommandContext(
        tenant_id=actor.tenant_id,
        actor_id=actor.actor_id,
        actor_kind=actor.actor_kind.value,
        received_at=autouse_now,
        identity_id=actor.identity_id,
        membership_id=actor.membership_id,
        session_id=actor.session_id,
        case_id=case_id,
        correlation_id=actor.correlation_id,
    )


@pytest.mark.concurrency
@pytest.mark.db
def test_stale_writer_is_rejected_after_peer_commits_new_revision(
    session_factory: sessionmaker[Session],
) -> None:
    actor, case_id, report_id, _ = _seed_draft(session_factory)
    command = _command(case_id, report_id, expected_revision=0)
    context = _context(actor, case_id=case_id)
    first_session = session_factory()
    second_session = session_factory()
    try:
        first_session.begin()
        second_session.begin()
        locked_snapshot = first_session.scalar(
            sa.select(FinancialReportSnapshotRecord)
            .where(FinancialReportSnapshotRecord.id == report_id)
            .with_for_update()
        )
        assert locked_snapshot is not None
        observed_by_stale_writer = second_session.scalar(
            sa.select(FinancialReportSnapshotRecord).where(
                FinancialReportSnapshotRecord.id == report_id
            )
        )
        assert observed_by_stale_writer is not None
        assert observed_by_stale_writer.aggregate_revision == 0

        locked_snapshot.aggregate_revision = 1
        locked_snapshot.sales_total_minor = 125_000
        first_session.commit()
        second_session.expire_all()

        with pytest.raises(CommandExecutionError, match="VERSION_CONFLICT"):
            AddFinancialReportLineHandler().execute(
                session=second_session,
                command=command,
                context=context,
            )
        second_session.rollback()
    finally:
        first_session.close()
        second_session.close()

    with session_factory() as session:
        snapshot = session.get(FinancialReportSnapshotRecord, report_id)
        assert snapshot is not None
        assert snapshot.aggregate_revision == 1
        assert snapshot.sales_total_minor == 125_000
        assert session.scalar(sa.select(sa.func.count()).select_from(DomainEventRecord)) == 0


@pytest.mark.concurrency
@pytest.mark.db
@pytest.mark.process
def test_processing_receipt_blocks_second_session_before_outbox_emission(
    session_factory: sessionmaker[Session],
) -> None:
    actor, case_id, report_id, _ = _seed_draft(session_factory)
    command = _command(case_id, report_id)
    context = _context(actor, case_id=case_id)
    with session_factory.begin() as owner_session:
        owner_session.add(
            CommandReceiptRecord(
                id=uuid4(),
                tenant_id=actor.tenant_id,
                actor_id=actor.actor_id,
                command_id=command.command_id,
                command_type=command.command_type,
                idempotency_key=command.idempotency_key,
                request_hash=canonical_request_hash(command),
                correlation_id=command.correlation_id,
                status="PROCESSING",
                lease_expires_at=None,
                event_ids_json=[],
            )
        )

    dispatcher = CommandDispatcher(
        session_factory=session_factory,
        handlers=financial_report_line_handlers(),
    )
    with pytest.raises(CommandInProgressError, match="already being processed"):
        dispatcher.dispatch(command=command, context=context)

    with session_factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(CommandReceiptRecord)) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(OutboxMessageRecord)) == 0
