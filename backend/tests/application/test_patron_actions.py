from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.modules.patron_action.application.commands import CreatePatronActionCommand
from app.modules.patron_action.application.service import (
    PatronActionService,
    patron_action_handlers,
)
from app.platform.events.dispatcher import CommandDispatcher
from app.platform.security.authorization import AuthorizationPolicy
from app.platform.security.capabilities import capabilities_for
from app.platform.security.context import ActorKind
from app.platform.security.models import PatronActionRecord
from sqlalchemy.orm import Session, sessionmaker

from tests.application.test_collab_work_task import _seed

NOW = datetime(2026, 8, 18, 10, 0, tzinfo=UTC)


@pytest.fixture
def action_service(session_factory: sessionmaker[Session]) -> PatronActionService:
    dispatcher = CommandDispatcher(
        session_factory=session_factory,
        handlers=patron_action_handlers(),
    )
    return PatronActionService(
        session_factory=session_factory,
        dispatcher=dispatcher,
        policy=AuthorizationPolicy(),
    )


def _patron(actor):
    return replace(
        actor,
        actor_kind=ActorKind.PATRON_ADMIN,
        capabilities=capabilities_for(ActorKind.PATRON_ADMIN),
    )


def test_patron_action_is_idempotent_and_readable_in_command_center(
    action_service: PatronActionService, session_factory: sessionmaker[Session]
) -> None:
    collaborator, _, case_id, _ = _seed(session_factory)
    actor = _patron(collaborator)
    action_id = uuid4()
    command = CreatePatronActionCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        action_id=action_id,
        case_id=case_id,
        functional_key=f"preparation-review:{case_id}",
        action_type="REVIEW_PREPARATION",
        severity="BLOCKING",
        title="Revoir la préparation avant décision",
        why_now="La transmission collaborateur est prête pour contrôle.",
        impact="La réponse ne doit pas avancer sans contrôle patron.",
        recommended_action="Ouvrir le dossier de préparation.",
        due_at=NOW + timedelta(hours=12),
        source_refs=["preparation-snapshot"],
    )

    created = action_service.execute(actor=actor, command=command, now=NOW)
    replay = action_service.execute(actor=actor, command=command, now=NOW)

    assert created.result_code == "PATRON_ACTION_CREATED"
    assert replay.replayed is True
    actions = action_service.list_open(actor=actor, now=NOW)
    assert [item.action_id for item in actions] == [action_id]
    assert actions[0].severity == "BLOCKING"
    assert actions[0].case_id == case_id

    with session_factory() as session:
        record = session.get(PatronActionRecord, action_id)
        assert record is not None
        assert record.state == "OPEN"
        assert record.aggregate_revision == 1


def test_patron_action_rejects_collaborator_and_duplicate_business_key(
    action_service: PatronActionService, session_factory: sessionmaker[Session]
) -> None:
    collaborator, _, case_id, _ = _seed(session_factory)
    command = CreatePatronActionCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        action_id=uuid4(),
        case_id=case_id,
        functional_key=f"unique:{case_id}",
        action_type="REVIEW_PREPARATION",
        severity="URGENT",
        title="Contrôler le dépôt",
        why_now="La date limite approche.",
        impact="Le dépôt pourrait être bloqué.",
        recommended_action="Contrôler les pièces.",
        due_at=None,
        source_refs=[],
    )
    with pytest.raises(PermissionError, match="PATRON_REQUIRED"):
        action_service.execute(actor=collaborator, command=command, now=NOW)

    patron = _patron(collaborator)
    action_service.execute(actor=patron, command=command, now=NOW)
    duplicate = command.model_copy(
        update={"command_id": uuid4(), "idempotency_key": uuid4(), "action_id": uuid4()}
    )
    with pytest.raises(RuntimeError, match="PATRON_ACTION_ALREADY_EXISTS"):
        action_service.execute(actor=patron, command=duplicate, now=NOW)
