"""First patron-owned transactional boundary for controlled Case assignment creation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.dce.application.commands import CreateCaseAssignmentCommand
from app.platform.events.dispatcher import (
    CommandContext,
    CommandDispatcher,
    CommandExecutionError,
    DispatchResult,
    HandlerOutcome,
    PendingDomainEvent,
)
from app.platform.security.audit import (
    AuditEventType,
    AuditOutcome,
    AuditSeverity,
    SecurityAuditEntry,
    SecurityAuditWriter,
)
from app.platform.security.authorization import (
    AuthorizationPolicyPort,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext, ActorKind, DataClassification
from app.platform.security.models import (
    CaseAssignmentChangeEventRecord,
    CaseAssignmentRecord,
    TenantMembershipRecord,
)


class PatronAssignmentManagementService:
    """Resolve patron authority before dispatching an assignment creation."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        dispatcher: CommandDispatcher,
        policy: AuthorizationPolicyPort,
        audit_writer: SecurityAuditWriter | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._dispatcher = dispatcher
        self._policy = policy
        self._audit_writer = audit_writer or SecurityAuditWriter()

    def create(
        self,
        *,
        actor: ActorContext,
        command: CreateCaseAssignmentCommand,
        now: datetime,
    ) -> DispatchResult:
        if actor.actor_kind is not ActorKind.PATRON_ADMIN:
            self._record_manual_denial(
                actor=actor,
                command=command,
                now=now,
                reason_code="ASSIGNMENT_PATRON_REQUIRED",
            )
            raise PermissionError("ASSIGNMENT_PATRON_REQUIRED")
        if actor.membership_id is None:
            self._record_manual_denial(
                actor=actor,
                command=command,
                now=now,
                reason_code="ASSIGNMENT_MEMBERSHIP_REQUIRED",
            )
            raise PermissionError("ASSIGNMENT_MEMBERSHIP_REQUIRED")

        case = self._resolve_case(tenant_id=actor.tenant_id, case_id=command.case_id)
        if case is None:
            self._record_manual_denial(
                actor=actor,
                command=command,
                now=now,
                reason_code="NOT_FOUND_OR_FORBIDDEN",
            )
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.ASSIGNMENT_MANAGE,
                resource=AuthorizationResource(
                    resource_type="CASE",
                    resource_id=case.id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                    case_id=case.id,
                ),
                evaluated_at=now,
            ),
        )
        if not decision.allowed:
            raise PermissionError(decision.code)

        return self._dispatcher.dispatch(
            command=command,
            context=CommandContext(
                tenant_id=actor.tenant_id,
                actor_id=actor.actor_id,
                actor_kind=actor.actor_kind.value,
                received_at=now,
                identity_id=actor.identity_id,
                membership_id=actor.membership_id,
                session_id=actor.session_id,
                case_id=case.id,
                correlation_id=actor.correlation_id,
            ),
        )

    def _record_manual_denial(
        self,
        *,
        actor: ActorContext,
        command: CreateCaseAssignmentCommand,
        now: datetime,
        reason_code: str,
    ) -> None:
        with self._session_factory.begin() as session:
            self._audit_writer.record(
                session=session,
                entry=SecurityAuditEntry(
                    occurred_at=now,
                    tenant_id=actor.tenant_id,
                    actor_id=actor.actor_id,
                    identity_id=actor.identity_id,
                    session_id=actor.session_id,
                    actor_kind=actor.actor_kind.value,
                    auth_strength=None,
                    event_type=AuditEventType.AUTHZ_DENIED,
                    outcome=AuditOutcome.DENIED,
                    severity=AuditSeverity.WARNING,
                    action=str(Capability.ASSIGNMENT_MANAGE),
                    resource_type="CASE",
                    resource_id=command.case_id,
                    case_id=command.case_id,
                    correlation_id=command.correlation_id,
                    command_id=command.command_id,
                    request_id=None,
                    source_ip_hash=None,
                    user_agent_family=None,
                    reason_code=reason_code,
                    metadata={"channel": "service"},
                ),
            )

    def _resolve_case(self, *, tenant_id: UUID, case_id: UUID) -> CaseRecord | None:
        with self._session_factory() as session:
            return session.scalar(
                sa.select(CaseRecord).where(
                    CaseRecord.tenant_id == tenant_id,
                    CaseRecord.id == case_id,
                )
            )


