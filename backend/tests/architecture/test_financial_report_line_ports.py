from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from app.modules.dce.application.commands import AddFinancialReportLineCommand
from app.modules.membership.application.financial_report_lines import (
    PatronFinancialReportLineService,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorKind

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)


def test_financial_line_service_checks_snapshot_through_application_port() -> None:
    tenant_id = uuid4()
    case_id = uuid4()
    report_id = uuid4()
    actor = SimpleNamespace(
        actor_kind=ActorKind.PATRON_ADMIN,
        membership_id=uuid4(),
        tenant_id=tenant_id,
        actor_id=uuid4(),
        identity_id=uuid4(),
        session_id=uuid4(),
        correlation_id=uuid4(),
    )
    command = AddFinancialReportLineCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        case_id=case_id,
        report_id=report_id,
        expected_revision=0,
        category="SALES",
        label="Prévisionnel",
        quantity_decimal="1",
        unit="forfait",
        amount_minor=100,
    )
    reader = Mock()
    reader.exists.return_value = True
    policy = Mock()
    policy.authorize.return_value = SimpleNamespace(allowed=True)
    dispatcher = Mock()
    dispatcher.dispatch.return_value = SimpleNamespace(result_code="OK")

    result = PatronFinancialReportLineService(
        reader=reader,
        dispatcher=dispatcher,
        policy=policy,
    ).add_line(actor=actor, command=command, now=NOW)

    assert result.result_code == "OK"
    reader.exists.assert_called_once_with(
        tenant_id=tenant_id,
        case_id=case_id,
        report_id=report_id,
    )
    authorization_request = policy.authorize.call_args.kwargs["request"]
    assert authorization_request.action is Capability.FINANCIAL_REPORT_LINE_WRITE
    dispatcher.dispatch.assert_called_once()
