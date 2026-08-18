from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from app.modules.preparation.application.service import (
    PreparationService,
    preparation_handlers,
)
from app.modules.preparation.application.transmission import (
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
from app.platform.events.dispatcher import CommandDispatcher, CommandExecutionError
from app.platform.persistence.models import DomainEventRecord, OutboxMessageRecord
from app.platform.security.authorization import AuthorizationPolicy
from app.platform.security.capabilities import Capability
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
