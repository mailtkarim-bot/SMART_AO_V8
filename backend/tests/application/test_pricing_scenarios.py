from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.modules.pricing.application.commands import CreatePricingScenarioCommand
from app.modules.pricing.application.service import (
    PricingScenarioService,
    pricing_scenario_handlers,
)
from app.modules.pricing.infrastructure.scenario_reader import SqlAlchemyPricingScenarioReader
from app.platform.events.dispatcher import CommandDispatcher, CommandExecutionError
from app.platform.security.authorization import AuthorizationPolicy
from app.platform.security.models import FinancialReportSnapshotRecord
from sqlalchemy.orm import Session, sessionmaker

from tests.application.test_financial_report_draft_lines import _seed_draft

NOW = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


@pytest.fixture
def pricing_service(session_factory: sessionmaker[Session]) -> PricingScenarioService:
    return PricingScenarioService(
        session_factory=session_factory,
        reader=SqlAlchemyPricingScenarioReader(session_factory),
        dispatcher=CommandDispatcher(
            session_factory=session_factory,
            handlers=pricing_scenario_handlers(),
        ),
        policy=AuthorizationPolicy(),
    )


def test_pricing_scenario_is_deterministic_idempotent_and_private(
    pricing_service: PricingScenarioService, session_factory: sessionmaker[Session]
) -> None:
    actor, case_id, snapshot_id, _ = _seed_draft(session_factory)
    with session_factory.begin() as session:
        snapshot = session.get(FinancialReportSnapshotRecord, snapshot_id)
        snapshot.state = "PUBLISHED"
        snapshot.published_at = NOW
        snapshot.sales_total_minor = 100_000
        snapshot.direct_cost_total_minor = 60_000
        snapshot.overhead_total_minor = 10_000
        snapshot.subcontracting_total_minor = 5_000
        snapshot.contingency_total_minor = 5_000
        snapshot.gross_margin_minor = 20_000
        snapshot.gross_margin_rate_bps = 2000
        snapshot.forecast_cashflow_minor = 15_000

    command = CreatePricingScenarioCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        scenario_id=uuid4(),
        case_id=case_id,
        source_snapshot_id=snapshot_id,
        scenario_key="PRUDENT",
        scenario_type="PRUDENT",
        sales_adjustment_bps=0,
        cost_adjustment_bps=800,
        assumptions={"supplier_buffer_bps": 800},
    )
    created = pricing_service.execute(actor=actor, command=command, now=NOW)
    replay = pricing_service.execute(actor=actor, command=command, now=NOW)
    assert created.result_code == "PRICING_SCENARIO_CREATED"
    assert replay.replayed is True
    projection = pricing_service.list_for_case(actor=actor, case_id=case_id, now=NOW)[0]
    assert projection.sales_total_minor == 100_000
    assert projection.total_cost_minor == 86_400
    assert projection.gross_margin_minor == 13_600
    assert projection.gross_margin_rate_bps == 1360
    assert "supplier_buffer_bps" in projection.assumptions


def test_pricing_scenario_requires_published_snapshot(
    pricing_service: PricingScenarioService, session_factory: sessionmaker[Session]
) -> None:
    actor, case_id, snapshot_id, _ = _seed_draft(session_factory)
    with pytest.raises(CommandExecutionError, match="OFFICIAL_PRICE_NOT_PUBLISHED"):
        pricing_service.execute(
            actor=actor,
            command=CreatePricingScenarioCommand(
                command_id=uuid4(),
                idempotency_key=uuid4(),
                correlation_id=uuid4(),
                scenario_id=uuid4(),
                case_id=case_id,
                source_snapshot_id=snapshot_id,
                scenario_key="BASE",
                scenario_type="BASE",
                sales_adjustment_bps=0,
                cost_adjustment_bps=0,
                assumptions={},
            ),
            now=NOW,
        )
