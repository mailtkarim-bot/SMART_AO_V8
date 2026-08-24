from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.modules.patron_action.application.commands import CreatePatronActionCommand
from app.modules.patron_action.application.service import (
    PatronActionService,
    PatronActionWriter,
    patron_action_handlers,
)
from app.platform.events.dispatcher import CommandContext, CommandDispatcher
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


def test_patron_action_writer_creates_review_action_for_confirmed_risk_link() -> None:
    session = MagicMock()
    session.scalar.return_value = None
    context = CommandContext(
        tenant_id=uuid4(),
        actor_id=uuid4(),
        actor_kind="PATRON_ADMIN",
        received_at=NOW,
        membership_id=uuid4(),
        correlation_id=uuid4(),
    )
    risk_id = uuid4()
    requirement_id = uuid4()
    link_id = uuid4()

    reference = PatronActionWriter().create_from_risk_requirement_link(
        session=session,
        context=context,
        case_id=uuid4(),
        risk_id=risk_id,
        requirement_id=requirement_id,
        link_id=link_id,
        command_id=uuid4(),
        idempotency_key=uuid4(),
    )

    assert reference is not None
    assert reference.id == link_id
    record = session.add.call_args.args[0]
    assert record.action_type == "DECIDE_GO_NO_GO"
    assert record.severity == "BLOCKING"
    assert record.source_refs_json == [
        f"decision-risk:{risk_id}",
        f"dce-requirement:{requirement_id}",
        f"decision-risk-requirement-link:{link_id}",
    ]
    assert "source_excerpt" not in str(record.source_refs_json)


def test_patron_action_writer_is_idempotent_for_existing_risk_link_action() -> None:
    session = MagicMock()
    session.scalar.return_value = SimpleNamespace(id=uuid4())
    context = CommandContext(
        tenant_id=uuid4(),
        actor_id=uuid4(),
        actor_kind="PATRON_ADMIN",
        received_at=NOW,
        membership_id=uuid4(),
    )

    reference = PatronActionWriter().create_from_risk_requirement_link(
        session=session,
        context=context,
        case_id=uuid4(),
        risk_id=uuid4(),
        requirement_id=uuid4(),
        link_id=uuid4(),
        command_id=uuid4(),
        idempotency_key=uuid4(),
    )

    assert reference is None
    session.add.assert_not_called()
