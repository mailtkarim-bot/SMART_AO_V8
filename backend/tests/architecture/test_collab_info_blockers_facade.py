from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from app.modules.membership.application.collab_info_blockers import CollaboratorInfoBlockerService
from app.modules.membership.application.collab_info_blockers_ports import (
    AssignmentProjection,
    TaskProjection,
)
from app.platform.security.context import ActorKind

from tests.support.actors import make_actor_context

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)


def _service(reader: Mock, dispatcher: Mock, policy: Mock) -> CollaboratorInfoBlockerService:
    return CollaboratorInfoBlockerService(reader=reader, dispatcher=dispatcher, policy=policy)


def test_facade_executes_through_reader_port_without_session_factory() -> None:
    case_id = uuid4()
    actor = make_actor_context(actor_kind=ActorKind.COLLABORATEUR)
    reader = Mock()
    reader.resolve_task_id.return_value = None
    reader.resolve_assignment.return_value = AssignmentProjection(case_id=case_id)
    policy = Mock()
    policy.authorize.return_value = SimpleNamespace(allowed=True)
    dispatcher = Mock()
    command = SimpleNamespace(command_type="DeclareTaskBlocker", task_id=uuid4())

    result = _service(reader, dispatcher, policy).execute(actor=actor, command=command, now=NOW)

    dispatcher.dispatch.assert_called_once()
    assert result is dispatcher.dispatch.return_value
    authorization_request = policy.authorize.call_args.kwargs["request"]
    assert authorization_request.resource.case_id == case_id
    assert authorization_request.resource.resource_id == command.task_id
    reader.resolve_assignment.assert_called_once_with(
        tenant_id=actor.tenant_id,
        membership_id=actor.membership_id,
        task_id=command.task_id,
    )


def test_facade_reads_workflow_projection_through_reader_port() -> None:
    task_id = uuid4()
    actor = make_actor_context(actor_kind=ActorKind.COLLABORATEUR)
    reader = Mock()
    reader.resolve_assignment.return_value = AssignmentProjection(case_id=uuid4())
    expected = (TaskProjection(id=task_id, state="IN_PROGRESS", aggregate_revision=2), (), (), ())
    reader.read_workflow.return_value = expected
    policy = Mock()
    policy.authorize.return_value = SimpleNamespace(allowed=True)

    result = _service(reader, Mock(), policy).read_workflow(actor=actor, task_id=task_id, now=NOW)

    assert result == expected
    authorization_request = policy.authorize.call_args.kwargs["request"]
    assert authorization_request.resource.case_id == reader.resolve_assignment.return_value.case_id
    reader.read_workflow.assert_called_once_with(tenant_id=actor.tenant_id, task_id=task_id)


def test_facade_delegates_missing_task_denial_to_reader() -> None:
    actor = make_actor_context(actor_kind=ActorKind.COLLABORATEUR)
    reader = Mock()
    reader.resolve_task_id.return_value = None
    dispatcher = Mock()
    policy = Mock()
    command = SimpleNamespace(command_type="RecordInformationRequestResponse", request_id=uuid4())

    try:
        _service(reader, dispatcher, policy).execute(actor=actor, command=command, now=NOW)
    except PermissionError as error:
        assert str(error) == "NOT_FOUND_OR_FORBIDDEN"
    else:
        raise AssertionError("expected a permission error")

    reader.record_denial.assert_called_once_with(
        actor=actor,
        command=command,
        now=NOW,
        reason="NOT_FOUND_OR_FORBIDDEN",
    )
    dispatcher.dispatch.assert_not_called()
