import os
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.dce.application.commands import AddFinancialReportLineCommand
from app.modules.membership.application.financial_report_lines import (
    PatronFinancialReportLineService,
    financial_report_line_handlers,
)
from app.platform.events.dispatcher import CommandDispatcher, CommandExecutionError
from app.platform.persistence.models import DomainEventRecord, OutboxMessageRecord, TenantRecord
from app.platform.security.authorization import AuthorizationPolicy
from app.platform.security.capabilities import capabilities_for
from app.platform.security.context import ActorContext, ActorKind, MembershipState
from app.platform.security.models import (
    FinancialReportLineRecord,
    FinancialReportSnapshotRecord,
    IdentityRecord,
    TenantMembershipRecord,
)
from sqlalchemy.orm import Session, sessionmaker

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPOSITORY_ROOT / "backend" / "alembic.ini"
DATABASE_URL = os.getenv("SMART_AO_TEST_DATABASE_URL") or (
    "postgresql+psycopg://"
    + "smart_ao"
    + ":"
    + "smart_ao"
    + "@127.0.0.1:5432/smart_ao"
)
NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


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
def isolate_financial_records(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


def _seed_draft(
    session_factory: sessionmaker[Session],
) -> tuple[ActorContext, UUID, UUID, UUID]:
    tenant_id = uuid4()
    patron_identity_id = uuid4()
    patron_membership_id = uuid4()
    case_id = uuid4()
    report_id = uuid4()

    with session_factory.begin() as session:
        session.add(
            TenantRecord(
                id=tenant_id,
                slug=f"tenant-{tenant_id.hex[:12]}",
                lifecycle="ACTIVE",
            )
        )
        session.add(
            IdentityRecord(
                id=patron_identity_id,
                email_normalized=f"patron-{patron_identity_id.hex[:12]}@example.test",
                lifecycle="ACTIVE",
                email_verified_at=NOW,
            )
        )
        session.add(
            TenantMembershipRecord(
                id=patron_membership_id,
                tenant_id=tenant_id,
                identity_id=patron_identity_id,
                role="PATRON_ADMIN",
                state="ACTIVE",
                activated_at=NOW,
                revoked_at=None,
            )
        )
        session.flush()
        session.add(
            CaseRecord(
                id=case_id,
                tenant_id=tenant_id,
                aggregate_revision=1,
                functional_identity_hash="a" * 64,
                title="Affaire financière de test",
                object_description=None,
                business_origin="MANUAL",
                origin_reference_id=None,
                origin_rationale="Test du chiffrage patron",
                consultation_id=None,
                scope_kind="CUSTOM",
                scope_json={},
                scope_fingerprint="b" * 64,
                applicable_dce_version_id=None,
                lifecycle="ACTIVE",
                commercial_stage="ANALYSIS",
                decision_readiness="NOT_ASSESSED",
                dce_freshness="NO_DCE",
                responsibility_status="UNASSIGNED",
                stopped_reason=None,
                stopped_at=None,
                archived_reason=None,
                archived_at=None,
                created_by_actor_id=None,
                updated_by_actor_id=None,
            )
        )
        session.add(
            FinancialReportSnapshotRecord(
                id=report_id,
                tenant_id=tenant_id,
                case_id=case_id,
                state="DRAFT",
                currency_code="EUR",
                ruleset_version=1,
                aggregate_revision=0,
                calculated_at=NOW,
                published_at=None,
                sales_total_minor=0,
                direct_cost_total_minor=0,
                overhead_total_minor=0,
                subcontracting_total_minor=0,
                contingency_total_minor=0,
                gross_margin_minor=0,
                gross_margin_rate_bps=0,
                forecast_cashflow_minor=0,
            )
        )

    actor = ActorContext(
        actor_id=patron_identity_id,
        identity_id=patron_identity_id,
        tenant_id=tenant_id,
        membership_id=patron_membership_id,
        actor_kind=ActorKind.PATRON_ADMIN,
        membership_state=MembershipState.ACTIVE,
        capabilities=capabilities_for(ActorKind.PATRON_ADMIN),
        assigned_case_ids=frozenset(),
        session_id=uuid4(),
        authenticated_at=NOW,
        mfa_verified_at=NOW,
        correlation_id=uuid4(),
        assignment_scopes=(),
    )
    return actor, case_id, report_id, patron_identity_id


def _service(session_factory: sessionmaker[Session]) -> PatronFinancialReportLineService:
    return PatronFinancialReportLineService(
        session_factory=session_factory,
        dispatcher=CommandDispatcher(
            session_factory=session_factory,
            handlers=financial_report_line_handlers(),
        ),
        policy=AuthorizationPolicy(),
    )


def _command(
    case_id: UUID,
    report_id: UUID,
    *,
    expected_revision: int = 0,
) -> AddFinancialReportLineCommand:
    return AddFinancialReportLineCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        case_id=case_id,
        report_id=report_id,
        expected_revision=expected_revision,
        category="SALES",
        label="Chiffre d'affaires prévisionnel",
        quantity_decimal="1",
        unit="forfait",
        amount_minor=125_000,
    )


