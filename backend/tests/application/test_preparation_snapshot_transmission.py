from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import sqlalchemy as sa
from app.modules.preparation.application.service import (
    PreparationService,
    preparation_handlers,
)
from app.modules.preparation.application.transmission import (
    PreparationTransmissionHandler,
    PreparationTransmissionService,
    preparation_transmission_handlers,
)
from app.modules.preparation.application.transmission_commands import (
    CreatePreparationSnapshotCommand,
    TransmitPreparationSnapshotCommand,
)
from app.modules.preparation.infrastructure.dce_preparation_reader import (
    SqlAlchemyPreparationDceReader,
)
from app.modules.preparation.infrastructure.document_storage import LocalGeneratedDocumentStorage
from app.platform.events.dispatcher import (
    CommandContext,
    CommandDispatcher,
    CommandExecutionError,
)
from app.platform.persistence.models import DomainEventRecord, OutboxMessageRecord
from app.platform.security.authorization import AuthorizationPolicy
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorKind
from app.platform.security.models import (
    CaseAssignmentRecord,
    PreparationPackageRecord,
    PreparationSnapshotRecord,
    PreparationTransmissionRecord,
)
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session, sessionmaker

from tests.application.test_preparation_review import _prepare_document

pytest_plugins = ("tests.application.test_preparation_review",)

NOW = datetime(2026, 8, 18, 10, 0, tzinfo=UTC)


@pytest.fixture
def services(session_factory: sessionmaker[Session], tmp_path: Path):
    storage = LocalGeneratedDocumentStorage(root=tmp_path / "dce-private")
    dispatcher = CommandDispatcher(
        session_factory=session_factory,
        handlers={
            **preparation_handlers(
                storage=storage,
                dce_reader=SqlAlchemyPreparationDceReader(),
            ),
            **preparation_transmission_handlers(),
        },
    )
    preparation = PreparationService(
        session_factory=session_factory,
        dispatcher=dispatcher,
        policy=AuthorizationPolicy(),
        storage=storage,
    )
    transmission = PreparationTransmissionService(
        session_factory=session_factory,
        dispatcher=dispatcher,
        policy=AuthorizationPolicy(),
    )
    return transmission, preparation


def test_snapshot_and_transmission_are_idempotent_versioned_and_append_only(
    services, session_factory: sessionmaker[Session]
) -> None:
    transmission, preparation = services
    actor, assignment_id, _, _, package_id, document_id = _prepare_document(
        (preparation, None),
        session_factory,
    )
    actor = _enable_transmission_scope(session_factory, actor, assignment_id)
    snapshot_id = uuid4()
    create = CreatePreparationSnapshotCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        package_id=package_id,
        snapshot_id=snapshot_id,
        expected_package_revision=3,
    )

    prepared = transmission.execute(actor=actor, command=create, now=NOW)
    replay = transmission.execute(actor=actor, command=create, now=NOW)

    assert prepared.result_code == "PREPARATION_SNAPSHOT_CREATED"
    assert replay.replayed is True
    assert replay.event_ids == prepared.event_ids

    transmission_id = uuid4()
    transmit = TransmitPreparationSnapshotCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        package_id=package_id,
        snapshot_id=snapshot_id,
        transmission_id=transmission_id,
        expected_package_revision=4,
    )
    sent = transmission.execute(actor=actor, command=transmit, now=NOW)
    sent_replay = transmission.execute(actor=actor, command=transmit, now=NOW)

    assert sent.result_code == "PREPARATION_TRANSMITTED_TO_PATRON"
    assert sent_replay.replayed is True

    with session_factory() as session:
        package = session.get(PreparationPackageRecord, package_id)
        snapshot = session.get(PreparationSnapshotRecord, snapshot_id)
        sent_record = session.get(PreparationTransmissionRecord, transmission_id)
        assert package is not None
        assert package.aggregate_revision == 5
        assert package.state == "A_REVIEW"
        assert snapshot is not None
        assert snapshot.version == 1
        assert snapshot.manifest_sha256
        assert snapshot.manifest_json["documents"][0]["document_id"] == str(document_id)
        assert "amount_minor" not in str(snapshot.manifest_json)
        assert sent_record is not None
        assert sent_record.state == "TRANSMITTED_TO_PATRON"
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(DomainEventRecord)
                .where(DomainEventRecord.tenant_id == actor.tenant_id)
            )
            >= 5
        )
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(OutboxMessageRecord)
                .where(OutboxMessageRecord.tenant_id == actor.tenant_id)
            )
            >= 5
        )

    with pytest.raises((IntegrityError, ProgrammingError)), session_factory.begin() as session:
        session.execute(
            sa.update(PreparationSnapshotRecord)
            .where(PreparationSnapshotRecord.tenant_id == actor.tenant_id)
            .values(version=2)
        )


