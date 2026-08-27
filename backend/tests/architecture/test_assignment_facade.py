from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from app.modules.dce.application.commands import AcknowledgeAssignmentCommand
from app.modules.membership.application.assignment import AssignmentInteractionService
from app.modules.membership.application.queries import AssignmentManagementTarget
from app.platform.security.context import ActorKind

from tests.support.actors import make_actor_context

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)


def _service(reader: Mock, dispatcher: Mock, policy: Mock) -> AssignmentInteractionService:
    return AssignmentInteractionService(reader=reader, dispatcher=dispatcher, policy=policy)


def _authorized_policy() -> Mock:
    policy = Mock()
    policy.authorize.return_value = SimpleNamespace(allowed=True)
    return policy


def test_facade_authorizes_with_reader_assignment_and_dispatches() -> None:
    actor = make_actor_context(actor_kind=ActorKind.COLLABORATEUR)
    assignment_id = uuid4()
    case_id = uuid4()
    reader = Mock()
    reader.get_assignment.return_value = AssignmentManagementTarget(
        id=assignment_id,
        case_id=case_id,
        membership_id=actor.membership_id,
    )
    dispatcher = Mock()
    command = AcknowledgeAssignmentCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        assignment_id=assignment_id,
        expected_revision=0,
        note="Affectation reçue.",
    )

    result = _service(reader, dispatcher, _authorized_policy()).acknowledge(
        actor=actor, command=command, now=NOW
    )

    assert result is dispatcher.dispatch.return_value
    assert dispatcher.dispatch.call_args.kwargs["context"].case_id == case_id
    reader.get_assignment.assert_called_once_with(
        tenant_id=actor.tenant_id,
        assignment_id=assignment_id,
    )


def test_facade_delegates_non_collaborator_denial_to_reader() -> None:
    actor = make_actor_context(actor_kind=ActorKind.PATRON_ADMIN)
    reader = Mock()
    command = AcknowledgeAssignmentCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        assignment_id=uuid4(),
        expected_revision=0,
        note="Affectation reçue.",
    )

    try:
        _service(reader, Mock(), _authorized_policy()).acknowledge(
            actor=actor, command=command, now=NOW
        )
    except PermissionError as error:
        assert str(error) == "ASSIGNMENT_COLLABORATOR_REQUIRED"
    else:
        raise AssertionError("expected a permission error")

    reader.record_denial.assert_called_once_with(
        actor=actor,
        command=command,
        now=NOW,
        reason="ASSIGNMENT_COLLABORATOR_REQUIRED",
    )
