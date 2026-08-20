from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.dce.infrastructure.models.consultation import ConsultationRecord
from app.modules.dce.infrastructure.models.dce_rc_analysis import (
    DceRcAnalysisRunRecord,
    DceRcRequirementObservationRecord,
)
from app.modules.dce.infrastructure.models.dce_requirements import (
    DceRequirementMaterializationRunRecord,
    DceRequirementRecord,
)
from app.modules.dce.infrastructure.models.dce_version import DceVersionRecord
from app.modules.membership.application.collab_work_task import (
    CollaboratorWorkTaskHandler,
    CollaboratorWorkTaskService,
    collaborator_work_task_handlers,
)
from app.modules.membership.application.collab_work_task_commands import (
    ClaimTaskCommand,
    CompleteTaskCommand,
    CreateTaskFromRequirementCommand,
    RecordTaskResultCommand,
)
from app.platform.events.dispatcher import (
    CommandContext,
    CommandDispatcher,
    CommandExecutionError,
)
from app.platform.persistence.models import DomainEventRecord, OutboxMessageRecord, TenantRecord
from app.platform.security.authorization import AuthorizationPolicy
from app.platform.security.capabilities import Capability, capabilities_for
from app.platform.security.context import (
    ActorContext,
    ActorKind,
    AssignmentScope,
    DataClassification,
    MembershipState,
)
from app.platform.security.models import (
    CaseAssignmentRecord,
    CollaboratorTaskRecord,
    CollaboratorTaskResultRecord,
    IdentityRecord,
    TenantMembershipRecord,
)

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)