def _snapshot_command(*, package_id, snapshot_id=None, expected_revision=3):
    return CreatePreparationSnapshotCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        package_id=package_id,
        snapshot_id=snapshot_id or uuid4(),
        expected_package_revision=expected_revision,
    )


def _handler_context(actor, *, membership_id=None, actor_kind=None) -> CommandContext:
    return CommandContext(
        tenant_id=actor.tenant_id,
        actor_id=actor.actor_id,
        actor_kind=actor_kind or actor.actor_kind.value,
        received_at=NOW,
        identity_id=actor.identity_id,
        membership_id=membership_id if membership_id is not None else actor.membership_id,
        session_id=actor.session_id,
        correlation_id=actor.correlation_id,
    )


@pytest.mark.db
@pytest.mark.security
def test_transmission_service_rejects_non_collaborator_and_missing_package(
    services, session_factory: sessionmaker[Session]
) -> None:
    transmission, preparation = services
    actor, assignment_id, _, _, package_id, _ = _prepare_document(
        (preparation, None), session_factory
    )
    actor = _enable_transmission_scope(session_factory, actor, assignment_id)
    command = _snapshot_command(package_id=package_id)

    with pytest.raises(PermissionError, match="COLLABORATOR_REQUIRED"):
        transmission.execute(
            actor=replace(actor, actor_kind=ActorKind.PATRON_ADMIN),
            command=command,
            now=NOW,
        )
    with pytest.raises(PermissionError, match="NOT_FOUND_OR_FORBIDDEN"):
        transmission.execute(
            actor=actor,
            command=_snapshot_command(package_id=uuid4()),
            now=NOW,
        )

    assert preparation is not None


@pytest.mark.db
@pytest.mark.security
def test_transmission_handler_rejects_invalid_membership_and_assignment_scope(
    services, session_factory: sessionmaker[Session]
) -> None:
    _, preparation = services
    actor, assignment_id, _, _, package_id, _ = _prepare_document(
        (preparation, None), session_factory
    )
    handler = PreparationTransmissionHandler()
    command = _snapshot_command(package_id=package_id)

    with (
        pytest.raises(CommandExecutionError, match="NOT_FOUND_OR_FORBIDDEN"),
        session_factory.begin() as session,
    ):
        handler.execute(
            session=session,
            command=command,
            context=_handler_context(actor, membership_id=uuid4()),
        )

    with session_factory.begin() as session:
        assignment = session.get(CaseAssignmentRecord, assignment_id)
        assert assignment is not None
        assignment.scope_actions_json = [Capability.PREPARATION_TRANSMIT.value]

    with (
        pytest.raises(CommandExecutionError, match="ASSIGNMENT_SCOPE_FORBIDDEN"),
        session_factory.begin() as session,
    ):
        handler.execute(
            session=session,
            command=_snapshot_command(package_id=package_id),
            context=_handler_context(actor),
        )

    assert preparation is not None


