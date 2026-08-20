from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import sqlalchemy as sa
from app.modules.pricing.application.commands import CreatePricingScenarioCommand
from app.modules.pricing.application.service import (
    PricingScenarioService,
    pricing_scenario_handlers,
)
from app.modules.pricing.application.transition_commands import TransitionPricingScenarioCommand
from app.modules.pricing.application.transition_service import (
    PricingScenarioTransitionService,
    pricing_scenario_transition_handlers,
)
from app.platform.events.dispatcher import CommandDispatcher
from app.platform.security.authorization import AuthorizationPolicy
from app.platform.security.capabilities import capabilities_for
from app.platform.security.context import ActorKind
from app.platform.security.models import PricingScenarioTransitionRecord
from sqlalchemy.orm import Session, sessionmaker

from tests.application.test_financial_report_draft_lines import _seed_draft

NOW = datetime(2026, 8, 18, 10, 0, tzinfo=UTC)


@pytest.fixture
def services(session_factory: sessionmaker[Session]):
    dispatcher = CommandDispatcher(
        session_factory=session_factory,
        handlers={
            **pricing_scenario_handlers(),
            **pricing_scenario_transition_handlers(),
        },
    )
    policy = AuthorizationPolicy()
    return (
        PricingScenarioService(
            session_factory=session_factory,
            dispatcher=dispatcher,
            policy=policy,
        ),
        PricingScenarioTransitionService(
            session_factory=session_factory,
            dispatcher=dispatcher,
            policy=policy,
        ),
    )


def _published_snapshot(session_factory, snapshot_id):
    with session_factory.begin() as session:
        snapshot = session.get(__import__(
            "app.platform.security.models", fromlist=["FinancialReportSnapshotRecord"]
        ).FinancialReportSnapshotRecord, snapshot_id)
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


def _create(pricing_service, actor, case_id, snapshot_id, key):
    command = CreatePricingScenarioCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        scenario_id=uuid4(),
        case_id=case_id,
        source_snapshot_id=snapshot_id,
        scenario_key=key,
        scenario_type=key,
        sales_adjustment_bps=0,
        cost_adjustment_bps=0,
        assumptions={},
    )
    pricing_service.execute(actor=actor, command=command, now=NOW)
    return command.scenario_id


def test_pricing_scenario_selection_and_archive_are_append_only_and_idempotent(
    services, session_factory
):
    pricing_service, transition_service = services
    actor, case_id, snapshot_id, _ = _seed_draft(session_factory)
    _published_snapshot(session_factory, snapshot_id)
    scenario_id = _create(pricing_service, actor, case_id, snapshot_id, "BASE")
    select = TransitionPricingScenarioCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        transition_id=uuid4(),
        scenario_id=scenario_id,
        expected_version=1,
        target_state="SELECTED",
        reason_code="PATRON_SELECTED",
    )
    created = transition_service.execute(actor=actor, command=select, now=NOW)
    replay = transition_service.execute(actor=actor, command=select, now=NOW)
    assert created.result_code == "PRICING_SCENARIO_TRANSITIONED"
    assert replay.replayed is True
    selected = transition_service.list_for_case(actor=actor, case_id=case_id, now=NOW)[0]
    assert selected.state == "SELECTED"
    archive = select.model_copy(
        update={
            "command_id": uuid4(),
            "idempotency_key": uuid4(),
            "transition_id": uuid4(),
            "expected_version": 2,
            "target_state": "ARCHIVED",
            "reason_code": "REPLACED",
        }
    )
    transition_service.execute(actor=actor, command=archive, now=NOW)
    archived = transition_service.list_for_case(actor=actor, case_id=case_id, now=NOW)[0]
    assert archived.state == "ARCHIVED"
    with session_factory() as session:
        record = session.get(PricingScenarioTransitionRecord, select.transition_id)
        assert record is not None
        with pytest.raises(sa.exc.DatabaseError), session.begin_nested():
            session.execute(
                sa.update(PricingScenarioTransitionRecord)
                .where(PricingScenarioTransitionRecord.id == select.transition_id)
                .values(to_state="SELECTED")
            )


def test_pricing_scenario_transition_requires_current_version_and_patron(services, session_factory):
    pricing_service, transition_service = services
    actor, case_id, snapshot_id, _ = _seed_draft(session_factory)
    _published_snapshot(session_factory, snapshot_id)
    scenario_id = _create(pricing_service, actor, case_id, snapshot_id, "BASE")
    first = TransitionPricingScenarioCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        transition_id=uuid4(),
        scenario_id=scenario_id,
        expected_version=1,
        target_state="SELECTED",
        reason_code="PATRON_SELECTED",
    )
    transition_service.execute(actor=actor, command=first, now=NOW)
    stale = first.model_copy(
        update={
            "command_id": uuid4(),
            "idempotency_key": uuid4(),
            "transition_id": uuid4(),
            "expected_version": 1,
            "target_state": "ARCHIVED",
        }
    )
    with pytest.raises(RuntimeError, match="VERSION_CONFLICT"):
        transition_service.execute(actor=actor, command=stale, now=NOW)
    collaborator = replace(
        actor,
        actor_id=uuid4(),
        identity_id=uuid4(),
        membership_id=uuid4(),
        actor_kind=ActorKind.COLLABORATEUR,
        capabilities=capabilities_for(ActorKind.COLLABORATEUR),
    )
    with pytest.raises(PermissionError, match="PATRON_REQUIRED"):
        transition_service.execute(actor=collaborator, command=stale, now=NOW)


def test_pricing_scenario_selection_rejects_another_active_selection(services, session_factory):
    pricing_service, transition_service = services
    actor, case_id, snapshot_id, _ = _seed_draft(session_factory)
    _published_snapshot(session_factory, snapshot_id)
    first_id = _create(pricing_service, actor, case_id, snapshot_id, "BASE")
    second_id = _create(pricing_service, actor, case_id, snapshot_id, "PRUDENT")
    first = TransitionPricingScenarioCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        transition_id=uuid4(),
        scenario_id=first_id,
        expected_version=1,
        target_state="SELECTED",
        reason_code="PATRON_SELECTED",
    )
    second = first.model_copy(
        update={
            "command_id": uuid4(),
            "idempotency_key": uuid4(),
            "transition_id": uuid4(),
            "scenario_id": second_id,
        }
    )
    transition_service.execute(actor=actor, command=first, now=NOW)
    with pytest.raises(RuntimeError, match="SCENARIO_ALREADY_SELECTED"):
        transition_service.execute(actor=actor, command=second, now=NOW)