@pytest.mark.db
@pytest.mark.security
def test_patron_adds_financial_line_atomically_and_without_financial_event_payload(
    session_factory: sessionmaker[Session],
) -> None:
    actor, case_id, report_id, _ = _seed_draft(session_factory)
    command = _command(case_id, report_id)

    result = _service(session_factory).add_line(actor=actor, command=command, now=NOW)

    assert result.result_code == "FINANCIAL_REPORT_LINE_ADDED"
    with session_factory() as session:
        snapshot = session.get(FinancialReportSnapshotRecord, report_id)
        lines = list(session.scalars(sa.select(FinancialReportLineRecord)))
        events = list(session.scalars(sa.select(DomainEventRecord)))
        outbox = list(session.scalars(sa.select(OutboxMessageRecord)))
    assert snapshot is not None
    assert snapshot.aggregate_revision == 1
    assert snapshot.sales_total_minor == 125_000
    assert len(lines) == 1
    assert lines[0].category == "SALES"
    assert lines[0].amount_minor == 125_000
    assert len(events) == 1
    assert events[0].event_type == "FinancialReportLineAdded"
    assert "amount_minor" not in events[0].payload_json["data"]
    assert len(outbox) == 1
    assert "amount_minor" not in outbox[0].payload_json["data"]


@pytest.mark.db
@pytest.mark.security
def test_replaying_financial_line_command_does_not_create_a_second_line(
    session_factory: sessionmaker[Session],
) -> None:
    actor, case_id, report_id, _ = _seed_draft(session_factory)
    command = _command(case_id, report_id)
    service = _service(session_factory)

    first = service.add_line(actor=actor, command=command, now=NOW)
    replay = service.add_line(actor=actor, command=command, now=NOW)

    assert first.result_code == "FINANCIAL_REPORT_LINE_ADDED"
    assert replay.replayed is True
    assert replay.aggregate_refs == first.aggregate_refs
    with session_factory() as session:
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(FinancialReportLineRecord))
            == 1
        )
        assert session.scalar(sa.select(sa.func.count()).select_from(DomainEventRecord)) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(OutboxMessageRecord)) == 1


@pytest.mark.db
@pytest.mark.security
def test_stale_financial_line_revision_leaves_snapshot_and_line_unchanged(
    session_factory: sessionmaker[Session],
) -> None:
    actor, case_id, report_id, _ = _seed_draft(session_factory)
    command = _command(case_id, report_id, expected_revision=4)

    with pytest.raises(CommandExecutionError, match="VERSION_CONFLICT"):
        _service(session_factory).add_line(actor=actor, command=command, now=NOW)

    with session_factory() as session:
        snapshot = session.get(FinancialReportSnapshotRecord, report_id)
        assert snapshot is not None
        assert snapshot.aggregate_revision == 0
        assert snapshot.sales_total_minor == 0
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(FinancialReportLineRecord))
            == 0
        )
        assert session.scalar(sa.select(sa.func.count()).select_from(DomainEventRecord)) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(OutboxMessageRecord)) == 0


