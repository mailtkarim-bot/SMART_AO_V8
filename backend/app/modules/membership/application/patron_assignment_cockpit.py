"""Read-only patron service for assignment authority cockpit projections."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from app.modules.membership.application.queries import (
    PatronAssignmentCockpitItemProjection,
    PatronAssignmentInteractionsLookup,
    PatronAssignmentJournalLookup,
)
from app.modules.membership.infrastructure.patron_assignment_cockpit_reader import (
    SqlAlchemyPatronAssignmentCockpitReader,
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


class PatronAssignmentCockpitService:
    """Authorize patron-only reads of closed assignment authority projections."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        policy: AuthorizationPolicyPort,
        audit_writer: SecurityAuditWriter | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._policy = policy
        self._audit_writer = audit_writer or SecurityAuditWriter()

    def list(
        self,
        *,
        actor: ActorContext,
        case_id: UUID | None,
        state: str | None,
        limit: int,
        now: datetime,
    ) -> tuple[PatronAssignmentCockpitItemProjection, ...]:
        self._require_patron(
            actor=actor,
            resource_type="ASSIGNMENT_COCKPIT",
            resource_id=actor.tenant_id,
            case_id=None,
            now=now,
        )
        self._authorize(
            actor=actor,
            resource_type="ASSIGNMENT_COCKPIT",
            resource_id=actor.tenant_id,
            case_id=None,
            now=now,
        )
        with self._session_factory() as session:
            return SqlAlchemyPatronAssignmentCockpitReader(session).list(
                tenant_id=actor.tenant_id,
                case_id=case_id,
                state=state,
                limit=limit,
            )

    def get_journal(
        self,
        *,
        actor: ActorContext,
        assignment_id: UUID,
        limit: int,
        now: datetime,
    ) -> PatronAssignmentJournalLookup:
        self._require_patron(
            actor=actor,
            resource_type="CASE_ASSIGNMENT_JOURNAL",
            resource_id=assignment_id,
            case_id=None,
            now=now,
        )
        with self._session_factory() as session:
            lookup = SqlAlchemyPatronAssignmentCockpitReader(session).get_journal(
                tenant_id=actor.tenant_id,
                assignment_id=assignment_id,
                limit=limit,
            )
        if lookup is None:
            self._record_manual_denial(
                actor=actor,
                resource_type="CASE_ASSIGNMENT_JOURNAL",
                resource_id=assignment_id,
                case_id=None,
                now=now,
                reason_code="NOT_FOUND_OR_FORBIDDEN",
            )
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        self._authorize(
            actor=actor,
            resource_type="CASE_ASSIGNMENT_JOURNAL",
            resource_id=assignment_id,
            case_id=lookup.assignment.case_id,
            now=now,
        )
        return lookup

    def get_interactions(
        self,
        *,
        actor: ActorContext,
        assignment_id: UUID,
        kind: str | None,
        limit: int,
        now: datetime,
    ) -> PatronAssignmentInteractionsLookup:
        self._require_patron(
            actor=actor,
            resource_type="CASE_ASSIGNMENT_INTERACTIONS",
            resource_id=assignment_id,
            case_id=None,
            now=now,
        )
        with self._session_factory() as session:
            lookup = SqlAlchemyPatronAssignmentCockpitReader(session).get_interactions(
                tenant_id=actor.tenant_id,
                assignment_id=assignment_id,
                kind=kind,
                limit=limit,
            )
        if lookup is None:
            self._record_manual_denial(
                actor=actor,
                resource_type="CASE_ASSIGNMENT_INTERACTIONS",
                resource_id=assignment_id,
                case_id=None,
                now=now,
                reason_code="NOT_FOUND_OR_FORBIDDEN",
            )
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        self._authorize(
            actor=actor,
            resource_type="CASE_ASSIGNMENT_INTERACTIONS",
            resource_id=assignment_id,
            case_id=lookup.case_id,
            now=now,
        )
        return lookup

    def _require_patron(
        self,
        *,
        actor: ActorContext,
        resource_type: str,
        resource_id: UUID,
        case_id: UUID | None,
        now: datetime,
    ) -> None:
        if actor.actor_kind is not ActorKind.PATRON_ADMIN:
            self._record_manual_denial(
                actor=actor,
                resource_type=resource_type,
                resource_id=resource_id,
                case_id=case_id,
                now=now,
                reason_code="ASSIGNMENT_PATRON_REQUIRED",
            )
            raise PermissionError("ASSIGNMENT_PATRON_REQUIRED")
        if actor.membership_id is None:
            self._record_manual_denial(
                actor=actor,
                resource_type=resource_type,
                resource_id=resource_id,
                case_id=case_id,
                now=now,
                reason_code="ASSIGNMENT_MEMBERSHIP_REQUIRED",
            )
            raise PermissionError("ASSIGNMENT_MEMBERSHIP_REQUIRED")

    def _authorize(
        self,
        *,
        actor: ActorContext,
        resource_type: str,
        resource_id: UUID,
        case_id: UUID | None,
        now: datetime,
    ) -> None:
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.ASSIGNMENT_MANAGE,
                resource=AuthorizationResource(
                    resource_type=resource_type,
                    resource_id=resource_id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                    case_id=case_id,
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
        resource_type: str,
        resource_id: UUID,
        case_id: UUID | None,
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
                    resource_type=resource_type,
                    resource_id=resource_id,
                    case_id=case_id,
                    correlation_id=actor.correlation_id,
                    command_id=None,
                    request_id=None,
                    source_ip_hash=None,
                    user_agent_family=None,
                    reason_code=reason_code,
                    metadata={"channel": "service"},
                ),
            )
