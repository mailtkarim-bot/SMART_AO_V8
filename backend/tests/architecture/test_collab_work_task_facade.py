from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from app.modules.membership.application.collab_work_task import CollaboratorWorkTaskService
from app.modules.membership.application.collab_work_task_ports import (
    AssignmentProjection,
    CollaboratorTaskProjection,
)
from app.platform.security.context import ActorKind

from tests.support.actors import make_actor_context

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)


def _service(reader: Mock, dispatcher: Mock, policy: Mock) -> CollaboratorWorkTaskService:
    return CollaboratorWorkTaskService(reader=reader, dispatcher=dispatcher, policy=policy)


def _authorized_policy() -> Mock:
    policy = Mock()
    policy.authorize.return_value = SimpleNamespace(allowed=True)
    return policy


def test_facade_executes_through_reader_and_dispatcher() -> None:
    actor = make_actor_context(actor_kind=ActorKind.COLLABORATEUR)
    assignment_id = uuid4()
    case_id = uuid4()
    task_id = uuid4()
    reader = Mock()
    reader.resolve_task_assignment_id.return_value = assignment_id
    reader.resolve_assignment.return_value = AssignmentProjection(id=assignment_id, case_id=case_id)
    dispatcher = Mock()
    command = SimpleNamespace(command_type="ClaimTask", task_id=task_id)

    result = _service(reader, dispatcher, _authorized_policy()).execute(
        actor=actor, command=command, now=NOW
    )

    assert result is dispatcher.dispatch.return_value
    authorization_request = dispatcher.dispatch.call_args.kwargs["context"]
    assert authorization_request.case_id == case_id
    reader.resolve_task_assignment_id.assert_called_once_with(
        tenant_id=actor.tenant_id, task_id=task_id
    )
    reader.resolve_assignment.assert_called_once_with(
        tenant_id=actor.tenant_id,
        membership_id=actor.membership_id,
        assignment_id=assignment_id,
    )


def test_facade_lists_projected_tasks_after_active_assignment_check() -> None:
    actor = make_actor_context(actor_kind=ActorKind.COLLABORATEUR)
    assignment_id = uuid4()
    case_id = uuid4()
    reader = Mock()
    reader.resolve_active_assignment_for_case.return_value = AssignmentProjection(
        id=assignment_id, case_id=case_id
    )
    expected = (
        CollaboratorTaskProjection(
            id=uuid4(),
            case_id=case_id,
            assignment_id=assignment_id,
            requirement_id=uuid4(),
            task_kind="REQUIREMENT_CHECK",
            title="Contrôle",
            objective="Vérifier",
            priority="NORMAL",
            state="READY",
            due_at=None,
            aggregate_revision=0,
        ),
    )
    reader.list_for_case.return_value = expected

    result = _service(reader, Mock(), _authorized_policy()).list_for_case(
        actor=actor, case_id=case_id, now=NOW
    )

    assert result == expected
    reader.list_for_case.assert_called_once_with(
        tenant_id=actor.tenant_id,
        case_id=case_id,
        assignment_id=assignment_id,
    )


def test_facade_delegates_non_collaborator_denial_to_reader() -> None:
    actor = make_actor_context(actor_kind=ActorKind.PATRON_ADMIN)
    reader = Mock()
    command = SimpleNamespace(
        command_type="ClaimTask",
        task_id=uuid4(),
        command_id=uuid4(),
        correlation_id=uuid4(),
    )

    try:
        _service(reader, Mock(), _authorized_policy()).execute(
            actor=actor, command=command, now=NOW
        )
    except PermissionError as error:
        assert str(error) == "COLLABORATOR_REQUIRED"
    else:
        raise AssertionError("expected a permission error")

    reader.record_denial.assert_called_once_with(
        actor=actor,
        command=command,
        now=NOW,
        reason="COLLABORATOR_REQUIRED",
    )