@pytest.mark.db
@pytest.mark.security
def test_collaborator_is_refused_before_financial_snapshot_resolution(
    session_factory: sessionmaker[Session],
) -> None:
    actor, case_id, report_id, _ = _seed_draft(session_factory)
    collaborator = replace(
        actor,
        actor_id=uuid4(),
        identity_id=uuid4(),
        membership_id=uuid4(),
        actor_kind=ActorKind.COLLABORATEUR,
        capabilities=capabilities_for(ActorKind.COLLABORATEUR),
    )

    with pytest.raises(PermissionError, match="FINANCIAL_REPORT_PATRON_REQUIRED"):
        _service(session_factory).add_line(
            actor=collaborator,
            command=_command(case_id, report_id),
            now=NOW,
        )

    with session_factory() as session:
        assert session.get(FinancialReportSnapshotRecord, report_id) is not None
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(FinancialReportLineRecord))
            == 0
        )
        assert case_id is not None


@pytest.mark.db
@pytest.mark.security
def test_published_financial_snapshot_rejects_new_line(
    session_factory: sessionmaker[Session],
) -> None:
    actor, case_id, report_id, _ = _seed_draft(session_factory)
    with session_factory.begin() as session:
        snapshot = session.get(FinancialReportSnapshotRecord, report_id)
        assert snapshot is not None
        snapshot.state = "PUBLISHED"
        snapshot.published_at = NOW

    with pytest.raises(CommandExecutionError, match="FINANCIAL_REPORT_NOT_DRAFT"):
        _service(session_factory).add_line(
            actor=actor,
            command=_command(case_id, report_id),
            now=NOW,
        )

    with session_factory() as session:
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(FinancialReportLineRecord))
            == 0
        )


@pytest.mark.db
@pytest.mark.security
def test_incorrect_revision_after_existing_line_does_not_create_a_second_line(
    session_factory: sessionmaker[Session],
) -> None:
    actor, case_id, report_id, _ = _seed_draft(session_factory)
    service = _service(session_factory)
    first = service.add_line(
        actor=actor,
        command=_command(case_id, report_id),
        now=NOW,
    )

    with pytest.raises(CommandExecutionError, match="VERSION_CONFLICT"):
        service.add_line(
            actor=actor,
            command=_command(case_id, report_id, expected_revision=0),
            now=NOW,
        )

    assert first.result_code == "FINANCIAL_REPORT_LINE_ADDED"
    with session_factory() as session:
        snapshot = session.get(FinancialReportSnapshotRecord, report_id)
        assert snapshot is not None
        assert snapshot.aggregate_revision == 1
        assert snapshot.sales_total_minor == 125_000
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(FinancialReportLineRecord))
            == 1
        )
        assert session.scalar(sa.select(sa.func.count()).select_from(DomainEventRecord)) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(OutboxMessageRecord)) == 1


@pytest.mark.db
@pytest.mark.security
def test_published_snapshot_rejects_line_after_existing_draft_write(
    session_factory: sessionmaker[Session],
) -> None:
    actor, case_id, report_id, _ = _seed_draft(session_factory)
    service = _service(session_factory)
    service.add_line(
        actor=actor,
        command=_command(case_id, report_id),
        now=NOW,
    )
    with session_factory.begin() as session:
        snapshot = session.get(FinancialReportSnapshotRecord, report_id)
        assert snapshot is not None
        snapshot.state = "PUBLISHED"
        snapshot.published_at = NOW

    with pytest.raises(CommandExecutionError, match="FINANCIAL_REPORT_NOT_DRAFT"):
        service.add_line(
            actor=actor,
            command=_command(case_id, report_id, expected_revision=1),
            now=NOW,
        )

    with session_factory() as session:
        snapshot = session.get(FinancialReportSnapshotRecord, report_id)
        assert snapshot is not None
        assert snapshot.state == "PUBLISHED"
        assert snapshot.aggregate_revision == 1
        assert snapshot.sales_total_minor == 125_000
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(FinancialReportLineRecord))
            == 1
        )
        assert session.scalar(sa.select(sa.func.count()).select_from(DomainEventRecord)) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(OutboxMessageRecord)) == 1
