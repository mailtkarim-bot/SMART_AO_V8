from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.dce.application.commands import (
    AcknowledgeAssignmentCommand,
    ReportAssignmentUnavailabilityCommand,
    RequestAssignmentClarificationCommand,
)
from app.modules.membership.application.assignment import (
    AssignmentInteractionService,
    assignment_handlers,
)
from app.platform.events.dispatcher import CommandDispatcher
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
    AssignmentClarificationRequestRecord,
    CaseAssignmentAcknowledgementRecord,
    CaseAssignmentRecord,
    CaseAssignmentUnavailabilityRecord,
    IdentityRecord,
    TenantMembershipRecord,
)
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

NOW = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)






@pytest.fixture(autouse=True)
def isolate_assignment_interactions(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


def _seed_assignment(session_factory: sessionmaker[Session]) -> tuple[ActorContext, UUID]:
    tenant_id = uuid4()
    identity_id = uuid4()
    membership_id = uuid4()
    case_id = uuid4()
    assignment_id = uuid4()
    actions = [
        Capability.ASSIGNMENT_ACKNOWLEDGE.value,
        Capability.ASSIGNMENT_CLARIFY.value,
        Capability.ASSIGNMENT_UNAVAILABILITY.value,
    ]
    with session_factory.begin() as session:
        session.add(
            TenantRecord(
                id=tenant_id,
                slug=f"tenant-{tenant_id.hex[:12]}",
                lifecycle="ACTIVE",
            )
        )
        session.add(
            IdentityRecord(
                id=identity_id,
                email_normalized=f"collab-{identity_id.hex[:12]}@example.test",
                lifecycle="ACTIVE",
                email_verified_at=NOW,
            )
        )
        session.add(
            TenantMembershipRecord(
                id=membership_id,
                tenant_id=tenant_id,
                identity_id=identity_id,
                role="COLLABORATEUR",
                state="ACTIVE",
                activated_at=NOW,
                revoked_at=None,
            )
        )
        session.flush()
        session.add(
            CaseRecord(
                id=case_id,
                tenant_id=tenant_id,
                aggregate_revision=1,
                functional_identity_hash="a" * 64,
                title="Affaire Assignment",
                object_description=None,
                business_origin="MANUAL",
                origin_reference_id=None,
                origin_rationale="Préparation du collaborateur",
                consultation_id=None,
                scope_kind="CUSTOM",
                scope_json={},
                scope_fingerprint="b" * 64,
                applicable_dce_version_id=None,
                lifecycle="ACTIVE",
                commercial_stage="ANALYSIS",
                decision_readiness="NOT_ASSESSED",
                dce_freshness="NO_DCE",
                responsibility_status="ASSIGNED",
                stopped_reason=None,
                stopped_at=None,
                archived_reason=None,
                archived_at=None,
                created_by_actor_id=None,
                updated_by_actor_id=None,
            )
        )
        session.flush()
        session.add(
            CaseAssignmentRecord(
                id=assignment_id,
                tenant_id=tenant_id,
                membership_id=membership_id,
                case_id=case_id,
                aggregate_revision=0,
                state="ACTIVE",
                scope_actions_json=actions,
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
                allowed_actions=frozenset(actions),
                allowed_classifications=frozenset({DataClassification.INTERNAL_OPERATIONAL}),
            ),
        ),
    )
    return actor, assignment_id


def _service(session_factory: sessionmaker[Session]) -> AssignmentInteractionService:
    return AssignmentInteractionService(
        session_factory=session_factory,
        dispatcher=CommandDispatcher(
            session_factory=session_factory,
            handlers=assignment_handlers(),
        ),
        policy=AuthorizationPolicy(),
    )


def _ack_command(
    assignment_id: UUID,
    *,
    expected_revision: int = 0,
) -> AcknowledgeAssignmentCommand:
    return AcknowledgeAssignmentCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        assignment_id=assignment_id,
        expected_revision=expected_revision,
        note="Affectation reçue.",
    )


@pytest.mark.db
@pytest.mark.security
def test_acknowledgement_is_authorized_replayed_and_append_only(session_factory) -> None:
    actor, assignment_id = _seed_assignment(session_factory)
    command = _ack_command(assignment_id)
    service = _service(session_factory)

    first = service.acknowledge(actor=actor, command=command, now=NOW)
    replay = service.acknowledge(actor=actor, command=command, now=NOW)

    assert first.result_code == "ASSIGNMENT_ACKNOWLEDGED"
    assert replay.replayed is True
    with session_factory() as session:
        assignment = session.get(CaseAssignmentRecord, assignment_id)
        acknowledgements = list(session.scalars(sa.select(CaseAssignmentAcknowledgementRecord)))
        events = list(session.scalars(sa.select(DomainEventRecord)))
        outbox = list(session.scalars(sa.select(OutboxMessageRecord)))
    assert assignment is not None
    assert assignment.aggregate_revision == 1
    assert len(acknowledgements) == 1
    assert acknowledgements[0].assignment_revision == 1
    assert len(events) == 1
    assert len(outbox) == 1

    with pytest.raises(DBAPIError), session_factory.begin() as session:
        stored = session.get(CaseAssignmentAcknowledgementRecord, acknowledgements[0].id)
        assert stored is not None
        stored.note = "mutation interdite"


