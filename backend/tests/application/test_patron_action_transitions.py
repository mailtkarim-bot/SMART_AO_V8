from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import sqlalchemy as sa
from app.modules.patron_action.application.commands import CreatePatronActionCommand
from app.modules.patron_action.application.service import (
    PatronActionService,
    patron_action_handlers,
)
from app.modules.patron_action.application.transition_commands import TransitionPatronActionCommand
from app.modules.patron_action.application.transition_service import (
    PatronActionTransitionService,
    patron_action_transition_handlers,
)
from app.platform.events.dispatcher import CommandDispatcher
from app.platform.security.authorization import AuthorizationPolicy
from app.platform.security.context import ActorKind
from app.platform.security.models import PatronActionTransitionRecord
from sqlalchemy.orm import Session, sessionmaker

from tests.application.test_collab_work_task import _seed
from tests.application.test_patron_actions import _patron

NOW = datetime(2026, 8, 18, 10, 0, tzinfo=UTC)


@pytest.fixture
def services(session_factory: sessionmaker[Session]):
    dispatcher = CommandDispatcher(
        session_factory=session_factory,
        handlers={
            **patron_action_handlers(),
            **patron_action_transition_handlers(),
        },
    )
    policy = AuthorizationPolicy()
    return (
        PatronActionService(
            session_factory=session_factory,
            dispatcher=dispatcher,
            policy=policy,
        ),
        PatronActionTransitionService(
            session_factory=session_factory,
            dispatcher=dispatcher,
            policy=policy,
        ),
    )


def _create_action(action_service, actor, case_id):
    command = CreatePatronActionCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        action_id=uuid4(),
        case_id=case_id,
        functional_key=f"transition:{case_id}",
        action_type="REVIEW_PREPARATION",
        severity="BLOCKING",
        title="Revoir la préparation",
        why_now="La transmission est disponible.",
        impact="Le contrôle patron est requis.",
        recommended_action="Ouvrir le dossier.",
        due_at=None,
        source_refs=["preparation-snapshot"],
    )
    action_service.execute(actor=actor, command=command, now=NOW)
    return command.action_id


def test_action_transitions_are_versioned_idempotent_and_append_only(services, session_factory):
    action_service, transition_service = services
    collaborator, _, case_id, _ = _seed(session_factory)
    patron = _patron(collaborator)
    action_id = _create_action(action_service, patron, case_id)
    command = TransitionPatronActionCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        transition_id=uuid4(),
        action_id=action_id,
        expected_revision=1,
        target_state="IN_PROGRESS",
        reason_code="CONTROL_STARTED",
    )
    created = transition_service.execute(actor=patron, command=command, now=NOW)
    replay = transition_service.execute(actor=patron, command=command, now=NOW)
    assert created.result_code == "PATRON_ACTION_TRANSITIONED"
    assert replay.replayed is True
    assert transition_service.list_open(actor=patron, now=NOW)[0].state == "IN_PROGRESS"
    with session_factory() as session:
        record = session.get(PatronActionTransitionRecord, command.transition_id)
        assert record is not None
        assert record.from_state == "OPEN"
        assert record.to_state == "IN_PROGRESS"
        with pytest.raises(sa.exc.DatabaseError), session.begin_nested():
            session.execute(
                sa.update(PatronActionTransitionRecord)
                .where(PatronActionTransitionRecord.id == command.transition_id)
                .values(to_state="COMPLETED")
            )


def test_action_transition_requires_current_revision_and_patron(services, session_factory):
    action_service, transition_service = services
    collaborator, _, case_id, _ = _seed(session_factory)
    patron = _patron(collaborator)
    action_id = _create_action(action_service, patron, case_id)
    first = TransitionPatronActionCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        transition_id=uuid4(),
        action_id=action_id,
        expected_revision=1,
        target_state="IN_PROGRESS",
        reason_code="CONTROL_STARTED",
    )
    transition_service.execute(actor=patron, command=first, now=NOW)
    stale = TransitionPatronActionCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        transition_id=uuid4(),
        action_id=action_id,
        expected_revision=1,
        target_state="COMPLETED",
        reason_code="DONE",
    )
    with pytest.raises(RuntimeError, match="VERSION_CONFLICT"):
        transition_service.execute(actor=patron, command=stale, now=NOW)
    with pytest.raises(PermissionError, match="PATRON_REQUIRED"):
        transition_service.execute(
            actor=replace(patron, actor_kind=ActorKind.COLLABORATEUR), command=stale, now=NOW
        )