def _seed(session_factory) -> tuple[ActorContext, UUID, UUID, UUID]:
    tenant_id, identity_id, membership_id = uuid4(), uuid4(), uuid4()
    consultation_id, dce_version_id = uuid4(), uuid4()
    analysis_id, observation_id, run_id, requirement_id = uuid4(), uuid4(), uuid4(), uuid4()
    case_id, assignment_id = uuid4(), uuid4()
    with session_factory.begin() as session:
        session.add_all(
            [
                TenantRecord(id=tenant_id, slug=f"tenant-{tenant_id.hex[:12]}", lifecycle="ACTIVE"),
                IdentityRecord(
                    id=identity_id,
                    email_normalized=f"collab-{identity_id.hex[:12]}@example.test",
                    lifecycle="ACTIVE",
                    email_verified_at=NOW,
                ),
                TenantMembershipRecord(
                    id=membership_id,
                    tenant_id=tenant_id,
                    identity_id=identity_id,
                    role="COLLABORATEUR",
                    state="ACTIVE",
                    activated_at=NOW,
                    revoked_at=None,
                ),
            ]
        )
        session.flush()
        session.add(
            ConsultationRecord(
                id=consultation_id,
                tenant_id=tenant_id,
                aggregate_revision=0,
                functional_identity_hash="a" * 64,
                buyer_legal_name="Acheteur test",
                buyer_normalized_id=None,
                external_reference=None,
                object_label="Objet test",
                location_label=None,
                source_channel="MANUAL",
                source_reference=None,
                source_received_at=NOW,
                lifecycle="OPEN",
                freshness="CURRENT",
                metadata_history_json=[],
                created_by_actor_id=identity_id,
                updated_by_actor_id=identity_id,
            )
        )
        session.add(
            DceVersionRecord(
                id=dce_version_id,
                tenant_id=tenant_id,
                aggregate_revision=0,
                consultation_id=consultation_id,
                corpus_hash="b" * 64,
                predecessor_dce_version_id=None,
                provenance_channel="TEST",
                provenance_reference="test",
                provenance_url=None,
                source_received_at=NOW,
                lifecycle="ADMITTED",
                integrity="VERIFIED",
                classification_readiness="CLASSIFIED",
                analysis_readiness="READY_FOR_ANALYSIS",
                withdrawal_source=None,
                withdrawal_reason=None,
                superseded_at=None,
                withdrawn_at=None,
                created_by_actor_id=identity_id,
                updated_by_actor_id=identity_id,
            )
        )
        session.flush()
        session.add_all(
            [
                DceRcAnalysisRunRecord(
                    id=analysis_id,
                    tenant_id=tenant_id,
                    dce_version_id=dce_version_id,
                    input_manifest_sha256="c" * 64,
                    analyzer_id="test",
                    analyzer_version="1",
                    status="COMPLETED",
                    source_fragment_count=1,
                    source_char_count=1,
                    failure_code=None,
                ),
                DceRcRequirementObservationRecord(
                    id=observation_id,
                    tenant_id=tenant_id,
                    analysis_id=analysis_id,
                    dce_version_id=dce_version_id,
                    requirement_kind="RC_DOCUMENT_CANDIDATURE",
                    directive="REQUIRED_SIGNAL",
                    rule_id="TEST_RULE",
                    rule_version="1",
                    fragment_id=uuid4(),
                    start_byte_offset=0,
                    end_byte_offset=1,
                    excerpt="X",
                ),
            ]
        )
        session.flush()
        session.add(
            DceRequirementMaterializationRunRecord(
                id=run_id,
                tenant_id=tenant_id,
                dce_version_id=dce_version_id,
                dce_rc_analysis_id=analysis_id,
                input_manifest_sha256="d" * 64,
                materializer_id="test",
                materializer_version="1",
                status="COMPLETED",
                source_observation_count=1,
                failure_code=None,
            )
        )
        session.flush()
        session.add(
            DceRequirementRecord(
                id=requirement_id,
                tenant_id=tenant_id,
                requirements_run_id=run_id,
                dce_version_id=dce_version_id,
                source_observation_id=observation_id,
                requirement_type="CANDIDATURE_DOCUMENT",
                directive_signal="REQUIRED_SIGNAL",
                confirmation_status="PENDING_HUMAN_CONFIRMATION",
                uncertainty_status="SOURCE_SIGNAL_ONLY",
            )
        )
        session.add(
            CaseRecord(
                id=case_id,
                tenant_id=tenant_id,
                aggregate_revision=1,
                functional_identity_hash="e" * 64,
                title="Affaire Task",
                object_description=None,
                business_origin="OPPORTUNITY",
                origin_reference_id=None,
                origin_rationale=None,
                consultation_id=consultation_id,
                scope_kind="CUSTOM",
                scope_json={},
                scope_fingerprint="f" * 64,
                applicable_dce_version_id=dce_version_id,
                lifecycle="ACTIVE",
                commercial_stage="ANALYSIS",
                decision_readiness="NOT_ASSESSED",
                dce_freshness="CURRENT",
                responsibility_status="ASSIGNED",
                stopped_reason=None,
                stopped_at=None,
                archived_reason=None,
                archived_at=None,
                created_by_actor_id=identity_id,
                updated_by_actor_id=identity_id,
            )
        )
        session.add(
            CaseAssignmentRecord(
                id=assignment_id,
                tenant_id=tenant_id,
                membership_id=membership_id,
                case_id=case_id,
                aggregate_revision=0,
                state="ACTIVE",
                scope_actions_json=[
                    Capability.WORK_TASK_READ.value,
                    Capability.WORK_TASK_WRITE.value,
                ],
                scope_classifications_json=[DataClassification.INTERNAL_OPERATIONAL.value],
                granted_by_membership_id=membership_id,
                granted_at=NOW,
                starts_at=NOW,
                ends_at=None,
                ended_at=None,
            )
        )
    actor = ActorContext(
        actor_id=identity_id,
        identity_id=identity_id,
        tenant_id=tenant_id,
        membership_id=membership_id,
        actor_kind=ActorKind.COLLABORATEUR,
        membership_state=MembershipState.ACTIVE,
        capabilities=capabilities_for(ActorKind.COLLABORATEUR),
        assigned_case_ids=frozenset({case_id}),
        session_id=uuid4(),
        authenticated_at=NOW,
        mfa_verified_at=NOW,
        correlation_id=uuid4(),
        assignment_scopes=(
            AssignmentScope(
                case_id=case_id,
                allowed_actions=frozenset(
                    {Capability.WORK_TASK_READ.value, Capability.WORK_TASK_WRITE.value}
                ),
                allowed_classifications=frozenset({DataClassification.INTERNAL_OPERATIONAL}),
            ),
        ),
    )
    return actor, assignment_id, case_id, requirement_id


