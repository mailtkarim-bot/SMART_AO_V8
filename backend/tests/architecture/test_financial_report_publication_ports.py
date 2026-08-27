from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock
from uuid import uuid4

from app.modules.dce.application.commands import PublishFinancialReportCommand
from app.modules.membership.application.financial_report_publication import (
    PatronFinancialReportPublicationService,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorKind

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)


def test_financial_publication_service_checks_snapshot_through_reader() -> None:
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
    command = PublishFinancialReportCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        case_id=case_id,
        report_id=report_id,
        expected_revision=0,
    )
    reader = Mock()
    reader.exists.return_value = True
    policy = Mock()
    policy.authorize.return_value = SimpleNamespace(allowed=True)
    dispatcher = Mock()
    dispatcher.dispatch.return_value = SimpleNamespace(result_code="PUBLISHED")

    result = PatronFinancialReportPublicationService(
        reader=reader,
        dispatcher=dispatcher,
        policy=policy,
    ).publish(actor=actor, command=command, now=NOW)

    assert result.result_code == "PUBLISHED"
    reader.exists.assert_called_once_with(
        tenant_id=tenant_id,
        case_id=case_id,
        report_id=report_id,
    )
    authorization_request = policy.authorize.call_args.kwargs["request"]
    assert authorization_request.action is Capability.FINANCIAL_REPORT_PUBLISH
    dispatcher.dispatch.assert_called_once()


def test_financial_report_reader_exists_uses_tenant_case_and_report_filters() -> None:
    from app.modules.membership.infrastructure.financial_report_reader import (
        SqlAlchemyFinancialReportReader,
    )

    tenant_id = uuid4()
    case_id = uuid4()
    report_id = uuid4()
    session = MagicMock()
    session.__enter__.return_value = session
    session.scalar.return_value = report_id
    session_factory = Mock(return_value=session)

    assert SqlAlchemyFinancialReportReader(session_factory).exists(
        tenant_id=tenant_id,
        case_id=case_id,
        report_id=report_id,
    )
    session.scalar.assert_called_once()