class PatronAssignmentManagementHandler:
    """Own the atomic creation of one patron-controlled Case assignment."""

    def execute(
        self,
        *,
        session: Session,
        command: CreateCaseAssignmentCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        if context.actor_kind != ActorKind.PATRON_ADMIN.value:
            raise CommandExecutionError("ASSIGNMENT_PATRON_REQUIRED")
        if context.membership_id is None:
            raise CommandExecutionError("ASSIGNMENT_MEMBERSHIP_CONTEXT_REQUIRED")
        if command.starts_at > context.received_at:
            raise CommandExecutionError("ASSIGNMENT_STARTS_IN_FUTURE")

        case = session.scalar(
            sa.select(CaseRecord)
            .where(
                CaseRecord.tenant_id == context.tenant_id,
                CaseRecord.id == command.case_id,
            )
            .with_for_update()
        )
        if case is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if case.lifecycle != "ACTIVE":
            raise CommandExecutionError("CASE_INACTIVE")
        if case.aggregate_revision != command.expected_case_revision:
            raise CommandExecutionError("CASE_VERSION_CONFLICT")
        if context.case_id is not None and context.case_id != case.id:
            raise CommandExecutionError("CASE_CONTEXT_MISMATCH")

        target_membership = session.scalar(
            sa.select(TenantMembershipRecord)
            .where(
                TenantMembershipRecord.tenant_id == context.tenant_id,
                TenantMembershipRecord.id == command.target_membership_id,
            )
            .with_for_update()
        )
        if target_membership is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if (
            target_membership.role != ActorKind.COLLABORATEUR.value
            or target_membership.state != "ACTIVE"
        ):
            raise CommandExecutionError("ASSIGNMENT_TARGET_NOT_COLLABORATOR")

        existing_open_assignment = session.scalar(
            sa.select(CaseAssignmentRecord)
            .where(
                CaseAssignmentRecord.tenant_id == context.tenant_id,
                CaseAssignmentRecord.membership_id == target_membership.id,
                CaseAssignmentRecord.case_id == case.id,
                CaseAssignmentRecord.state.in_(("ACTIVE", "SUSPENDED")),
            )
            .with_for_update()
        )
        if existing_open_assignment is not None:
            raise CommandExecutionError("ASSIGNMENT_ALREADY_OPEN")

        assignment = CaseAssignmentRecord(
            id=command.assignment_id,
            tenant_id=context.tenant_id,
            membership_id=target_membership.id,
            case_id=case.id,
            aggregate_revision=0,
            state="ACTIVE",
            scope_actions_json=list(command.scope_actions),
            scope_classifications_json=list(command.scope_classifications),
            granted_by_membership_id=context.membership_id,
            granted_at=context.received_at,
            starts_at=command.starts_at,
            ends_at=command.ends_at,
            ended_at=None,
        )
        session.add(assignment)
        session.flush()
        change_event = CaseAssignmentChangeEventRecord(
            id=uuid4(),
            tenant_id=context.tenant_id,
            assignment_id=assignment.id,
            case_id=case.id,
            target_membership_id=target_membership.id,
            author_membership_id=context.membership_id,
            event_type="ASSIGNMENT_CREATED",
            previous_revision=None,
            resulting_revision=0,
            previous_state=None,
            resulting_state="ACTIVE",
            reason_code=None,
            previous_scope_actions_json=None,
            previous_scope_classifications_json=None,
            resulting_scope_actions_json=list(command.scope_actions),
            resulting_scope_classifications_json=list(command.scope_classifications),
            command_id=command.command_id,
            correlation_id=command.correlation_id,
        )
        session.add(change_event)
        return HandlerOutcome(
            result_code="CASE_ASSIGNMENT_CREATED",
            aggregate_refs=(
                {
                    "aggregate_type": "Assignment",
                    "aggregate_id": str(assignment.id),
                    "aggregate_revision": 0,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="Assignment",
                    aggregate_id=assignment.id,
                    aggregate_revision=0,
                    event_type="CaseAssignmentCreated",
                    payload={
                        "assignment_id": str(assignment.id),
                        "case_id": str(case.id),
                        "target_membership_id": str(target_membership.id),
                        "assignment_revision": 0,
                        "scope_actions": list(command.scope_actions),
                        "scope_classifications": list(command.scope_classifications),
                    },
                ),
            ),
        )


def patron_assignment_handlers() -> dict[str, PatronAssignmentManagementHandler]:
    """Return the closed patron command registrations available in increment one."""

    handler = PatronAssignmentManagementHandler()
    return {"CreateCaseAssignment": handler}