def _service(factory, *, policy=None):
    dispatcher = CommandDispatcher(
        session_factory=factory, handlers=collaborator_work_task_handlers()
    )
    return CollaboratorWorkTaskService(
        session_factory=factory,
        dispatcher=dispatcher,
        policy=policy or AuthorizationPolicy(),
    )


class _DenyPolicy:
    def authorize(self, **kwargs):
        return SimpleNamespace(allowed=False, code="ASSIGNMENT_SCOPE_FORBIDDEN")


def _create(
    assignment_id: UUID, case_id: UUID, requirement_id: UUID
) -> CreateTaskFromRequirementCommand:
    return CreateTaskFromRequirementCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        task_id=uuid4(),
        assignment_id=assignment_id,
        case_id=case_id,
        requirement_id=requirement_id,
        task_kind="REQUIREMENT_CHECK",
        title="Vérifier la pièce de candidature",
        objective="Confirmer la source et signaler tout manque.",
    )


@pytest.mark.db
@pytest.mark.security
def test_task_lifecycle_is_idempotent_and_append_only(session_factory) -> None:
    actor, assignment_id, case_id, requirement_id = _seed(session_factory)
    service = _service(session_factory)
    create = _create(assignment_id, case_id, requirement_id)

    first = service.execute(actor=actor, command=create, now=NOW)
    replay = service.execute(actor=actor, command=create, now=NOW)
    task_id = UUID(first.aggregate_refs[0]["aggregate_id"])
    claim = service.execute(
        actor=actor,
        command=ClaimTaskCommand(
            command_id=uuid4(), idempotency_key=uuid4(), task_id=task_id, expected_revision=0
        ),
        now=NOW,
    )
    result = service.execute(
        actor=actor,
        command=RecordTaskResultCommand(
            command_id=uuid4(),
            idempotency_key=uuid4(),
            task_id=task_id,
            expected_revision=1,
            result_text="Pièce requise confirmée dans RC:p8.",
            source_locator="RC:p8",
            outcome="RECORDED",
        ),
        now=NOW,
    )
    completed = service.execute(
        actor=actor,
        command=CompleteTaskCommand(
            command_id=uuid4(), idempotency_key=uuid4(), task_id=task_id, expected_revision=2
        ),
        now=NOW,
    )

    assert first.result_code == "TASK_CREATED"
    assert replay.replayed is True
    assert claim.result_code == "TASK_CLAIMED"
    assert result.result_code == "TASK_UPDATED"
    assert completed.result_code == "TASK_COMPLETED"
    with session_factory() as session:
        task = session.get(CollaboratorTaskRecord, task_id)
        assert task is not None and task.state == "COMPLETED" and task.aggregate_revision == 3
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(CollaboratorTaskResultRecord))
            == 1
        )
        events = session.scalars(
            sa.select(DomainEventRecord).where(DomainEventRecord.aggregate_id == task_id)
        ).all()
        assert [event.event_type for event in events] == [
            "TaskCreatedFromRequirement",
            "TaskClaimed",
            "TaskResultRecorded",
            "TaskCompleted",
        ]
        payload = str([event.payload_json for event in events])
        assert "price" not in payload.lower()
        assert "margin" not in payload.lower()
        assert session.scalar(sa.select(sa.func.count()).select_from(OutboxMessageRecord)) == 4


