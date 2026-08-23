from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.patron_action.application.commands import CreatePatronActionCommand
from app.modules.patron_action.infrastructure.models import (
    PatronActionRecord,
    PatronActionTransitionRecord,
)
from app.modules.patron_action.public.ports import PatronActionReference
from app.platform.events.dispatcher import (
    CommandContext,
    CommandDispatcher,
    CommandExecutionError,
    DispatchResult,
    HandlerOutcome,
    PendingDomainEvent,
)
from app.platform.security.authorization import (
    AuthorizationPolicyPort,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext, ActorKind, DataClassification


@dataclass(frozen=True, slots=True)
class PatronActionProjection:
    action_id: UUID
    case_id: UUID | None
    functional_key: str
    action_type: str
    severity: str
    state: str
    title: str
    why_now: str
    impact: str
    recommended_action: str
    due_at: datetime | None
    source_refs: tuple[str, ...]
    aggregate_revision: int


class PatronActionService:
    """Patron-only command and query facade for the decision queue."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        dispatcher: CommandDispatcher,
        policy: AuthorizationPolicyPort,
    ) -> None:
        self._session_factory = session_factory
        self._dispatcher = dispatcher
        self._policy = policy

    def execute(self, *, actor: ActorContext, command, now: datetime) -> DispatchResult:
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("PATRON_REQUIRED")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.PATRON_ACTION_WRITE,
                resource=AuthorizationResource(
                    resource_type="PATRON_ACTION",
                    resource_id=command.action_id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                    case_id=command.case_id,
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
                case_id=command.case_id,
                correlation_id=actor.correlation_id,
            ),
        )

    def list_open(
        self, *, actor: ActorContext, now: datetime
    ) -> tuple[PatronActionProjection, ...]:
        self._authorize_read(actor=actor, action_id=None, now=now)
        with self._session_factory() as session:
            records = session.scalars(
                sa.select(PatronActionRecord)
                .where(
                    PatronActionRecord.tenant_id == actor.tenant_id,
                    PatronActionRecord.state.in_(["OPEN", "IN_PROGRESS", "WAITING"]),
                )
                .order_by(
                    sa.case(
                        (PatronActionRecord.severity == "URGENT", 0),
                        (PatronActionRecord.severity == "BLOCKING", 1),
                        (PatronActionRecord.severity == "AT_RISK", 2),
                        else_=3,
                    ),
                    PatronActionRecord.due_at.asc().nulls_last(),
                    PatronActionRecord.created_at.asc(),
                )
            ).all()
            projections = []
            for record in records:
                latest = session.scalar(
                    sa.select(PatronActionTransitionRecord)
                    .where(
                        PatronActionTransitionRecord.tenant_id == actor.tenant_id,
                        PatronActionTransitionRecord.action_id == record.id,
                    )
                    .order_by(PatronActionTransitionRecord.aggregate_revision.desc())
                    .limit(1)
                )
                state = latest.to_state if latest is not None else record.state
                if state in {"COMPLETED", "ABANDONED"}:
                    continue
                revision = (
                    latest.aggregate_revision if latest is not None else record.aggregate_revision
                )
                projections.append(_projection(record, state=state, revision=revision))
            return tuple(projections)

    def _authorize_read(
        self, *, actor: ActorContext, action_id: UUID | None, now: datetime
    ) -> None:
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("PATRON_REQUIRED")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.PATRON_ACTION_READ,
                resource=AuthorizationResource(
                    resource_type="PATRON_ACTION_QUEUE",
                    resource_id=action_id or actor.tenant_id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                ),
                evaluated_at=now,
            ),
        )
        if not decision.allowed:
            raise PermissionError(decision.code)


class PatronActionWriter:
    """Public adapter that raises one action from a preparation transmission."""

    def create_from_preparation_transmission(
        self,
        *,
        session: Session,
        context: CommandContext,
        case_id: UUID,
        package_id: UUID,
        transmission_id: UUID,
        command_id: UUID,
        idempotency_key: UUID,
    ) -> PatronActionReference | None:
        functional_key = f"preparation-transmission:{transmission_id}"
        existing = session.scalar(
            sa.select(PatronActionRecord).where(
                PatronActionRecord.tenant_id == context.tenant_id,
                PatronActionRecord.functional_key == functional_key,
            )
        )
        if existing is not None:
            return None
        record = PatronActionRecord(
            id=UUID(str(transmission_id)),
            tenant_id=context.tenant_id,
            case_id=case_id,
            functional_key=functional_key,
            action_type="REVIEW_PREPARATION",
            severity="BLOCKING",
            state="OPEN",
            title="Revoir la préparation transmise par le collaborateur",
            why_now="Une préparation non financière vient d’être transmise au patron.",
            impact="La décision et la suite de l’affaire attendent un contrôle patron.",
            recommended_action="Ouvrir le dossier de préparation et décider de la suite.",
            due_at=None,
            source_refs_json=[
                f"preparation-package:{package_id}",
                f"preparation-transmission:{transmission_id}",
            ],
            aggregate_revision=1,
            actor_id=context.actor_id,
            membership_id=context.membership_id,
            command_id=command_id,
            idempotency_key=idempotency_key,
            correlation_id=context.correlation_id,
        )
        session.add(record)
        return PatronActionReference(
            id=record.id,
            case_id=record.case_id,
            action_type=record.action_type,
            severity=record.severity,
            state=record.state,
            aggregate_revision=record.aggregate_revision,
        )


class PatronActionHandler:

    """Persist the first version of an explainable patron action."""

    def execute(self, *, session: Session, command, context: CommandContext) -> HandlerOutcome:
        if context.actor_kind != ActorKind.PATRON_ADMIN.value or context.membership_id is None:
            raise CommandExecutionError("PATRON_REQUIRED")
        existing = session.scalar(
            sa.select(PatronActionRecord).where(
                PatronActionRecord.tenant_id == context.tenant_id,
                PatronActionRecord.functional_key == command.functional_key,
            )
        )
        if existing is not None:
            raise CommandExecutionError("PATRON_ACTION_ALREADY_EXISTS")
        record = PatronActionRecord(
            id=command.action_id,
            tenant_id=context.tenant_id,
            case_id=command.case_id,
            functional_key=command.functional_key,
            action_type=command.action_type,
            severity=command.severity,
            state="OPEN",
            title=command.title,
            why_now=command.why_now,
            impact=command.impact,
            recommended_action=command.recommended_action,
            due_at=command.due_at,
            source_refs_json=sorted(command.source_refs),
            aggregate_revision=1,
            actor_id=context.actor_id,
            membership_id=context.membership_id,
            command_id=command.command_id,
            idempotency_key=command.idempotency_key,
            correlation_id=command.correlation_id,
        )
        session.add(record)
        return HandlerOutcome(
            result_code="PATRON_ACTION_CREATED",
            aggregate_refs=(
                {
                    "aggregate_type": "PatronAction",
                    "aggregate_id": str(record.id),
                    "aggregate_revision": record.aggregate_revision,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="PatronAction",
                    aggregate_id=record.id,
                    aggregate_revision=record.aggregate_revision,
                    event_type="PatronActionCreated",
                    payload={
                        "action_id": str(record.id),
                        "case_id": str(record.case_id) if record.case_id else None,
                        "action_type": record.action_type,
                        "severity": record.severity,
                        "state": record.state,
                    },
                ),
            ),
        )


def patron_action_handlers() -> dict[str, PatronActionHandler]:
    handler = PatronActionHandler()
    return {CreatePatronActionCommand.command_type: handler}


def _projection(
    record: PatronActionRecord, *, state: str | None = None, revision: int | None = None
) -> PatronActionProjection:
    return PatronActionProjection(
        action_id=record.id,
        case_id=record.case_id,
        functional_key=record.functional_key,
        action_type=record.action_type,
        severity=record.severity,
        state=state or record.state,
        title=record.title,
        why_now=record.why_now,
        impact=record.impact,
        recommended_action=record.recommended_action,
        due_at=record.due_at,
        source_refs=tuple(record.source_refs_json),
        aggregate_revision=revision or record.aggregate_revision,
    )