@pytest.mark.db
@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("state", "PREPARATION_NOT_GENERATED"),
        ("readiness_missing", "READINESS_NOT_FOUND"),
        ("readiness_blocked", "PREPARATION_BLOCKED"),
        ("document_missing", "TECHNICAL_DOCUMENT_REQUIRED"),
    ],
)
def test_snapshot_handler_rejects_incomplete_preparation(
    mutation: str, error: str
) -> None:
    package = SimpleNamespace(
        id=uuid4(),
        tenant_id=uuid4(),
        assignment_id=uuid4(),
        case_id=uuid4(),
        dce_version_id=uuid4(),
        state="IN_PREPARATION" if mutation == "state" else "GENERATED",
        aggregate_revision=3,
    )
    assignment = SimpleNamespace(scope_actions_json=[Capability.WORK_TASK_WRITE.value])
    readiness = None
    if mutation == "readiness_blocked":
        readiness = SimpleNamespace(
            id=uuid4(),
            revision=2,
            state="BLOCKED",
            blocker_codes_json=[],
            warning_codes_json=[],
        )
    elif mutation == "document_missing":
        readiness = SimpleNamespace(
            id=uuid4(),
            revision=2,
            state="READY",
            blocker_codes_json=[],
            warning_codes_json=[],
        )

    class FakeScalarResult:
        def __init__(self, values):
            self.values = values

        def all(self):
            return self.values

    class FakeSession:
        def __init__(self) -> None:
            self.scalar_calls = 0

        def scalar(self, statement):
            self.scalar_calls += 1
            if self.scalar_calls == 1:
                return package
            if self.scalar_calls == 2:
                return assignment
            return readiness

        def scalars(self, statement):
            return FakeScalarResult([])

        def add(self, value) -> None:
            raise AssertionError("incomplete preparation must fail before persistence")

    command = _snapshot_command(package_id=package.id)
    context = CommandContext(
        tenant_id=package.tenant_id,
        actor_id=uuid4(),
        actor_kind=ActorKind.COLLABORATEUR.value,
        received_at=NOW,
        membership_id=uuid4(),
        correlation_id=uuid4(),
    )

    with pytest.raises(CommandExecutionError, match=error):
        PreparationTransmissionHandler().execute(
            session=FakeSession(), command=command, context=context
        )


@pytest.mark.db
@pytest.mark.security
def test_transmit_handler_rejects_missing_and_already_transmitted_snapshot(
    services, session_factory: sessionmaker[Session]
) -> None:
    transmission, preparation = services
    actor, assignment_id, _, _, package_id, _ = _prepare_document(
        (preparation, None), session_factory
    )
    actor = _enable_transmission_scope(session_factory, actor, assignment_id)
    snapshot_id = uuid4()
    transmission.execute(
        actor=actor,
        command=_snapshot_command(package_id=package_id, snapshot_id=snapshot_id),
        now=NOW,
    )

    handler = PreparationTransmissionHandler()
    transmit = TransmitPreparationSnapshotCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        package_id=package_id,
        snapshot_id=uuid4(),
        transmission_id=uuid4(),
        expected_package_revision=4,
    )
    with pytest.raises(
        CommandExecutionError, match="SNAPSHOT_NOT_FOUND_OR_FORBIDDEN"
    ), session_factory.begin() as session:
        handler.execute(
            session=session,
            command=transmit,
            context=_handler_context(actor),
        )

    with session_factory.begin() as session:
        snapshot = session.get(PreparationSnapshotRecord, snapshot_id)
        package = session.get(PreparationPackageRecord, package_id)
        assert snapshot is not None and package is not None
        session.add(
            PreparationTransmissionRecord(
                id=uuid4(),
                tenant_id=actor.tenant_id,
                package_id=package_id,
                snapshot_id=snapshot_id,
                state="TRANSMITTED_TO_PATRON",
                actor_id=actor.actor_id,
                membership_id=actor.membership_id,
                command_id=uuid4(),
                idempotency_key=uuid4(),
                correlation_id=uuid4(),
            )
        )

    duplicate = TransmitPreparationSnapshotCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        package_id=package_id,
        snapshot_id=snapshot_id,
        transmission_id=uuid4(),
        expected_package_revision=4,
    )
    with (
        pytest.raises(CommandExecutionError, match="SNAPSHOT_ALREADY_TRANSMITTED"),
        session_factory.begin() as session,
    ):
        handler.execute(
            session=session,
            command=duplicate,
            context=_handler_context(actor),
        )