@pytest.mark.db
@pytest.mark.security
def test_task_refuses_revision_conflict_and_completion_without_result(session_factory) -> None:
    actor, assignment_id, case_id, requirement_id = _seed(session_factory)
    service = _service(session_factory)
    create = _create(assignment_id, case_id, requirement_id)
    task_id = UUID(
        service.execute(actor=actor, command=create, now=NOW).aggregate_refs[0]["aggregate_id"]
    )
    service.execute(
        actor=actor,
        command=ClaimTaskCommand(
            command_id=uuid4(), idempotency_key=uuid4(), task_id=task_id, expected_revision=0
        ),
        now=NOW,
    )
    with pytest.raises(CommandExecutionError, match="VERSION_CONFLICT"):
        service.execute(
            actor=actor,
            command=ClaimTaskCommand(
                command_id=uuid4(), idempotency_key=uuid4(), task_id=task_id, expected_revision=0
            ),
            now=NOW,
        )
    with pytest.raises(CommandExecutionError, match="EVIDENCE_OF_COMPLETION_REQUIRED"):
        service.execute(
            actor=actor,
            command=CompleteTaskCommand(
                command_id=uuid4(), idempotency_key=uuid4(), task_id=task_id, expected_revision=1
            ),
            now=NOW,
        )


@pytest.mark.db
@pytest.mark.security
def test_task_refuses_foreign_requirement_and_wrong_membership(session_factory) -> None:
    actor, assignment_id, case_id, requirement_id = _seed(session_factory)
    service = _service(session_factory)
    foreign_requirement_id = uuid4()
    with pytest.raises(CommandExecutionError, match="NOT_FOUND_OR_FORBIDDEN"):
        service.execute(
            actor=actor,
            command=_create(assignment_id, case_id, foreign_requirement_id),
            now=NOW,
        )

    wrong_actor = replace(actor, membership_id=uuid4())
    with pytest.raises(PermissionError, match="NOT_FOUND_OR_FORBIDDEN"):
        service.execute(
            actor=wrong_actor, command=_create(assignment_id, case_id, requirement_id), now=NOW
        )


@pytest.mark.db
@pytest.mark.security
def test_task_service_rejects_non_collaborator_and_missing_membership(session_factory) -> None:
    actor, assignment_id, case_id, requirement_id = _seed(session_factory)
    service = _service(session_factory)
    patron = replace(actor, actor_kind=ActorKind.PATRON_ADMIN)
    without_membership = replace(actor, membership_id=None)

    with pytest.raises(PermissionError, match="COLLABORATOR_REQUIRED"):
        service.execute(
            actor=patron, command=_create(assignment_id, case_id, requirement_id), now=NOW
        )
    with pytest.raises(PermissionError, match="MEMBERSHIP_REQUIRED"):
        service.execute(
            actor=without_membership,
            command=_create(assignment_id, case_id, requirement_id),
            now=NOW,
        )


@pytest.mark.db
@pytest.mark.security
def test_task_service_rejects_policy_denial_and_missing_assignment(session_factory) -> None:
    actor, assignment_id, case_id, requirement_id = _seed(session_factory)
    denied = _service(session_factory, policy=_DenyPolicy())
    with pytest.raises(PermissionError, match="ASSIGNMENT_SCOPE_FORBIDDEN"):
        denied.execute(
            actor=actor, command=_create(assignment_id, case_id, requirement_id), now=NOW
        )

    service = _service(session_factory)
    with pytest.raises(PermissionError, match="NOT_FOUND_OR_FORBIDDEN"):
        service.list_for_case(actor=actor, case_id=uuid4(), now=NOW)


@pytest.mark.db
@pytest.mark.security
def test_task_list_rejects_non_collaborator_and_policy_denial(session_factory) -> None:
    actor, assignment_id, case_id, requirement_id = _seed(session_factory)
    service = _service(session_factory)
    patron = replace(actor, actor_kind=ActorKind.PATRON_ADMIN)
    with pytest.raises(PermissionError, match="COLLABORATOR_REQUIRED"):
        service.list_for_case(actor=patron, case_id=case_id, now=NOW)

    with pytest.raises(PermissionError, match="ASSIGNMENT_SCOPE_FORBIDDEN"):
        _service(session_factory, policy=_DenyPolicy()).list_for_case(
            actor=actor, case_id=case_id, now=NOW
        )