@pytest.mark.db
@pytest.mark.security
def test_unavailability_increments_assignment_revision_without_changing_state(
    session_factory,
) -> None:
    actor, assignment_id = _seed_assignment(session_factory)
    command = ReportAssignmentUnavailabilityCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        assignment_id=assignment_id,
        expected_revision=0,
        reason_kind="CAPACITY_CONFLICT",
        reason="Conflit de capacité sur la période.",
        unavailable_from=NOW + timedelta(days=1),
        unavailable_until=NOW + timedelta(days=3),
        known_deadline_impact=True,
        impact_note="Le patron doit vérifier la date de remise.",
    )

    result = _service(session_factory).report_unavailability(
        actor=actor,
        command=command,
        now=NOW,
    )

    assert result.result_code == "ASSIGNMENT_UNAVAILABILITY_REPORTED"
    with session_factory() as session:
        assignment = session.get(CaseAssignmentRecord, assignment_id)
        rows = list(session.scalars(sa.select(CaseAssignmentUnavailabilityRecord)))
    assert assignment is not None
    assert assignment.aggregate_revision == 1
    assert assignment.state == "ACTIVE"
    assert len(rows) == 1
    assert rows[0].known_deadline_impact is True


@pytest.mark.db
@pytest.mark.security
def test_clarification_is_functionally_idempotent_without_assignment_revision_change(
    session_factory,
) -> None:
    actor, assignment_id = _seed_assignment(session_factory)
    first_command = RequestAssignmentClarificationCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        assignment_id=assignment_id,
        expected_revision=0,
        clarification_kind="SCOPE",
        subject="Périmètre de la Case",
        question="Quel lot doit être préparé en priorité ?",
        requested_scope="Lot structure",
        priority="HIGH",
    )
    second_command = first_command.model_copy(
        update={"command_id": uuid4(), "idempotency_key": uuid4()}
    )
    service = _service(session_factory)

    first = service.clarify(actor=actor, command=first_command, now=NOW)
    second = service.clarify(actor=actor, command=second_command, now=NOW)

    assert first.result_code == "ASSIGNMENT_CLARIFICATION_REQUESTED"
    assert second.result_code == first.result_code
    with session_factory() as session:
        assignment = session.get(CaseAssignmentRecord, assignment_id)
        requests = list(session.scalars(sa.select(AssignmentClarificationRequestRecord)))
        events = list(session.scalars(sa.select(DomainEventRecord)))
    assert assignment is not None
    assert assignment.aggregate_revision == 0
    assert len(requests) == 1
    assert len(events) == 1


@pytest.mark.db
@pytest.mark.security
def test_assignment_scope_or_tenant_mismatch_is_denied_without_durable_write(
    session_factory,
) -> None:
    actor, assignment_id = _seed_assignment(session_factory)
    denied_actor = replace(
        actor,
        assignment_scopes=(
            AssignmentScope(
                case_id=next(iter(actor.assigned_case_ids)),
                allowed_actions=frozenset({Capability.CASE_DCE_READ}),
                allowed_classifications=frozenset({DataClassification.INTERNAL_OPERATIONAL}),
            ),
        ),
    )

    with pytest.raises(PermissionError, match="AUTHORIZATION_DENIED"):
        _service(session_factory).acknowledge(
            actor=denied_actor,
            command=_ack_command(assignment_id),
            now=NOW,
        )

    foreign_command = _ack_command(uuid4())
    with pytest.raises(PermissionError, match="NOT_FOUND_OR_FORBIDDEN"):
        _service(session_factory).acknowledge(
            actor=actor,
            command=foreign_command,
            now=NOW,
        )
    with session_factory() as session:
        assert session.scalar(sa.select(CaseAssignmentAcknowledgementRecord)) is None


def test_unavailability_command_rejects_invalid_period_and_missing_impact_note() -> None:
    assignment_id = uuid4()
    with pytest.raises(ValueError):
        ReportAssignmentUnavailabilityCommand(
            command_id=uuid4(),
            idempotency_key=uuid4(),
            assignment_id=assignment_id,
            expected_revision=0,
            reason_kind="LEAVE",
            reason="Congé",
            unavailable_from=NOW,
            unavailable_until=NOW,
        )
    with pytest.raises(ValueError):
        ReportAssignmentUnavailabilityCommand(
            command_id=uuid4(),
            idempotency_key=uuid4(),
            assignment_id=assignment_id,
            expected_revision=0,
            reason_kind="LEAVE",
            reason="Congé",
            unavailable_from=NOW,
            known_deadline_impact=True,
        )
