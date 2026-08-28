from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from app.modules.dce.application.commands import CreateCaseAssignmentCommand
from app.modules.membership.application.patron_assignment import (
    PatronAssignmentManagementService,
)
from app.modules.membership.application.queries import AssignmentManagementCase
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorKind

from tests.support.actors import make_actor_context

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def _service(reader: Mock, dispatcher: Mock, policy: Mock) -> PatronAssignmentManagementService:
    return PatronAssignmentManagementService(
        reader=reader,
        dispatcher=dispatcher,
        policy=policy,
    )


def _command(case_id, target_membership_id) -> CreateCaseAssignmentCommand:
    return CreateCaseAssignmentCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        assignment_id=uuid4(),
        case_id=case_id,
        target_membership_id=target_membership_id,
        expected_case_revision=1,
        scope_actions=(Capability.ASSIGNMENT_ACKNOWLEDGE.value,),
        scope_classifications=("INTERNAL_OPERATIONAL",),
        starts_at=NOW,
        ends_at=NOW + timedelta(days=30),
    )


def _authorized_policy() -> Mock:
    policy = Mock()
    policy.authorize.return_value = SimpleNamespace(allowed=True)
    return policy


def test_facade_resolves_case_from_reader_and_dispatches() -> None:
    actor = make_actor_context(actor_kind=ActorKind.PATRON_ADMIN)
    case_id = uuid4()
    target_membership_id = uuid4()
    command = _command(case_id, target_membership_id)
    reader = Mock()
    reader.get_case.return_value = AssignmentManagementCase(id=case_id, lifecycle="ACTIVE")
    dispatcher = Mock()

    result = _service(reader, dispatcher, _authorized_policy()).create(
        actor=actor,
        command=command,
        now=NOW,
    )

    assert result is dispatcher.dispatch.return_value
    reader.get_case.assert_called_once_with(tenant_id=actor.tenant_id, case_id=case_id)
    assert dispatcher.dispatch.call_args.kwargs["context"].case_id == case_id


def test_facade_delegates_non_patron_refusal_to_reader_audit() -> None:
    actor = make_actor_context(actor_kind=ActorKind.COLLABORATEUR)
    command = _command(uuid4(), uuid4())
    reader = Mock()

    try:
        _service(reader, Mock(), _authorized_policy()).create(
            actor=actor,
            command=command,
            now=NOW,
        )
    except PermissionError as error:
        assert str(error) == "ASSIGNMENT_PATRON_REQUIRED"
    else:
        raise AssertionError("expected a permission error")

    reader.record_denial.assert_called_once_with(
        actor=actor,
        command=command,
        now=NOW,
        reason="ASSIGNMENT_PATRON_REQUIRED",
    )
