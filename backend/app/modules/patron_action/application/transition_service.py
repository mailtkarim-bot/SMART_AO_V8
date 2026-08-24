from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.patron_action.application.transition_commands import TransitionPatronActionCommand
from app.modules.patron_action.domain.state import ensure_transition_allowed
from app.modules.patron_action.infrastructure.models import (
    PatronActionRecord,
    PatronActionTransitionRecord,
)
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


class PatronActionTransitionService:
    def __init__(
        self, *, session_factory, dispatcher: CommandDispatcher, policy: AuthorizationPolicyPort
    ) -> None:
        self._session_factory = session_factory
        self._dispatcher = dispatcher
        self._policy = policy

    def execute(
        self, *, actor: ActorContext, command: TransitionPatronActionCommand, now: datetime
    ) -> DispatchResult:
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
                correlation_id=actor.correlation_id,
            ),
        )

    def list_open(self, *, actor: ActorContext, now: datetime):
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("PATRON_REQUIRED")
        with self._session_factory() as session:
            rows = (
                session.execute(
                    sa.select(PatronActionRecord)
                    .where(
                        PatronActionRecord.tenant_id == actor.tenant_id,
                        PatronActionRecord.state.notin_(("COMPLETED", "ABANDONED")),
                    )
                    .order_by(
                        PatronActionRecord.severity,
                        PatronActionRecord.due_at,
                        PatronActionRecord.created_at,
                    )
                )
                .scalars()
                .all()
            )
            projections = []
            for row in rows:
                latest = session.scalar(
                    sa.select(PatronActionTransitionRecord)
                    .where(
                        PatronActionTransitionRecord.tenant_id == actor.tenant_id,
                        PatronActionTransitionRecord.action_id == row.id,
                    )
                    .order_by(PatronActionTransitionRecord.aggregate_revision.desc())
                    .limit(1)
                )
                state = latest.to_state if latest is not None else row.state
                if state in {"COMPLETED", "ABANDONED"}:
                    continue
                projections.append(row.__class__)
                projections[-1] = type(
                    "PatronActionProjection",
                    (),
                    {
                        "action_id": row.id,
                        "case_id": row.case_id,
                        "severity": row.severity,
                        "state": state,
                    },
                )()
            return projections


class TransitionPatronActionHandler:
    def execute(self, *, session: Session, command, context: CommandContext) -> HandlerOutcome:
        action = session.scalar(
            sa.select(PatronActionRecord)
            .where(
                PatronActionRecord.tenant_id == context.tenant_id,
                PatronActionRecord.id == command.action_id,
            )
            .with_for_update()
        )
        if action is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        latest = session.scalar(
            sa.select(PatronActionTransitionRecord)
            .where(
                PatronActionTransitionRecord.tenant_id == context.tenant_id,
                PatronActionTransitionRecord.action_id == action.id,
            )
            .order_by(PatronActionTransitionRecord.aggregate_revision.desc())
            .limit(1)
        )
        current_state = latest.to_state if latest is not None else action.state
        current_revision = (
            latest.aggregate_revision if latest is not None else action.aggregate_revision
        )
        if current_revision != command.expected_revision:
            raise CommandExecutionError("VERSION_CONFLICT")
        if current_state in {"COMPLETED", "ABANDONED"}:
            raise CommandExecutionError("ACTION_ALREADY_CLOSED")
        try:
            ensure_transition_allowed(current_state, command.target_state)
        except ValueError as error:
            raise CommandExecutionError("INVALID_STATE_TRANSITION") from error
        transition = PatronActionTransitionRecord(
            id=command.transition_id,
            tenant_id=context.tenant_id,
            action_id=action.id,
            from_state=current_state,
            to_state=command.target_state,
            reason_code=command.reason_code,
            aggregate_revision=current_revision + 1,
            actor_id=context.actor_id,
            membership_id=context.membership_id,
            command_id=command.command_id,
            idempotency_key=command.idempotency_key,
            correlation_id=command.correlation_id,
        )
        action.state = command.target_state
        action.aggregate_revision = transition.aggregate_revision
        session.add(transition)
        return HandlerOutcome(
            result_code="PATRON_ACTION_TRANSITIONED",
            aggregate_refs=(
                {
                    "aggregate_type": "PatronAction",
                    "aggregate_id": str(action.id),
                    "aggregate_revision": transition.aggregate_revision,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="PatronAction",
                    aggregate_id=action.id,
                    aggregate_revision=transition.aggregate_revision,
                    event_type="PatronActionTransitioned",
                    payload={
                        "action_id": str(action.id),
                        "from_state": current_state,
                        "to_state": command.target_state,
                        "aggregate_revision": transition.aggregate_revision,
                    },
                ),
            ),
        )


def patron_action_transition_handlers():
    handler = TransitionPatronActionHandler()
    return {TransitionPatronActionCommand.command_type: handler}
