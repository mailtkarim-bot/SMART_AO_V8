from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from app.modules.dce.infrastructure.models.dce_requirement_confirmations import (
    DceRequirementConfirmationCurrentRecord,
    DceRequirementConfirmationRecord,
)
from app.modules.preparation.application.commands import (
    EvaluatePreparationReadinessCommand,
    GenerateTechnicalDocumentCommand,
)
from app.modules.preparation.application.service import PreparationService, preparation_handlers
from app.modules.preparation.infrastructure.document_storage import LocalGeneratedDocumentStorage
from app.platform.events.dispatcher import CommandDispatcher, CommandExecutionError
from app.platform.persistence.models import DomainEventRecord, OutboxMessageRecord
from app.platform.security.authorization import AuthorizationPolicy
from app.platform.security.capabilities import Capability
from app.platform.security.context import AssignmentScope, DataClassification
from app.platform.security.models import (
    CaseAssignmentRecord,
    CollaboratorTaskRecord,
    GeneratedTechnicalDocumentRecord,
    PreparationPackageRecord,
    PreparationReadinessRecord,
)
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session, sessionmaker

from tests.application.test_collab_work_task import NOW, _seed

pytest_plugins = ("tests.application.test_collab_work_task",)


@pytest.fixture
def preparation_service(
    session_factory: sessionmaker[Session], tmp_path: Path
) -> PreparationService:
    storage = LocalGeneratedDocumentStorage(root=tmp_path / "dce-private")
    dispatcher = CommandDispatcher(
        session_factory=session_factory,
        handlers=preparation_handlers(storage=storage),
    )
    return PreparationService(
        session_factory=session_factory,
        dispatcher=dispatcher,
        policy=AuthorizationPolicy(),
        storage=storage,
    )


def _readiness_command(
    *, actor, assignment_id, case_id, dce_version_id, package_id, expected_revision
):
    return EvaluatePreparationReadinessCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        package_id=package_id,
        case_id=case_id,
        assignment_id=assignment_id,
        dce_version_id=dce_version_id,
        expected_revision=expected_revision,
    )


def _confirm_requirement(session_factory, *, actor, requirement_id) -> None:
    confirmation_id = uuid4()
    with session_factory.begin() as session:
        session.add(
            DceRequirementConfirmationRecord(
                id=confirmation_id,
                tenant_id=actor.tenant_id,
                requirement_id=requirement_id,
                revision=1,
                previous_confirmation_id=None,
                outcome="CONFIRMED",
                reason_code="SOURCE_REVIEWED",
                confirmed_by_actor_id=actor.actor_id,
            )
        )
        session.flush()
        session.add(
            DceRequirementConfirmationCurrentRecord(
                tenant_id=actor.tenant_id,
                requirement_id=requirement_id,
                confirmation_id=confirmation_id,
                revision=1,
                outcome="CONFIRMED",
            )
        )


def test_preparation_cycle_blocked_then_ready_then_document_is_append_only(
    preparation_service: PreparationService, session_factory: sessionmaker[Session]
) -> None:
    actor, assignment_id, case_id, requirement_id = _seed(session_factory)
    actor = _enable_preparation_scope(session_factory, actor, assignment_id)
    dce_version_id = _dce_version_id(session_factory, actor.tenant_id)
    package_id = uuid4()

    blocked_command = _readiness_command(
        actor=actor,
        assignment_id=assignment_id,
        case_id=case_id,
        dce_version_id=dce_version_id,
        package_id=package_id,
        expected_revision=0,
    )
    blocked = preparation_service.execute(actor=actor, command=blocked_command, now=NOW)
    assert blocked.result_code == "PREPARATION_READINESS_EVALUATED"
    assert not blocked.replayed
    assert _latest_readiness(session_factory, actor.tenant_id, package_id).state == "BLOCKED"

    replay = preparation_service.execute(actor=actor, command=blocked_command, now=NOW)
    assert replay.replayed
    assert replay.event_ids == blocked.event_ids

    _confirm_requirement(session_factory, actor=actor, requirement_id=requirement_id)
    ready_command = _readiness_command(
        actor=actor,
        assignment_id=assignment_id,
        case_id=case_id,
        dce_version_id=dce_version_id,
        package_id=package_id,
        expected_revision=1,
    )
    preparation_service.execute(actor=actor, command=ready_command, now=NOW)
    assert _latest_readiness(session_factory, actor.tenant_id, package_id).state == "READY"

    document_command = GenerateTechnicalDocumentCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        package_id=package_id,
        document_id=uuid4(),
        expected_revision=2,
        readiness_revision=2,
        document_kind="TECHNICAL_RESPONSE",
    )
    generated = preparation_service.execute(actor=actor, command=document_command, now=NOW)
    assert generated.result_code == "TECHNICAL_DOCUMENT_GENERATED"

    with session_factory() as session:
        package = session.get(PreparationPackageRecord, package_id)
        readiness_rows = session.scalars(
            sa.select(PreparationReadinessRecord).where(
                PreparationReadinessRecord.tenant_id == actor.tenant_id,
                PreparationReadinessRecord.package_id == package_id,
            )
        ).all()
        documents = session.scalars(
            sa.select(GeneratedTechnicalDocumentRecord).where(
                GeneratedTechnicalDocumentRecord.tenant_id == actor.tenant_id,
                GeneratedTechnicalDocumentRecord.package_id == package_id,
            )
        ).all()
        assert package.aggregate_revision == 3
        assert package.state == "GENERATED"
        assert [row.revision for row in readiness_rows] == [1, 2]
        assert [row.version for row in documents] == [1]
        assert documents[0].storage_key.startswith("generated-documents/")
        assert documents[0].content_sha256
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(DomainEventRecord)
                .where(
                    DomainEventRecord.tenant_id == actor.tenant_id,
                    DomainEventRecord.aggregate_id.in_([package_id, documents[0].id]),
                )
            )
            == 3
        )
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(OutboxMessageRecord)
                .where(OutboxMessageRecord.tenant_id == actor.tenant_id)
            )
            >= 3
        )

    with pytest.raises((IntegrityError, ProgrammingError)), session_factory.begin() as session:
        session.execute(
            sa.update(PreparationReadinessRecord)
            .where(PreparationReadinessRecord.tenant_id == actor.tenant_id)
            .values(state="READY")
        )


