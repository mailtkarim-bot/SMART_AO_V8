from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
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
    CaseCapabilityGapRecord,
    CaseCapabilityProposalRecord,
    CollaboratorTaskRecord,
    EnterpriseCapabilityProofLinkRecord,
    EnterpriseCapabilityRecord,
    EnterpriseDocumentRecord,
    GeneratedTechnicalDocumentRecord,
    PreparationPackageRecord,
    PreparationReadinessRecord,
)
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session, sessionmaker

from tests.application.test_collab_capability import _seed as _seed_capability
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


def _seed_capability_assessment(
    session_factory: sessionmaker[Session],
    *,
    proof_status: str | None = None,
    proof_expires_at=None,
):
    (
        actor,
        assignment_id,
        case_id,
        requirement_id,
        capability_id,
        version_id,
    ) = _seed_capability(session_factory)
    actor = _enable_preparation_scope(session_factory, actor, assignment_id)
    _confirm_requirement(session_factory, actor=actor, requirement_id=requirement_id)
    with session_factory.begin() as session:
        company_id = session.scalar(
            sa.select(EnterpriseCapabilityRecord.company_id).where(
                EnterpriseCapabilityRecord.tenant_id == actor.tenant_id,
                EnterpriseCapabilityRecord.id == capability_id,
            )
        )
        if proof_status is not None:
            document_id = uuid4()
            session.add(
                EnterpriseDocumentRecord(
                    id=document_id,
                    tenant_id=actor.tenant_id,
                    company_id=company_id,
                    document_kind="INSURANCE",
                    document_label="Attestation de test",
                    storage_object_id=uuid4(),
                    original_filename="preuve-test.pdf",
                    issued_at=NOW - timedelta(days=30),
                    expires_at=proof_expires_at,
                    sha256="a" * 64,
                    verification_status=proof_status,
                    registered_by_membership_id=actor.membership_id,
                    command_id=uuid4(),
                    idempotency_key=uuid4(),
                    correlation_id=uuid4(),
                )
            )
            session.flush()
            session.add(
                EnterpriseCapabilityProofLinkRecord(
                    id=uuid4(),
                    tenant_id=actor.tenant_id,
                    capability_version_id=version_id,
                    document_id=document_id,
                    relation_label="preuve de qualification",
                )
            )
        session.add(
            CaseCapabilityProposalRecord(
                id=uuid4(),
                tenant_id=actor.tenant_id,
                case_id=case_id,
                assignment_id=assignment_id,
                capability_id=capability_id,
                capability_version_id=version_id,
                requirement_id=requirement_id,
                task_id=None,
                state="PROPOSED",
                validity_state="CURRENT",
                justification="Proposition de preuve opérationnelle.",
                source_locator="RC p. 8",
                functional_key=f"proposal-{uuid4()}",
                proposed_by_membership_id=actor.membership_id,
                command_id=uuid4(),
                idempotency_key=uuid4(),
                correlation_id=uuid4(),
            )
        )
    return actor, assignment_id, case_id, requirement_id, version_id


@pytest.mark.db
@pytest.mark.security
@pytest.mark.parametrize(
    ("proof_status", "proof_expires_at", "expected_code"),
    [
        (None, None, "CAPABILITY_PROOF_MISSING"),
        ("VALIDATED", NOW - timedelta(days=1), "CAPABILITY_PROOF_EXPIRED"),
        ("REJECTED", NOW + timedelta(days=30), "CAPABILITY_PROOF_UNAUTHORIZED"),
    ],
)
def test_readiness_blocks_missing_expired_or_unauthorized_capability_proof(
    preparation_service: PreparationService,
    session_factory: sessionmaker[Session],
    proof_status: str | None,
    proof_expires_at,
    expected_code: str,
) -> None:
    actor, assignment_id, case_id, _, _ = _seed_capability_assessment(
        session_factory,
        proof_status=proof_status,
        proof_expires_at=proof_expires_at,
    )
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
    readiness = _latest_readiness(session_factory, actor.tenant_id, package_id)
    assert readiness.state == "BLOCKED"
    assert expected_code in readiness.blocker_codes_json
    assert set(readiness.blocker_codes_json) <= {
        "REQUIREMENT_UNCONFIRMED",
        "TASK_BLOCKED",
        "DCE_NOT_READY",
        "CAPABILITY_PROOF_MISSING",
        "CAPABILITY_PROOF_EXPIRED",
        "CAPABILITY_PROOF_UNAUTHORIZED",
        "CAPABILITY_GAP_BLOCKING",
    }


@pytest.mark.db
@pytest.mark.security
@pytest.mark.parametrize(
    ("severity", "expected_state", "expected_code"),
    [
        ("IMPORTANT", "READY_WITH_WARNINGS", "CAPABILITY_GAP_IMPORTANT"),
        ("BLOCKING", "BLOCKED", "CAPABILITY_GAP_BLOCKING"),
    ],
)
def test_readiness_consumes_capability_gap_severity(
    preparation_service: PreparationService,
    session_factory: sessionmaker[Session],
    severity: str,
    expected_state: str,
    expected_code: str,
) -> None:
    actor, assignment_id, case_id, requirement_id, capability_id, _ = _seed_capability(
        session_factory
    )
    actor = _enable_preparation_scope(session_factory, actor, assignment_id)
    _confirm_requirement(session_factory, actor=actor, requirement_id=requirement_id)
    with session_factory.begin() as session:
        session.add(
            CaseCapabilityGapRecord(
                id=uuid4(),
                tenant_id=actor.tenant_id,
                case_id=case_id,
                assignment_id=assignment_id,
                capability_id=capability_id,
                requirement_id=requirement_id,
                task_id=None,
                gap_kind="MISSING",
                severity=severity,
                reason="La preuve opérationnelle doit être complétée.",
                source_locator="RC p. 9",
                recommended_action="Demander une preuve au patron.",
                functional_key=f"gap-{uuid4()}",
                reported_by_membership_id=actor.membership_id,
                command_id=uuid4(),
                idempotency_key=uuid4(),
                correlation_id=uuid4(),
            )
        )
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
    readiness = _latest_readiness(session_factory, actor.tenant_id, package_id)
    assert readiness.state == expected_state
    code_collection = readiness.blocker_codes_json + readiness.warning_codes_json
    assert expected_code in code_collection


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
