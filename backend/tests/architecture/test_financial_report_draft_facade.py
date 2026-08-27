from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from app.modules.dce.application.commands import CreateFinancialReportDraftCommand
from app.modules.membership.application.financial_report_draft import (
    PatronFinancialReportDraftCreationService,
)
from app.platform.security.context import ActorKind

from tests.support.actors import make_actor_context

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)


def _service(
    reader: Mock, dispatcher: Mock, policy: Mock
) -> PatronFinancialReportDraftCreationService:
    return PatronFinancialReportDraftCreationService(
        reader=reader,
        dispatcher=dispatcher,
        policy=policy,
    )


def _command() -> CreateFinancialReportDraftCommand:
    return CreateFinancialReportDraftCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        case_id=uuid4(),
        currency_code="EUR",
        ruleset_version=1,
    )


def _authorized_policy() -> Mock:
    policy = Mock()
    policy.authorize.return_value = SimpleNamespace(allowed=True)
    return policy


def test_facade_guards_financial_reader_before_non_patron_access() -> None:
    actor = make_actor_context(actor_kind=ActorKind.COLLABORATEUR)
    reader = Mock()
    policy = _authorized_policy()

    try:
        _service(reader, Mock(), policy).create(actor=actor, command=_command(), now=NOW)
    except PermissionError as error:
        assert str(error) == "FINANCIAL_REPORT_PATRON_REQUIRED"
    else:
        raise AssertionError("expected a permission error")

    reader.exists.assert_not_called()
    policy.authorize.assert_not_called()


def test_facade_authorizes_case_and_dispatches_without_orm_dependency() -> None:
    actor = make_actor_context(actor_kind=ActorKind.PATRON_ADMIN)
    command = _command()
    reader = Mock()
    reader.exists.return_value = True
    dispatcher = Mock()

    result = _service(reader, dispatcher, _authorized_policy()).create(
        actor=actor, command=command, now=NOW
    )

    assert result is dispatcher.dispatch.return_value
    assert dispatcher.dispatch.call_args.kwargs["context"].case_id == command.case_id
    reader.exists.assert_called_once_with(
        tenant_id=actor.tenant_id,
        case_id=command.case_id,
    )