def test_readiness_warning_allows_document_when_task_has_no_result(
    preparation_service: PreparationService, session_factory: sessionmaker[Session]
) -> None:
    actor, assignment_id, case_id, requirement_id = _seed(session_factory)
    actor = _enable_preparation_scope(session_factory, actor, assignment_id)
    dce_version_id = _dce_version_id(session_factory, actor.tenant_id)
    _confirm_requirement(session_factory, actor=actor, requirement_id=requirement_id)
    with session_factory.begin() as session:
        session.add(
            CollaboratorTaskRecord(
                id=uuid4(),
                tenant_id=actor.tenant_id,
                case_id=case_id,
                assignment_id=assignment_id,
                requirement_id=requirement_id,
                task_kind="TECHNICAL_PREPARATION",
                title="Vérifier la conformité technique",
                objective="Contrôler les pièces et la cohérence documentaire",
                priority="NORMAL",
                state="IN_PROGRESS",
                functional_key=f"preparation-{uuid4()}",
                aggregate_revision=1,
            )
        )
    package_id = uuid4()
    result = preparation_service.execute(
        actor=actor,
        command=_readiness_command(
            actor=actor,
            assignment_id=assignment_id,
            case_id=case_id,
            dce_version_id=dce_version_id,
            package_id=package_id,
            expected_revision=0,
        ),
        now=NOW,
    )
    assert result.result_code == "PREPARATION_READINESS_EVALUATED"
    assert (
        _latest_readiness(session_factory, actor.tenant_id, package_id).state
        == "READY_WITH_WARNINGS"
    )


def test_blocked_readiness_and_wrong_revision_cannot_generate(
    preparation_service: PreparationService, session_factory: sessionmaker[Session]
) -> None:
    actor, assignment_id, case_id, requirement_id = _seed(session_factory)
    actor = _enable_preparation_scope(session_factory, actor, assignment_id)
    dce_version_id = _dce_version_id(session_factory, actor.tenant_id)
    package_id = uuid4()
    preparation_service.execute(
        actor=actor,
        command=_readiness_command(
            actor=actor,
            assignment_id=assignment_id,
            case_id=case_id,
            dce_version_id=dce_version_id,
            package_id=package_id,
            expected_revision=0,
        ),
        now=NOW,
    )
    with pytest.raises(CommandExecutionError, match="PREPARATION_BLOCKED"):
        preparation_service.execute(
            actor=actor,
            command=GenerateTechnicalDocumentCommand(
                command_id=uuid4(),
                idempotency_key=uuid4(),
                correlation_id=uuid4(),
                package_id=package_id,
                document_id=uuid4(),
                expected_revision=1,
                readiness_revision=1,
                document_kind="TECHNICAL_RESPONSE",
            ),
            now=NOW,
        )

    with pytest.raises(PermissionError, match="NOT_FOUND_OR_FORBIDDEN"):
        preparation_service.execute(
            actor=replace(actor, membership_id=uuid4(), assigned_case_ids=frozenset()),
            command=_readiness_command(
                actor=actor,
                assignment_id=assignment_id,
                case_id=case_id,
                dce_version_id=dce_version_id,
                package_id=uuid4(),
                expected_revision=0,
            ),
            now=NOW,
        )


def _enable_preparation_scope(session_factory, actor, assignment_id):
    with session_factory.begin() as session:
        assignment = session.get(CaseAssignmentRecord, assignment_id)
        assignment.scope_actions_json = [
            Capability.WORK_TASK_READ.value,
            Capability.WORK_TASK_WRITE.value,
            Capability.PREPARATION_READINESS_WRITE.value,
            Capability.PREPARATION_DOCUMENT_WRITE.value,
        ]
    return replace(
        actor,
        assignment_scopes=(
            AssignmentScope(
                case_id=next(iter(actor.assigned_case_ids)),
                allowed_actions=frozenset(
                    {
                        Capability.WORK_TASK_READ.value,
                        Capability.WORK_TASK_WRITE.value,
                        Capability.PREPARATION_READINESS_WRITE.value,
                        Capability.PREPARATION_DOCUMENT_WRITE.value,
                    }
                ),
                allowed_classifications=frozenset({DataClassification.INTERNAL_OPERATIONAL}),
            ),
        ),
    )


def _dce_version_id(session_factory, tenant_id):
    from app.modules.dce.infrastructure.models.dce_version import DceVersionRecord

    with session_factory() as session:
        return session.scalar(
            sa.select(DceVersionRecord.id).where(DceVersionRecord.tenant_id == tenant_id)
        )


def _latest_readiness(session_factory, tenant_id, package_id):
    with session_factory() as session:
        return session.scalar(
            sa.select(PreparationReadinessRecord)
            .where(
                PreparationReadinessRecord.tenant_id == tenant_id,
                PreparationReadinessRecord.package_id == package_id,
            )
            .order_by(PreparationReadinessRecord.revision.desc())
            .limit(1)
        )