@pytest.mark.db
@pytest.mark.security
def test_transmit_handler_emits_patron_action_event_when_writer_returns_action(
    services, session_factory: sessionmaker[Session]
) -> None:
    transmission, preparation = services
    actor, assignment_id, case_id, _, package_id, _ = _prepare_document(
        (preparation, None), session_factory
    )
    actor = _enable_transmission_scope(session_factory, actor, assignment_id)
    snapshot_id = uuid4()
    transmission.execute(
        actor=actor,
        command=_snapshot_command(package_id=package_id, snapshot_id=snapshot_id),
        now=NOW,
    )

    class Writer:
        def create_from_preparation_transmission(self, **kwargs):
            return SimpleNamespace(
                id=kwargs["transmission_id"],
                aggregate_revision=1,
                case_id=case_id,
                action_type="REVIEW_PREPARATION",
                severity="BLOCKING",
                state="OPEN",
            )

    handler = PreparationTransmissionHandler(action_writer=Writer())
    command = TransmitPreparationSnapshotCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        package_id=package_id,
        snapshot_id=snapshot_id,
        transmission_id=uuid4(),
        expected_package_revision=4,
    )
    with session_factory.begin() as session:
        outcome = handler.execute(
            session=session,
            command=command,
            context=_handler_context(actor),
        )

    assert outcome.result_code == "PREPARATION_TRANSMITTED_TO_PATRON"
    assert len(outcome.events) == 2
    assert outcome.events[1].event_type == "PatronActionCreated"


def _enable_transmission_scope(session_factory: sessionmaker[Session], actor, assignment_id):
    with session_factory.begin() as session:
        assignment = session.get(CaseAssignmentRecord, assignment_id)
        assignment.scope_actions_json = [
            *assignment.scope_actions_json,
            Capability.PREPARATION_TRANSMIT.value,
        ]
    scope = actor.assignment_scopes[0]
    return replace(
        actor,
        assignment_scopes=(
            replace(
                scope,
                allowed_actions=frozenset(
                    {*scope.allowed_actions, Capability.PREPARATION_TRANSMIT.value}
                ),
            ),
        ),
    )


def test_snapshot_requires_current_revision_and_assignment_scope(
    services, session_factory: sessionmaker[Session]
) -> None:
    transmission, preparation = services
    actor, assignment_id, _, _, package_id, _ = _prepare_document(
        (preparation, None),
        session_factory,
    )
    actor = _enable_transmission_scope(session_factory, actor, assignment_id)
    with pytest.raises(CommandExecutionError, match="VERSION_CONFLICT"):
        transmission.execute(
            actor=actor,
            command=CreatePreparationSnapshotCommand(
                command_id=uuid4(),
                idempotency_key=uuid4(),
                correlation_id=uuid4(),
                package_id=package_id,
                snapshot_id=uuid4(),
                expected_package_revision=2,
            ),
            now=NOW,
        )

    with pytest.raises(PermissionError, match="AUTHORIZATION_DENIED"):
        transmission.execute(
            actor=replace(actor, assignment_scopes=()),
            command=CreatePreparationSnapshotCommand(
                command_id=uuid4(),
                idempotency_key=uuid4(),
                correlation_id=uuid4(),
                package_id=package_id,
                snapshot_id=uuid4(),
                expected_package_revision=3,
            ),
            now=NOW,
        )
