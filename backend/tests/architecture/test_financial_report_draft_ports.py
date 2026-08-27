from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock
from uuid import uuid4

from app.modules.dce.application.commands import CreateFinancialReportDraftCommand
from app.modules.membership.application.financial_report_draft import (
    PatronFinancialReportDraftCreationService,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorKind

from tests.support.actors import make_actor_context

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)


def test_financial_draft_service_checks_case_through_application_port() -> None:
    tenant_id = uuid4()
    case_id = uuid4()
    actor = make_actor_context(tenant_id=tenant_id)
    command = CreateFinancialReportDraftCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        case_id=case_id,
        currency_code="EUR",
        ruleset_version=1,
    )
    reader = Mock()
    reader.exists.return_value = True
    policy = Mock()
    policy.authorize.return_value = SimpleNamespace(allowed=True)
    dispatcher = Mock()
    dispatcher.dispatch.return_value = SimpleNamespace(result_code="OK")

    result = PatronFinancialReportDraftCreationService(
        reader=reader,
        dispatcher=dispatcher,
        policy=policy,
    ).create(actor=actor, command=command, now=NOW)

    assert result.result_code == "OK"
    reader.exists.assert_called_once_with(tenant_id=tenant_id, case_id=case_id)
    authorization_request = policy.authorize.call_args.kwargs["request"]
    assert authorization_request.action is Capability.FINANCIAL_REPORT_CREATE
    dispatcher.dispatch.assert_called_once()


def _draft_command(case_id):
    return CreateFinancialReportDraftCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        case_id=case_id,
    )


def test_financial_draft_service_rejects_non_patron_before_reader() -> None:
    reader = Mock()
    actor = make_actor_context(actor_kind=ActorKind.COLLABORATEUR)

    try:
        PatronFinancialReportDraftCreationService(
            reader=reader,
            dispatcher=Mock(),
            policy=Mock(),
        ).create(actor=actor, command=_draft_command(uuid4()), now=NOW)
    except PermissionError as error:
        assert str(error) == "FINANCIAL_REPORT_PATRON_REQUIRED"
    else:
        raise AssertionError("non-patron actor should be rejected")

    reader.exists.assert_not_called()


def test_financial_draft_service_rejects_unknown_case_before_dispatch() -> None:
    tenant_id = uuid4()
    case_id = uuid4()
    reader = Mock()
    reader.exists.return_value = False
    policy = Mock()
    policy.authorize.return_value = SimpleNamespace(allowed=True)
    actor = make_actor_context(tenant_id=tenant_id)
    dispatcher = Mock()

    try:
        PatronFinancialReportDraftCreationService(
            reader=reader,
            dispatcher=dispatcher,
            policy=policy,
        ).create(actor=actor, command=_draft_command(case_id), now=NOW)
    except PermissionError as error:
        assert str(error) == "NOT_FOUND_OR_FORBIDDEN"
    else:
        raise AssertionError("unknown case should be rejected")

    reader.exists.assert_called_once_with(tenant_id=tenant_id, case_id=case_id)
    dispatcher.dispatch.assert_not_called()


def test_financial_draft_service_rejects_denied_policy_before_reader() -> None:
    tenant_id = uuid4()
    actor = make_actor_context(tenant_id=tenant_id)
    reader = Mock()
    policy = Mock()
    policy.authorize.return_value = SimpleNamespace(allowed=False, code="DENIED")

    try:
        PatronFinancialReportDraftCreationService(
            reader=reader,
            dispatcher=Mock(),
            policy=policy,
        ).create(actor=actor, command=_draft_command(uuid4()), now=NOW)
    except PermissionError as error:
        assert str(error) == "DENIED"
    else:
        raise AssertionError("denied policy should reject the draft")

    reader.exists.assert_not_called()


def test_financial_draft_case_reader_is_tenant_scoped() -> None:
    from app.modules.membership.infrastructure.financial_draft_case_reader import (
        SqlAlchemyFinancialDraftCaseReader,
    )

    tenant_id = uuid4()
    case_id = uuid4()
    session = MagicMock()
    session.__enter__.return_value = session
    session.scalar.return_value = case_id
    session_factory = Mock(return_value=session)

    assert SqlAlchemyFinancialDraftCaseReader(session_factory).exists(
        tenant_id=tenant_id,
        case_id=case_id,
    )
    session.scalar.assert_called_once()
