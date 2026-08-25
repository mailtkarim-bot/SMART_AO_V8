"""Transactional patron-owned boundaries for controlled Case assignment management."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.dce.application.commands import (
    AmendCaseAssignmentScopeCommand,
    CreateCaseAssignmentCommand,
    EndCaseAssignmentCommand,
    ReactivateCaseAssignmentCommand,
    SuspendCaseAssignmentCommand,
    ValidateAssignmentInteractionCommand,
)
from app.modules.membership.application.queries import (
    AssignmentManagementCase,
    AssignmentManagementReader,
    AssignmentManagementTarget,
)
from app.modules.membership.infrastructure.records import (
    AssignmentClarificationRequestRecord,
    AssignmentInteractionPatronValidationRecord,
    CaseAssignmentAcknowledgementRecord,
    CaseAssignmentChangeEventRecord,
    CaseAssignmentRecord,
    CaseAssignmentUnavailabilityRecord,
    TenantMembershipRecord,
)
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


class PatronAssignmentManagementService:
    """Resolve patron authority before dispatching assignment management commands."""

    def __init__(
        self,
        *,
        session_factory: Any,
        reader: AssignmentManagementReader,
        dispatcher: CommandDispatcher,
        policy: AuthorizationPolicyPort,
        audit_writer: SecurityAuditWriter | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._reader = reader
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
        self._require_patron(
            actor=actor,
            command=command,
            now=now,
            resource_type="CASE",
            resource_id=command.case_id,
            case_id=command.case_id,
        )
        case = self._resolve_case(tenant_id=actor.tenant_id, case_id=command.case_id)
        if case is None:
            self._record_manual_denial(
                actor=actor,
                command=command,
                now=now,
                reason_code="NOT_FOUND_OR_FORBIDDEN",
                resource_type="CASE",
                resource_id=command.case_id,
                case_id=command.case_id,
            )
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        self._authorize_case_management(actor=actor, case=case, now=now)
        return self._dispatch(actor=actor, command=command, case_id=case.id, now=now)

    def amend_scope(
        self,
        *,
        actor: ActorContext,
        command: AmendCaseAssignmentScopeCommand,
        now: datetime,
    ) -> DispatchResult:
        self._require_patron(
            actor=actor,
            command=command,
            now=now,
            resource_type="CASE_ASSIGNMENT",
            resource_id=command.assignment_id,
            case_id=None,
        )
        assignment = self._resolve_assignment(
            tenant_id=actor.tenant_id,
            assignment_id=command.assignment_id,
        )
        if assignment is None:
            self._record_manual_denial(
                actor=actor,
                command=command,
                now=now,
                reason_code="NOT_FOUND_OR_FORBIDDEN",
                resource_type="CASE_ASSIGNMENT",
                resource_id=command.assignment_id,
                case_id=None,
            )
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.ASSIGNMENT_MANAGE,
                resource=AuthorizationResource(
                    resource_type="CASE_ASSIGNMENT",
                    resource_id=assignment.id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                    case_id=assignment.case_id,
                ),
                evaluated_at=now,
            ),
        )
        if not decision.allowed:
            raise PermissionError(decision.code)
        return self._dispatch(actor=actor, command=command, case_id=assignment.case_id, now=now)

    def suspend(
        self,
        *,
        actor: ActorContext,
        command: SuspendCaseAssignmentCommand,
        now: datetime,
    ) -> DispatchResult:
        self._require_patron(
            actor=actor,
            command=command,
            now=now,
            resource_type="CASE_ASSIGNMENT",
            resource_id=command.assignment_id,
            case_id=None,
        )
        assignment = self._resolve_assignment(
            tenant_id=actor.tenant_id,
            assignment_id=command.assignment_id,
        )
        if assignment is None:
            self._record_manual_denial(
                actor=actor,
                command=command,
                now=now,
                reason_code="NOT_FOUND_OR_FORBIDDEN",
                resource_type="CASE_ASSIGNMENT",
                resource_id=command.assignment_id,
                case_id=None,
            )
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        self._authorize_assignment_management(actor=actor, assignment=assignment, now=now)
        return self._dispatch(actor=actor, command=command, case_id=assignment.case_id, now=now)

    def reactivate(
        self,
        *,
        actor: ActorContext,
        command: ReactivateCaseAssignmentCommand,
        now: datetime,
    ) -> DispatchResult:
        self._require_patron(
            actor=actor,
            command=command,
            now=now,
            resource_type="CASE_ASSIGNMENT",
            resource_id=command.assignment_id,
            case_id=None,
        )
        assignment = self._resolve_assignment(
            tenant_id=actor.tenant_id,
            assignment_id=command.assignment_id,
        )
        if assignment is None:
            self._record_manual_denial(
                actor=actor,
                command=command,
                now=now,
                reason_code="NOT_FOUND_OR_FORBIDDEN",
                resource_type="CASE_ASSIGNMENT",
                resource_id=command.assignment_id,
                case_id=None,
            )
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        self._authorize_assignment_management(actor=actor, assignment=assignment, now=now)
        return self._dispatch(actor=actor, command=command, case_id=assignment.case_id, now=now)

    def end(
        self,
        *,
        actor: ActorContext,
        command: EndCaseAssignmentCommand,
        now: datetime,
    ) -> DispatchResult:
        self._require_patron(
            actor=actor,
            command=command,
            now=now,
            resource_type="CASE_ASSIGNMENT",
            resource_id=command.assignment_id,
            case_id=None,
        )
        assignment = self._resolve_assignment(
            tenant_id=actor.tenant_id,
            assignment_id=command.assignment_id,
        )
        if assignment is None:
            self._record_manual_denial(
                actor=actor,
                command=command,
                now=now,
                reason_code="NOT_FOUND_OR_FORBIDDEN",
                resource_type="CASE_ASSIGNMENT",
                resource_id=command.assignment_id,
                case_id=None,
            )
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        self._authorize_assignment_management(actor=actor, assignment=assignment, now=now)
        return self._dispatch(actor=actor, command=command, case_id=assignment.case_id, now=now)

    def validate_interaction(
        self,
        *,
        actor: ActorContext,
        command: ValidateAssignmentInteractionCommand,
        now: datetime,
    ) -> DispatchResult:
        self._require_patron(
            actor=actor,
            command=command,
            now=now,
            resource_type="CASE_ASSIGNMENT_INTERACTION_VALIDATION",
            resource_id=command.assignment_id,
            case_id=None,
        )
        assignment = self._resolve_assignment(
            tenant_id=actor.tenant_id,
            assignment_id=command.assignment_id,
        )
        if assignment is None:
            self._record_manual_denial(
                actor=actor,
                command=command,
                now=now,
                reason_code="NOT_FOUND_OR_FORBIDDEN",
                resource_type="CASE_ASSIGNMENT_INTERACTION_VALIDATION",
                resource_id=command.assignment_id,
                case_id=None,
            )
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        self._authorize_assignment_management(actor=actor, assignment=assignment, now=now)
        return self._dispatch(actor=actor, command=command, case_id=assignment.case_id, now=now)

    def _dispatch(
        self,
        *,
        actor: ActorContext,
        command,
        case_id: UUID,
        now: datetime,
    ) -> DispatchResult:
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
                case_id=case_id,
                correlation_id=actor.correlation_id,
            ),
        )

    def _require_patron(
        self,
        *,
        actor: ActorContext,
        command,
        now: datetime,
        resource_type: str,
        resource_id: UUID,
        case_id: UUID | None,
    ) -> None:
        if actor.actor_kind is not ActorKind.PATRON_ADMIN:
            self._record_manual_denial(
                actor=actor,
                command=command,
                now=now,
                reason_code="ASSIGNMENT_PATRON_REQUIRED",
                resource_type=resource_type,
                resource_id=resource_id,
                case_id=case_id,
            )
            raise PermissionError("ASSIGNMENT_PATRON_REQUIRED")
        if actor.membership_id is None:
            self._record_manual_denial(
                actor=actor,
                command=command,
                now=now,
                reason_code="ASSIGNMENT_MEMBERSHIP_REQUIRED",
                resource_type=resource_type,
                resource_id=resource_id,
                case_id=case_id,
            )
            raise PermissionError("ASSIGNMENT_MEMBERSHIP_REQUIRED")

    def _authorize_case_management(
        self,
        *,
        actor: ActorContext,
        case: AssignmentManagementCase,
        now: datetime,
    ) -> None:
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

    def _authorize_assignment_management(
        self,
        *,
        actor: ActorContext,
        assignment: AssignmentManagementTarget,
        now: datetime,
    ) -> None:
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.ASSIGNMENT_MANAGE,
                resource=AuthorizationResource(
                    resource_type="CASE_ASSIGNMENT",
                    resource_id=assignment.id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                    case_id=assignment.case_id,
                ),
                evaluated_at=now,
            ),
        )
        if not decision.allowed:
            raise PermissionError(decision.code)

    def _record_manual_denial(
        self,
        *,
        actor: ActorContext,
        command,
        now: datetime,
        reason_code: str,
        resource_type: str,
        resource_id: UUID,
        case_id: UUID | None,
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
                    resource_type=resource_type,
                    resource_id=resource_id,
                    case_id=case_id,
                    correlation_id=command.correlation_id,
                    command_id=command.command_id,
                    request_id=None,
                    source_ip_hash=None,
                    user_agent_family=None,
                    reason_code=reason_code,
                    metadata={"channel": "service"},
                ),
            )

    def _resolve_case(
        self, *, tenant_id: UUID, case_id: UUID
    ) -> AssignmentManagementCase | None:
        return self._reader.get_case(tenant_id=tenant_id, case_id=case_id)

    def _resolve_assignment(
        self, *, tenant_id: UUID, assignment_id: UUID
    ) -> AssignmentManagementTarget | None:
        return self._reader.get_assignment(tenant_id=tenant_id, assignment_id=assignment_id)


class PatronAssignmentManagementHandler:
    """Own the atomic patron mutations available in the current increment."""

    def execute(self, *, session: Session, command, context: CommandContext) -> HandlerOutcome:
        if context.actor_kind != ActorKind.PATRON_ADMIN.value:
            raise CommandExecutionError("ASSIGNMENT_PATRON_REQUIRED")
        if context.membership_id is None:
            raise CommandExecutionError("ASSIGNMENT_MEMBERSHIP_CONTEXT_REQUIRED")
        if command.command_type == "CreateCaseAssignment":
            return self._create(session=session, command=command, context=context)
        if command.command_type == "AmendCaseAssignmentScope":
            return self._amend_scope(session=session, command=command, context=context)
        if command.command_type == "SuspendCaseAssignment":
            return self._suspend(session=session, command=command, context=context)
        if command.command_type == "ReactivateCaseAssignment":
            return self._reactivate(session=session, command=command, context=context)
        if command.command_type == "EndCaseAssignment":
            return self._end(session=session, command=command, context=context)
        if command.command_type == "ValidateAssignmentInteraction":
            return self._validate_interaction(session=session, command=command, context=context)
        raise CommandExecutionError(
            f"unsupported patron assignment command: {command.command_type}"
        )

    @staticmethod
    def _create(
        *,
        session: Session,
        command: CreateCaseAssignmentCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
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
        session.add(
            _change_event_for_creation(
                assignment=assignment,
                author_membership_id=context.membership_id,
                command=command,
            )
        )
        return HandlerOutcome(
            result_code="CASE_ASSIGNMENT_CREATED",
            aggregate_refs=(_aggregate_ref(assignment=assignment, revision=0),),
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

    @staticmethod
    def _amend_scope(
        *,
        session: Session,
        command: AmendCaseAssignmentScopeCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        assignment = session.scalar(
            sa.select(CaseAssignmentRecord)
            .where(
                CaseAssignmentRecord.tenant_id == context.tenant_id,
                CaseAssignmentRecord.id == command.assignment_id,
            )
            .with_for_update()
        )
        if assignment is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if assignment.state not in {"ACTIVE", "SUSPENDED"}:
            raise CommandExecutionError("ASSIGNMENT_INACTIVE")
        if assignment.aggregate_revision != command.expected_revision:
            raise CommandExecutionError("VERSION_CONFLICT")
        if context.case_id is not None and context.case_id != assignment.case_id:
            raise CommandExecutionError("CASE_CONTEXT_MISMATCH")

        case = session.scalar(
            sa.select(CaseRecord).where(
                CaseRecord.tenant_id == context.tenant_id,
                CaseRecord.id == assignment.case_id,
            )
        )
        if case is None or case.lifecycle == "ARCHIVED":
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")

        previous_actions = list(assignment.scope_actions_json)
        previous_classifications = list(assignment.scope_classifications_json)
        resulting_actions = list(command.scope_actions)
        resulting_classifications = list(command.scope_classifications)
        if (
            previous_actions == resulting_actions
            and previous_classifications == resulting_classifications
        ):
            raise CommandExecutionError("ASSIGNMENT_SCOPE_UNCHANGED")

        revision = assignment.aggregate_revision + 1
        assignment.scope_actions_json = resulting_actions
        assignment.scope_classifications_json = resulting_classifications
        assignment.aggregate_revision = revision
        session.add(
            CaseAssignmentChangeEventRecord(
                id=uuid4(),
                tenant_id=context.tenant_id,
                assignment_id=assignment.id,
                case_id=assignment.case_id,
                target_membership_id=assignment.membership_id,
                author_membership_id=context.membership_id,
                event_type="ASSIGNMENT_SCOPE_AMENDED",
                previous_revision=revision - 1,
                resulting_revision=revision,
                previous_state=assignment.state,
                resulting_state=assignment.state,
                reason_code=None,
                previous_scope_actions_json=previous_actions,
                previous_scope_classifications_json=previous_classifications,
                resulting_scope_actions_json=resulting_actions,
                resulting_scope_classifications_json=resulting_classifications,
                command_id=command.command_id,
                correlation_id=command.correlation_id,
            )
        )
        return HandlerOutcome(
            result_code="CASE_ASSIGNMENT_SCOPE_AMENDED",
            aggregate_refs=(_aggregate_ref(assignment=assignment, revision=revision),),
            events=(
                PendingDomainEvent(
                    aggregate_type="Assignment",
                    aggregate_id=assignment.id,
                    aggregate_revision=revision,
                    event_type="CaseAssignmentScopeAmended",
                    payload={
                        "assignment_id": str(assignment.id),
                        "case_id": str(assignment.case_id),
                        "previous_revision": revision - 1,
                        "resulting_revision": revision,
                        "previous_scope_fingerprint": _scope_fingerprint(
                            actions=previous_actions,
                            classifications=previous_classifications,
                        ),
                        "resulting_scope_fingerprint": _scope_fingerprint(
                            actions=resulting_actions,
                            classifications=resulting_classifications,
                        ),
                    },
                ),
            ),
        )

    @staticmethod
    def _suspend(
        *,
        session: Session,
        command: SuspendCaseAssignmentCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        assignment = session.scalar(
            sa.select(CaseAssignmentRecord)
            .where(
                CaseAssignmentRecord.tenant_id == context.tenant_id,
                CaseAssignmentRecord.id == command.assignment_id,
            )
            .with_for_update()
        )
        if assignment is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if assignment.state != "ACTIVE":
            raise CommandExecutionError("ASSIGNMENT_NOT_ACTIVE")
        if assignment.aggregate_revision != command.expected_revision:
            raise CommandExecutionError("VERSION_CONFLICT")
        if context.case_id is not None and context.case_id != assignment.case_id:
            raise CommandExecutionError("CASE_CONTEXT_MISMATCH")

        revision = assignment.aggregate_revision + 1
        assignment.state = "SUSPENDED"
        assignment.aggregate_revision = revision
        scope_actions = list(assignment.scope_actions_json)
        scope_classifications = list(assignment.scope_classifications_json)
        session.add(
            CaseAssignmentChangeEventRecord(
                id=uuid4(),
                tenant_id=context.tenant_id,
                assignment_id=assignment.id,
                case_id=assignment.case_id,
                target_membership_id=assignment.membership_id,
                author_membership_id=context.membership_id,
                event_type="ASSIGNMENT_SUSPENDED",
                previous_revision=revision - 1,
                resulting_revision=revision,
                previous_state="ACTIVE",
                resulting_state="SUSPENDED",
                reason_code=command.suspension_reason_code,
                previous_scope_actions_json=scope_actions,
                previous_scope_classifications_json=scope_classifications,
                resulting_scope_actions_json=scope_actions,
                resulting_scope_classifications_json=scope_classifications,
                command_id=command.command_id,
                correlation_id=command.correlation_id,
            )
        )
        return HandlerOutcome(
            result_code="CASE_ASSIGNMENT_SUSPENDED",
            aggregate_refs=(_aggregate_ref(assignment=assignment, revision=revision),),
            events=(
                PendingDomainEvent(
                    aggregate_type="Assignment",
                    aggregate_id=assignment.id,
                    aggregate_revision=revision,
                    event_type="CaseAssignmentSuspended",
                    payload={
                        "assignment_id": str(assignment.id),
                        "case_id": str(assignment.case_id),
                        "previous_revision": revision - 1,
                        "resulting_revision": revision,
                        "suspension_reason_code": command.suspension_reason_code,
                    },
                ),
            ),
        )

    @staticmethod
    def _reactivate(
        *,
        session: Session,
        command: ReactivateCaseAssignmentCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        assignment = session.scalar(
            sa.select(CaseAssignmentRecord)
            .where(
                CaseAssignmentRecord.tenant_id == context.tenant_id,
                CaseAssignmentRecord.id == command.assignment_id,
            )
            .with_for_update()
        )
        if assignment is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if assignment.state != "SUSPENDED":
            raise CommandExecutionError("ASSIGNMENT_NOT_SUSPENDED")
        if assignment.aggregate_revision != command.expected_revision:
            raise CommandExecutionError("VERSION_CONFLICT")
        if context.case_id is not None and context.case_id != assignment.case_id:
            raise CommandExecutionError("CASE_CONTEXT_MISMATCH")

        case = session.scalar(
            sa.select(CaseRecord)
            .where(
                CaseRecord.tenant_id == context.tenant_id,
                CaseRecord.id == assignment.case_id,
            )
            .with_for_update()
        )
        if case is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if case.lifecycle != "ACTIVE":
            raise CommandExecutionError("CASE_INACTIVE")
        target_membership = session.scalar(
            sa.select(TenantMembershipRecord)
            .where(
                TenantMembershipRecord.tenant_id == context.tenant_id,
                TenantMembershipRecord.id == assignment.membership_id,
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
        if assignment.starts_at > context.received_at:
            raise CommandExecutionError("ASSIGNMENT_WINDOW_NOT_OPEN")
        if assignment.ends_at is not None and context.received_at >= assignment.ends_at:
            raise CommandExecutionError("ASSIGNMENT_WINDOW_CLOSED")

        revision = assignment.aggregate_revision + 1
        assignment.state = "ACTIVE"
        assignment.aggregate_revision = revision
        scope_actions = list(assignment.scope_actions_json)
        scope_classifications = list(assignment.scope_classifications_json)
        session.add(
            CaseAssignmentChangeEventRecord(
                id=uuid4(),
                tenant_id=context.tenant_id,
                assignment_id=assignment.id,
                case_id=assignment.case_id,
                target_membership_id=assignment.membership_id,
                author_membership_id=context.membership_id,
                event_type="ASSIGNMENT_REACTIVATED",
                previous_revision=revision - 1,
                resulting_revision=revision,
                previous_state="SUSPENDED",
                resulting_state="ACTIVE",
                reason_code=command.reactivation_reason_code,
                previous_scope_actions_json=scope_actions,
                previous_scope_classifications_json=scope_classifications,
                resulting_scope_actions_json=scope_actions,
                resulting_scope_classifications_json=scope_classifications,
                command_id=command.command_id,
                correlation_id=command.correlation_id,
            )
        )
        return HandlerOutcome(
            result_code="CASE_ASSIGNMENT_REACTIVATED",
            aggregate_refs=(_aggregate_ref(assignment=assignment, revision=revision),),
            events=(
                PendingDomainEvent(
                    aggregate_type="Assignment",
                    aggregate_id=assignment.id,
                    aggregate_revision=revision,
                    event_type="CaseAssignmentReactivated",
                    payload={
                        "assignment_id": str(assignment.id),
                        "case_id": str(assignment.case_id),
                        "previous_revision": revision - 1,
                        "resulting_revision": revision,
                        "reactivation_reason_code": command.reactivation_reason_code,
                    },
                ),
            ),
        )

    @staticmethod
    def _end(
        *,
        session: Session,
        command: EndCaseAssignmentCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        assignment = session.scalar(
            sa.select(CaseAssignmentRecord)
            .where(
                CaseAssignmentRecord.tenant_id == context.tenant_id,
                CaseAssignmentRecord.id == command.assignment_id,
            )
            .with_for_update()
        )
        if assignment is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if assignment.state not in {"ACTIVE", "SUSPENDED"}:
            raise CommandExecutionError("ASSIGNMENT_NOT_OPEN")
        if assignment.aggregate_revision != command.expected_revision:
            raise CommandExecutionError("VERSION_CONFLICT")
        if context.case_id is not None and context.case_id != assignment.case_id:
            raise CommandExecutionError("CASE_CONTEXT_MISMATCH")

        previous_state = assignment.state
        revision = assignment.aggregate_revision + 1
        scope_actions = list(assignment.scope_actions_json)
        scope_classifications = list(assignment.scope_classifications_json)
        assignment.state = "ENDED"
        assignment.ended_at = context.received_at
        assignment.aggregate_revision = revision
        session.add(
            CaseAssignmentChangeEventRecord(
                id=uuid4(),
                tenant_id=context.tenant_id,
                assignment_id=assignment.id,
                case_id=assignment.case_id,
                target_membership_id=assignment.membership_id,
                author_membership_id=context.membership_id,
                event_type="ASSIGNMENT_ENDED",
                previous_revision=revision - 1,
                resulting_revision=revision,
                previous_state=previous_state,
                resulting_state="ENDED",
                reason_code=command.end_reason_code,
                previous_scope_actions_json=scope_actions,
                previous_scope_classifications_json=scope_classifications,
                resulting_scope_actions_json=scope_actions,
                resulting_scope_classifications_json=scope_classifications,
                command_id=command.command_id,
                correlation_id=command.correlation_id,
            )
        )
        return HandlerOutcome(
            result_code="CASE_ASSIGNMENT_ENDED",
            aggregate_refs=(_aggregate_ref(assignment=assignment, revision=revision),),
            events=(
                PendingDomainEvent(
                    aggregate_type="Assignment",
                    aggregate_id=assignment.id,
                    aggregate_revision=revision,
                    event_type="CaseAssignmentEnded",
                    payload={
                        "assignment_id": str(assignment.id),
                        "case_id": str(assignment.case_id),
                        "previous_revision": revision - 1,
                        "resulting_revision": revision,
                        "previous_state": previous_state,
                        "end_reason_code": command.end_reason_code,
                    },
                ),
            ),
        )

    @staticmethod
    def _validate_interaction(
        *,
        session: Session,
        command: ValidateAssignmentInteractionCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        assignment = session.scalar(
            sa.select(CaseAssignmentRecord)
            .where(
                CaseAssignmentRecord.tenant_id == context.tenant_id,
                CaseAssignmentRecord.id == command.assignment_id,
            )
            .with_for_update()
        )
        if assignment is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if context.case_id is not None and context.case_id != assignment.case_id:
            raise CommandExecutionError("CASE_CONTEXT_MISMATCH")
        source_model = {
            "ACKNOWLEDGEMENT": CaseAssignmentAcknowledgementRecord,
            "CLARIFICATION_REQUEST": AssignmentClarificationRequestRecord,
            "UNAVAILABILITY_REPORT": CaseAssignmentUnavailabilityRecord,
        }[command.interaction_kind]
        source = session.scalar(
            sa.select(source_model)
            .where(
                source_model.tenant_id == context.tenant_id,
                source_model.assignment_id == assignment.id,
                source_model.id == command.interaction_id,
            )
            .with_for_update()
        )
        if source is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        existing = session.scalar(
            sa.select(AssignmentInteractionPatronValidationRecord)
            .where(
                AssignmentInteractionPatronValidationRecord.tenant_id == context.tenant_id,
                AssignmentInteractionPatronValidationRecord.interaction_kind
                == command.interaction_kind,
                AssignmentInteractionPatronValidationRecord.interaction_id
                == command.interaction_id,
            )
            .with_for_update()
        )
        if existing is not None:
            raise CommandExecutionError("INTERACTION_ALREADY_VALIDATED")
        validation = AssignmentInteractionPatronValidationRecord(
            id=uuid4(),
            tenant_id=context.tenant_id,
            assignment_id=assignment.id,
            case_id=assignment.case_id,
            interaction_id=command.interaction_id,
            interaction_kind=command.interaction_kind,
            validation_code=command.validation_code,
            patron_membership_id=context.membership_id,
            command_id=command.command_id,
            correlation_id=command.correlation_id,
        )
        session.add(validation)
        return HandlerOutcome(
            result_code="INTERACTION_VALIDATED",
            aggregate_refs=(
                {
                    "aggregate_type": "AssignmentInteractionValidation",
                    "aggregate_id": str(validation.id),
                    "aggregate_revision": 0,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="AssignmentInteractionValidation",
                    aggregate_id=validation.id,
                    aggregate_revision=0,
                    event_type="AssignmentInteractionValidated",
                    payload={
                        "validation_id": str(validation.id),
                        "assignment_id": str(assignment.id),
                        "case_id": str(assignment.case_id),
                        "interaction_kind": command.interaction_kind,
                        "validation_code": command.validation_code,
                    },
                ),
            ),
        )


def _change_event_for_creation(
    *,
    assignment: CaseAssignmentRecord,
    author_membership_id: UUID,
    command: CreateCaseAssignmentCommand,
) -> CaseAssignmentChangeEventRecord:
    return CaseAssignmentChangeEventRecord(
        id=uuid4(),
        tenant_id=assignment.tenant_id,
        assignment_id=assignment.id,
        case_id=assignment.case_id,
        target_membership_id=assignment.membership_id,
        author_membership_id=author_membership_id,
        event_type="ASSIGNMENT_CREATED",
        previous_revision=None,
        resulting_revision=0,
        previous_state=None,
        resulting_state="ACTIVE",
        reason_code=None,
        previous_scope_actions_json=None,
        previous_scope_classifications_json=None,
        resulting_scope_actions_json=list(assignment.scope_actions_json),
        resulting_scope_classifications_json=list(assignment.scope_classifications_json),
        command_id=command.command_id,
        correlation_id=command.correlation_id,
    )


def _aggregate_ref(*, assignment: CaseAssignmentRecord, revision: int) -> dict[str, object]:
    return {
        "aggregate_type": "Assignment",
        "aggregate_id": str(assignment.id),
        "aggregate_revision": revision,
    }


def _scope_fingerprint(*, actions: list[str], classifications: list[str]) -> str:
    payload = json.dumps(
        {"actions": actions, "classifications": classifications},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def patron_assignment_handlers() -> dict[str, PatronAssignmentManagementHandler]:
    """Return the closed patron command registrations available in the current increment."""

    handler = PatronAssignmentManagementHandler()
    return {
        "CreateCaseAssignment": handler,
        "AmendCaseAssignmentScope": handler,
        "SuspendCaseAssignment": handler,
        "ReactivateCaseAssignment": handler,
        "EndCaseAssignment": handler,
        "ValidateAssignmentInteraction": handler,
    }
