import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from app.modules.membership.application.collab_info_blockers import (
    CollaboratorInfoBlockerService,
    collaborator_info_blocker_handlers,
)
from app.modules.membership.application.collab_info_blockers_commands import (
    CreateInformationRequestCommand,
    DeclareTaskBlockerCommand,
    RecordInformationRequestResponseCommand,
    ResolveTaskBlockerCommand,
)
from app.modules.membership.application.collab_work_task import (
    CollaboratorWorkTaskService,
    collaborator_work_task_handlers,
)
from app.platform.events.dispatcher import CommandDispatcher, CommandExecutionError
from app.platform.persistence.models import DomainEventRecord, OutboxMessageRecord
from app.platform.security.authorization import AuthorizationPolicy
from app.platform.security.models import (
    CollaboratorInformationRequestRecord,
    CollaboratorInformationResponseRecord,
    CollaboratorTaskBlockerRecord,
)
from sqlalchemy.exc import DBAPIError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_collab_work_task import _create as _create_task  # noqa: E402
from test_collab_work_task import _seed  # noqa: E402

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)






def _task_service(factory):
    return CollaboratorWorkTaskService(
        session_factory=factory,
        dispatcher=CommandDispatcher(
            session_factory=factory, handlers=collaborator_work_task_handlers()
        ),
        policy=AuthorizationPolicy(),
    )


def _info_service(factory):
    return CollaboratorInfoBlockerService(
        session_factory=factory,
        dispatcher=CommandDispatcher(
            session_factory=factory, handlers=collaborator_info_blocker_handlers()
        ),
        policy=AuthorizationPolicy(),
    )


def _create_info(task_id: UUID, *, expected_revision: int = 0) -> CreateInformationRequestCommand:
    return CreateInformationRequestCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        request_id=uuid4(),
        task_id=task_id,
        expected_task_revision=expected_revision,
        request_kind="MISSING_SOURCE",
        subject="Source de l’exigence",
        question="Pouvez-vous confirmer la page du RC ?",
        requested_object="Localisation de la source",
        reason="La source est nécessaire pour contrôler l’exigence.",
        priority="HIGH",
    )


@pytest.mark.db
@pytest.mark.security
def test_information_request_response_and_blocker_workflow_is_durable(session_factory) -> None:
    actor, assignment_id, case_id, requirement_id = _seed(session_factory)
    task_service = _task_service(session_factory)
    info_service = _info_service(session_factory)
    task_result = task_service.execute(
        actor=actor,
        command=_create_task(assignment_id, case_id, requirement_id),
        now=NOW,
    )
    task_id = UUID(task_result.aggregate_refs[0]["aggregate_id"])

    create = _create_info(task_id)
    first_request = info_service.execute(actor=actor, command=create, now=NOW)
    replay_request = info_service.execute(actor=actor, command=create, now=NOW)
    request_id = UUID(first_request.aggregate_refs[0]["aggregate_id"])
    response_command_id = uuid4()
    response = info_service.execute(
        actor=actor,
        command=RecordInformationRequestResponseCommand(
            command_id=response_command_id,
            idempotency_key=uuid4(),
            correlation_id=uuid4(),
            request_id=request_id,
            expected_revision=0,
            response_text="La source est RC:p8.",
            source_locator="RC:p8",
            outcome="ANSWERED",
        ),
        now=NOW,
    )
    blocker_command = DeclareTaskBlockerCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        task_id=task_id,
        expected_revision=0,
        blocker_id=uuid4(),
        blocker_kind="MISSING_INFORMATION",
        description="La source doit être vérifiée avant la clôture.",
        source_locator="RC:p8",
        resolution_owner="COLLABORATEUR",
    )
    blocked = info_service.execute(actor=actor, command=blocker_command, now=NOW)
    unblocked = info_service.execute(
        actor=actor,
        command=ResolveTaskBlockerCommand(
            command_id=uuid4(),
            idempotency_key=uuid4(),
            correlation_id=uuid4(),
            task_id=task_id,
            blocker_id=blocker_command.blocker_id,
            expected_revision=1,
            resolution_note="La réponse RC:p8 a été reçue et contrôlée.",
        ),
        now=NOW,
    )

    assert first_request.result_code == "INFORMATION_REQUEST_CREATED"
    assert replay_request.replayed is True
    assert response.result_code == "INFORMATION_REQUEST_ANSWERED"
    assert blocked.result_code == "TASK_BLOCKED"
    assert unblocked.result_code == "TASK_UNBLOCKED"
    with session_factory() as session:
        request = session.get(CollaboratorInformationRequestRecord, request_id)
        assert (
            request is not None and request.state == "ANSWERED" and request.aggregate_revision == 1
        )
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(CollaboratorInformationResponseRecord)
            )
            == 1
        )
        blocker = session.get(CollaboratorTaskBlockerRecord, blocker_command.blocker_id)
        assert blocker is not None and blocker.state == "RESOLVED"
        workflow_events = session.scalars(
            sa.select(DomainEventRecord).where(
                DomainEventRecord.aggregate_id.in_([request_id, task_id])
            )
        ).all()
        assert {event.event_type for event in workflow_events} == {
            "TaskCreatedFromRequirement",
            "InformationRequestCreated",
            "RequestResponseReceived",
            "TaskBlockerDeclared",
            "TaskBlockerResolved",
        }
        assert session.scalar(sa.select(sa.func.count()).select_from(OutboxMessageRecord)) == 5
        financial_payload = str([event.payload_json for event in workflow_events]).lower()
        assert "price" not in financial_payload
        assert "margin" not in financial_payload
        assert "treasury" not in financial_payload


@pytest.mark.db
@pytest.mark.security
def test_info_blocker_rejects_revision_replay_foreign_actor_and_mutation(session_factory) -> None:
    actor, assignment_id, case_id, requirement_id = _seed(session_factory)
    task = _task_service(session_factory).execute(
        actor=actor,
        command=_create_task(assignment_id, case_id, requirement_id),
        now=NOW,
    )
    task_id = UUID(task.aggregate_refs[0]["aggregate_id"])
    service = _info_service(session_factory)
    create = _create_info(task_id)
    service.execute(actor=actor, command=create, now=NOW)
    request_id = create.request_id
    response_command_id = uuid4()
    service.execute(
        actor=actor,
        command=RecordInformationRequestResponseCommand(
            command_id=response_command_id,
            idempotency_key=uuid4(),
            request_id=request_id,
            expected_revision=0,
            response_text="Réponse source RC:p8.",
            outcome="ANSWERED",
        ),
        now=NOW,
    )
    with pytest.raises(CommandExecutionError, match="VERSION_CONFLICT"):
        service.execute(
            actor=actor,
            command=RecordInformationRequestResponseCommand(
                command_id=uuid4(),
                idempotency_key=uuid4(),
                request_id=request_id,
                expected_revision=0,
                response_text="Deuxième réponse.",
                outcome="ANSWERED",
            ),
            now=NOW,
        )
    wrong_actor = replace(actor, membership_id=uuid4())
    with pytest.raises(PermissionError, match="NOT_FOUND_OR_FORBIDDEN"):
        service.execute(actor=wrong_actor, command=create, now=NOW)
    with session_factory.begin() as session:
        stored = session.get(CollaboratorInformationResponseRecord, response_command_id)
        assert stored is not None
        stored.response_text = "mutation interdite"
        with pytest.raises(DBAPIError):
            session.flush()
