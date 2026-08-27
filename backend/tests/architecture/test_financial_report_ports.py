from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from app.modules.membership.application.financial_report import (
    FinancialReportLineProjection,
    FinancialReportProjection,
    PatronFinancialReportService,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorKind

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)


def test_financial_report_service_reads_through_application_port() -> None:
    tenant_id = uuid4()
    case_id = uuid4()
    report_id = uuid4()
    reader = Mock()
    reader.get.return_value = FinancialReportProjection(
        report_id=report_id,
        case_id=case_id,
        currency_code="EUR",
        calculated_at=NOW,
        ruleset_version=1,
        summary={"gross_margin_minor": 125_000},
        lines=(
            FinancialReportLineProjection(
                line_id=uuid4(),
                category="SALES",
                label="Prévisionnel",
                quantity_decimal="1",
                unit="forfait",
                amount_minor=125_000,
                currency_code="EUR",
            ),
        ),
        status="DRAFT",
        aggregate_revision=1,
    )
    policy = Mock()
    policy.authorize.return_value = SimpleNamespace(allowed=True)
    actor = SimpleNamespace(
        actor_kind=ActorKind.PATRON_ADMIN,
        membership_id=uuid4(),
        tenant_id=tenant_id,
    )

    projection = PatronFinancialReportService(reader=reader, policy=policy).get_draft(
        actor=actor,
        case_id=case_id,
        report_id=report_id,
        now=NOW,
    )

    assert projection.report_id == report_id
    reader.get.assert_called_once_with(
        tenant_id=tenant_id,
        case_id=case_id,
        report_id=report_id,
        state="DRAFT",
    )
    authorization_request = policy.authorize.call_args.kwargs["request"]
    assert authorization_request.action is Capability.FINANCIAL_REPORT_READ
    assert authorization_request.resource.resource_id == report_id