@pytest.mark.db
@pytest.mark.security
def test_task_handler_rejects_invalid_context_and_unsupported_command(session_factory) -> None:
    actor, assignment_id, case_id, requirement_id = _seed(session_factory)
    service = _service(session_factory)
    task_id = UUID(
        service.execute(
            actor=actor, command=_create(assignment_id, case_id, requirement_id), now=NOW
        ).aggregate_refs[0]["aggregate_id"]
    )
    handler = CollaboratorWorkTaskHandler()
    with session_factory.begin() as session, pytest.raises(
        CommandExecutionError, match="COLLABORATOR_REQUIRED"
    ):
            handler.execute(
                session=session,
                command=ClaimTaskCommand(
                    command_id=uuid4(), idempotency_key=uuid4(), task_id=task_id,
                    expected_revision=0,
                ),
                context=CommandContext(
                    tenant_id=actor.tenant_id, actor_id=actor.actor_id,
                    actor_kind=ActorKind.PATRON_ADMIN.value, received_at=NOW,
                    membership_id=actor.membership_id,
                ),
            )

    with session_factory.begin() as session, pytest.raises(
        CommandExecutionError, match="unsupported task command"
    ):
            handler.execute(
                session=session,
                command=SimpleNamespace(
                    command_type="UnknownTaskCommand", task_id=task_id,
                    expected_revision=0,
                ),
                context=CommandContext(
                    tenant_id=actor.tenant_id, actor_id=actor.actor_id,
                    actor_kind=ActorKind.COLLABORATEUR.value, received_at=NOW,
                    membership_id=actor.membership_id, case_id=case_id,
                ),
            )


@pytest.mark.db
@pytest.mark.security
def test_task_handler_returns_existing_task_without_duplicate_event(session_factory) -> None:
    actor, assignment_id, case_id, requirement_id = _seed(session_factory)
    service = _service(session_factory)
    command = _create(assignment_id, case_id, requirement_id)
    service.execute(actor=actor, command=command, now=NOW)
    handler = CollaboratorWorkTaskHandler()
    with session_factory.begin() as session:
        outcome = handler.execute(
            session=session,
            command=command,
            context=CommandContext(
                tenant_id=actor.tenant_id, actor_id=actor.actor_id,
                actor_kind=ActorKind.COLLABORATEUR.value, received_at=NOW,
                membership_id=actor.membership_id, case_id=case_id,
            ),
        )
    assert outcome.result_code == "TASK_CREATED"
    assert outcome.events == ()


@pytest.mark.db
@pytest.mark.security
def test_task_handler_rejects_inactive_scope_classification_and_case_context(
    session_factory,
) -> None:
    actor, assignment_id, case_id, requirement_id = _seed(session_factory)
    service = _service(session_factory)
    command = _create(assignment_id, case_id, requirement_id)
    task_id = UUID(
        service.execute(actor=actor, command=command, now=NOW).aggregate_refs[0]["aggregate_id"]
    )
    handler = CollaboratorWorkTaskHandler()
    base_context = CommandContext(
        tenant_id=actor.tenant_id, actor_id=actor.actor_id,
        actor_kind=ActorKind.COLLABORATEUR.value, received_at=NOW,
        membership_id=actor.membership_id, case_id=case_id,
    )

    with session_factory.begin() as session:
        assignment = session.get(CaseAssignmentRecord, assignment_id)
        assert assignment is not None
        assignment.state = "SUSPENDED"
    with session_factory.begin() as session, pytest.raises(
        CommandExecutionError, match="ASSIGNMENT_INACTIVE"
    ):
            handler.execute(
                session=session,
                command=ClaimTaskCommand(
                    command_id=uuid4(), idempotency_key=uuid4(), task_id=task_id,
                    expected_revision=0,
                ),
                context=base_context,
            )

    with session_factory.begin() as session:
        assignment = session.get(CaseAssignmentRecord, assignment_id)
        assert assignment is not None
        assignment.state = "ACTIVE"
        assignment.scope_actions_json = [Capability.CASE_DCE_READ.value]
    with session_factory.begin() as session, pytest.raises(
        CommandExecutionError, match="ASSIGNMENT_SCOPE_FORBIDDEN"
    ):
            handler.execute(
                session=session,
                command=ClaimTaskCommand(
                    command_id=uuid4(), idempotency_key=uuid4(), task_id=task_id,
                    expected_revision=0,
                ),
                context=base_context,
            )

    with session_factory.begin() as session:
        assignment = session.get(CaseAssignmentRecord, assignment_id)
        assert assignment is not None
        assignment.scope_actions_json = [Capability.WORK_TASK_WRITE.value]
        assignment.scope_classifications_json = [DataClassification.PUBLIC_TENDER.value]
    with session_factory.begin() as session, pytest.raises(
        CommandExecutionError, match="ASSIGNMENT_CLASSIFICATION_FORBIDDEN"
    ):
            handler.execute(
                session=session,
                command=ClaimTaskCommand(
                    command_id=uuid4(), idempotency_key=uuid4(), task_id=task_id,
                    expected_revision=0,
                ),
                context=base_context,
            )

    with session_factory.begin() as session:
        assignment = session.get(CaseAssignmentRecord, assignment_id)
        assert assignment is not None
        assignment.scope_classifications_json = [DataClassification.INTERNAL_OPERATIONAL.value]
    with session_factory.begin() as session, pytest.raises(
        CommandExecutionError, match="CASE_CONTEXT_MISMATCH"
    ):
            handler.execute(
                session=session,
                command=ClaimTaskCommand(
                    command_id=uuid4(), idempotency_key=uuid4(), task_id=task_id,
                    expected_revision=0,
                ),
                context=replace(base_context, case_id=uuid4()),
            )


@pytest.mark.db
@pytest.mark.security
def test_task_handler_rejects_non_claimable_result_and_non_completable_states(
    session_factory,
) -> None:
    actor, assignment_id, case_id, requirement_id = _seed(session_factory)
    service = _service(session_factory)
    task_id = UUID(
        service.execute(
            actor=actor, command=_create(assignment_id, case_id, requirement_id), now=NOW
        ).aggregate_refs[0]["aggregate_id"]
    )
    service.execute(
        actor=actor,
        command=ClaimTaskCommand(
            command_id=uuid4(), idempotency_key=uuid4(), task_id=task_id, expected_revision=0
        ),
        now=NOW,
    )
    with pytest.raises(CommandExecutionError, match="TASK_NOT_CLAIMABLE"):
        service.execute(
            actor=actor,
            command=ClaimTaskCommand(
                command_id=uuid4(), idempotency_key=uuid4(), task_id=task_id, expected_revision=1
            ),
            now=NOW,
        )
    service.execute(
        actor=actor,
        command=RecordTaskResultCommand(
            command_id=uuid4(), idempotency_key=uuid4(), task_id=task_id,
            expected_revision=1, result_text="Résultat", source_locator="RC:p1",
            outcome="RECORDED",
        ),
        now=NOW,
    )
    service.execute(
        actor=actor,
        command=CompleteTaskCommand(
            command_id=uuid4(), idempotency_key=uuid4(), task_id=task_id, expected_revision=2
        ),
        now=NOW,
    )
    with pytest.raises(CommandExecutionError, match="TASK_NOT_ACTIVE"):
        service.execute(
            actor=actor,
            command=RecordTaskResultCommand(
                command_id=uuid4(), idempotency_key=uuid4(), task_id=task_id,
                expected_revision=3, result_text="Après clôture", source_locator="RC:p2",
                outcome="RECORDED",
            ),
            now=NOW,
        )
    with pytest.raises(CommandExecutionError, match="TASK_NOT_COMPLETABLE"):
        service.execute(
            actor=actor,
            command=CompleteTaskCommand(
                command_id=uuid4(), idempotency_key=uuid4(), task_id=task_id, expected_revision=3
            ),
            now=NOW,
        )
