from __future__ import annotations

import json
from collections.abc import Callable
from hashlib import sha256
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.modules.decision.application.lifecycle_commands import (
    CreateDecisionCommand,
    FreezeDecisionContextCommand,
    ResolveDecisionConditionCommand,
)
from app.modules.decision.application.ports import (
    DecisionConditionRepository,
    DecisionConditionTransitionDraft,
    DecisionContextDraft,
    DecisionContextReferenceDraft,
    DecisionDraft,
    DecisionLifecycleRepository,
    DecisionRepository,
)
from app.modules.decision.domain.decision import DecisionContext
from app.platform.events.dispatcher import (
    CommandContext,
    CommandDispatcher,
    CommandExecutionError,
    CommandHandler,
    DispatchResult,
    HandlerOutcome,
    PendingDomainEvent,
)
from app.platform.persistence.repository import OptimisticRevisionConflictError
from app.platform.security.authorization import (
    AuthorizationPolicyPort,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext, ActorKind, DataClassification


class PatronDecisionLifecycleService:
    """Authorize and dispatch patron-only Decision lifecycle commands."""

    def __init__(self, *, dispatcher: CommandDispatcher, policy: AuthorizationPolicyPort) -> None:
        self._dispatcher = dispatcher
        self._policy = policy

    def execute(self, *, actor: ActorContext, command: Any, now) -> DispatchResult:
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("PATRON_REQUIRED")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.DECISION_MANAGE,
                resource=AuthorizationResource(
                    resource_type="DECISION",
                    resource_id=command.decision_id,
                    tenant_id=actor.tenant_id,
                    case_id=command.case_id,
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
                case_id=command.case_id,
                correlation_id=actor.correlation_id,
            ),
        )


class CreateDecisionHandler:
    def __init__(self, *, repository: DecisionLifecycleRepository) -> None:
        self._repository = repository

    def execute(
        self, *, session, command: CreateDecisionCommand, context: CommandContext
    ) -> HandlerOutcome:
        tenant_id = UUID(str(context.tenant_id))
        if not self._repository.case_exists(
            session=session, tenant_id=tenant_id, case_id=command.case_id
        ):
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        case_scope_fingerprint = self._repository.case_scope_fingerprint(
            session=session, tenant_id=tenant_id, case_id=command.case_id
        )
        if case_scope_fingerprint is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if (
            command.scope_fingerprint is not None
            and case_scope_fingerprint.lower() != command.scope_fingerprint.lower()
        ):
            raise CommandExecutionError("STALE_CASE_SCOPE")
        effective_scope_fingerprint = case_scope_fingerprint.lower()
        decision_key_hash = _sha256_json(
            {
                "case_id": str(command.case_id),
                "decision_type": command.decision_type,
                "scope_fingerprint": effective_scope_fingerprint,
            }
        )
        if self._repository.active_decision_exists(
            session=session,
            tenant_id=tenant_id,
            decision_key_hash=decision_key_hash,
        ):
            raise CommandExecutionError("DECISION_ALREADY_ACTIVE")
        decision = DecisionDraft(
            id=command.decision_id,
            tenant_id=UUID(str(context.tenant_id)),
            decision_type=command.decision_type,
            subject_type="CASE",
            subject_id=command.case_id,
            case_id=command.case_id,
            scope_fingerprint=effective_scope_fingerprint,
            decision_key_hash=decision_key_hash,
            cycle_number=self._repository.next_cycle_number(
                session=session,
                tenant_id=tenant_id,
                decision_key_hash=decision_key_hash,
            ),
            actor_id=UUID(str(context.actor_id)),
        )
        self._repository.create_root(session=session, draft=decision)
        flush = getattr(session, "flush", None)
        if callable(flush):
            try:
                flush()
            except IntegrityError as error:
                raise CommandExecutionError("DECISION_ALREADY_ACTIVE") from error
        return HandlerOutcome(
            result_code="DECISION_DRAFT_CREATED",
            aggregate_refs=(
                {
                    "aggregate_type": "Decision",
                    "aggregate_id": str(decision.id),
                    "aggregate_revision": 0,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="Decision",
                    aggregate_id=decision.id,
                    aggregate_revision=0,
                    event_type="DecisionDraftCreated",
                    payload={"decision_id": str(decision.id), "case_id": str(decision.case_id)},
                ),
            ),
        )


class FreezeDecisionContextHandler:
    def __init__(
        self,
        *,
        lifecycle_repository: DecisionLifecycleRepository,
        repository_factory: Callable[[Any], DecisionRepository],
    ) -> None:
        self._lifecycle_repository = lifecycle_repository
        self._repository_factory = repository_factory

    def execute(
        self, *, session, command: FreezeDecisionContextCommand, context: CommandContext
    ) -> HandlerOutcome:
        repository = self._repository_factory(session)
        snapshot = repository.get(tenant_id=context.tenant_id, aggregate_id=command.decision_id)
        if snapshot is None or snapshot.root.case_id != command.case_id:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if (
            snapshot.root.decision_type != "GO_NO_GO"
            or snapshot.root.lifecycle != "DRAFT"
            or snapshot.root.context_status != "INCOMPLETE"
            or snapshot.contexts
        ):
            raise CommandExecutionError("DECISION_NOT_READY_FOR_CONTEXT")
        if snapshot.root.aggregate_revision != command.expected_revision:
            raise CommandExecutionError("STALE_DECISION_REVISION")
        if not any(
            reference.aggregate_type == "CASE" and reference.aggregate_id == command.case_id
            for reference in command.references
        ):
            raise CommandExecutionError("DECISION_CONTEXT_CASE_REFERENCE_REQUIRED")
        valid_reference_types = {reference.aggregate_type for reference in command.references}
        if (
            self._lifecycle_repository.case_has_applicable_dce(
                session=session,
                tenant_id=UUID(str(context.tenant_id)),
                case_id=command.case_id,
            )
            and "DCE_REQUIREMENT" not in valid_reference_types
        ):
            raise CommandExecutionError("DCE_REQUIREMENT_REFERENCE_REQUIRED")
        for reference in command.references:
            if not self._lifecycle_repository.context_reference_is_valid(
                session=session,
                tenant_id=UUID(str(context.tenant_id)),
                case_id=command.case_id,
                aggregate_type=reference.aggregate_type,
                aggregate_id=reference.aggregate_id,
                aggregate_revision=reference.aggregate_revision,
                content_hash=reference.content_hash,
            ):
                raise CommandExecutionError("INVALID_DECISION_CONTEXT_REFERENCE")

        prepared_at = context.received_at
        reference_tokens = tuple(
            _reference_token(
                reference.aggregate_type,
                reference.aggregate_id,
                reference.aggregate_revision,
                reference.reference_role,
            )
            for reference in command.references
        )
        decision_context = DecisionContext.build(
            context_id=command.context_id,
            tenant_id=UUID(str(context.tenant_id)),
            references=reference_tokens,
            unknowns=command.unknowns,
            risks=command.risks,
            prepared_at=prepared_at,
        )
        canonical_context_json = {
            "decision_id": str(command.decision_id),
            "case_id": str(command.case_id),
            "references": [
                {
                    "aggregate_type": reference.aggregate_type,
                    "aggregate_id": str(reference.aggregate_id),
                    "aggregate_revision": reference.aggregate_revision,
                    "content_hash": reference.content_hash,
                    "reference_role": reference.reference_role,
                }
                for reference in command.references
            ],
            "unknowns": list(decision_context.unknowns),
            "risks": list(decision_context.risks),
            "prepared_at": prepared_at.isoformat(),
        }
        self._lifecycle_repository.create_context(
            session=session,
            context=DecisionContextDraft(
                id=decision_context.context_id,
                tenant_id=UUID(str(context.tenant_id)),
                decision_id=command.decision_id,
                sequence_number=1,
                context_fingerprint=decision_context.fingerprint,
                canonical_context_json=canonical_context_json,
                rationale=command.rationale.strip(),
                unknowns_json=decision_context.unknowns,
                prepared_at=prepared_at,
                prepared_by_actor_id=UUID(str(context.actor_id)),
            ),
            references=tuple(
                DecisionContextReferenceDraft(
                    id=_reference_id(reference),
                    tenant_id=UUID(str(context.tenant_id)),
                    decision_context_id=command.context_id,
                    aggregate_type=reference.aggregate_type,
                    aggregate_id=reference.aggregate_id,
                    aggregate_revision=reference.aggregate_revision,
                    content_hash=reference.content_hash.lower() if reference.content_hash else None,
                    reference_role=reference.reference_role.strip(),
                )
                for reference in command.references
            ),
        )
        try:
            new_revision = repository.update_root(
                tenant_id=context.tenant_id,
                aggregate_id=command.decision_id,
                expected_revision=command.expected_revision,
                changes={
                    "lifecycle": "PENDING_PATRON",
                    "context_status": "FROZEN",
                    "updated_by_actor_id": context.actor_id,
                },
            )
        except OptimisticRevisionConflictError as error:
            raise CommandExecutionError("STALE_DECISION_REVISION") from error
        return HandlerOutcome(
            result_code="DECISION_CONTEXT_FROZEN",
            aggregate_refs=(
                {
                    "aggregate_type": "Decision",
                    "aggregate_id": str(command.decision_id),
                    "aggregate_revision": new_revision,
                },
                {
                    "aggregate_type": "DecisionContext",
                    "aggregate_id": str(command.context_id),
                    "aggregate_revision": new_revision,
                    "fingerprint": decision_context.fingerprint,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="Decision",
                    aggregate_id=command.decision_id,
                    aggregate_revision=new_revision,
                    event_type="DecisionContextFrozen",
                    payload={
                        "decision_id": str(command.decision_id),
                        "case_id": str(command.case_id),
                        "context_id": str(command.context_id),
                        "fingerprint": decision_context.fingerprint,
                        "reference_count": len(command.references),
                    },
                ),
            ),
        )


class ResolveDecisionConditionHandler:
    def __init__(
        self,
        *,
        repository_factory: Callable[[Any], DecisionRepository],
        condition_repository: DecisionConditionRepository,
    ) -> None:
        self._repository_factory = repository_factory
        self._condition_repository = condition_repository

    def execute(
        self, *, session, command: ResolveDecisionConditionCommand, context: CommandContext
    ) -> HandlerOutcome:
        repository = self._repository_factory(session)
        snapshot = repository.get(tenant_id=context.tenant_id, aggregate_id=command.decision_id)
        if snapshot is None or snapshot.root.case_id != command.case_id:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if snapshot.root.outcome != "CONDITIONAL_GO" or snapshot.root.lifecycle != "FINALIZED":
            raise CommandExecutionError("DECISION_NOT_CONDITIONAL_GO")
        condition_index = next(
            (
                index
                for index, item in enumerate(snapshot.conditions)
                if item.id == command.condition_id
            ),
            None,
        )
        if condition_index is None:
            raise CommandExecutionError("DECISION_CONDITION_NOT_FOUND")
        condition = snapshot.conditions[condition_index]
        if condition.status != "OPEN":
            raise CommandExecutionError("DECISION_CONDITION_ALREADY_RESOLVED")
        if snapshot.root.aggregate_revision != command.expected_revision:
            raise CommandExecutionError("STALE_DECISION_REVISION")
        if command.target_status == "SATISFIED" and not command.evidence_reference:
            raise CommandExecutionError("CONDITION_EVIDENCE_REQUIRED")
        if command.target_status == "FAILED" and not command.failure_reason:
            raise CommandExecutionError("CONDITION_FAILURE_REASON_REQUIRED")

        statuses = [item.status for item in snapshot.conditions]
        statuses[condition_index] = command.target_status
        condition_status = (
            "FAILED"
            if "FAILED" in statuses
            else "SATISFIED"
            if all(status in {"SATISFIED", "WAIVED"} for status in statuses)
            else "OPEN"
        )
        new_revision = command.expected_revision + 1
        try:
            self._condition_repository.transition(
                session=session,
                draft=DecisionConditionTransitionDraft(
                    id=command.transition_id,
                    tenant_id=UUID(str(context.tenant_id)),
                    decision_id=command.decision_id,
                    condition_id=command.condition_id,
                    from_status="OPEN",
                    to_status=command.target_status,
                    satisfied_evidence_ref_json=(
                        {
                            "reference": command.evidence_reference.strip(),
                            "recorded_at": context.received_at.isoformat(),
                        }
                        if command.evidence_reference
                        else None
                    ),
                    failure_reason=command.failure_reason.strip()
                    if command.failure_reason
                    else None,
                    aggregate_revision=new_revision,
                    actor_id=UUID(str(context.actor_id)),
                    membership_id=UUID(str(context.membership_id)),
                    command_id=UUID(str(command.command_id)),
                    idempotency_key=UUID(str(command.idempotency_key)),
                    correlation_id=(
                        UUID(str(command.correlation_id)) if command.correlation_id else None
                    ),
                ),
            )
        except ValueError as error:
            raise CommandExecutionError("DECISION_CONDITION_ALREADY_RESOLVED") from error
        try:
            persisted_revision = repository.update_root(
                tenant_id=context.tenant_id,
                aggregate_id=command.decision_id,
                expected_revision=command.expected_revision,
                changes={
                    "condition_status": condition_status,
                    "updated_by_actor_id": context.actor_id,
                },
            )
        except OptimisticRevisionConflictError as error:
            raise CommandExecutionError("STALE_DECISION_REVISION") from error
        return HandlerOutcome(
            result_code="DECISION_CONDITION_RESOLVED",
            aggregate_refs=(
                {
                    "aggregate_type": "Decision",
                    "aggregate_id": str(command.decision_id),
                    "aggregate_revision": persisted_revision,
                },
                {
                    "aggregate_type": "DecisionCondition",
                    "aggregate_id": str(command.condition_id),
                    "aggregate_revision": persisted_revision,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="Decision",
                    aggregate_id=command.decision_id,
                    aggregate_revision=persisted_revision,
                    event_type="DecisionConditionResolved",
                    payload={
                        "decision_id": str(command.decision_id),
                        "condition_id": str(command.condition_id),
                        "status": command.target_status,
                        "condition_status": condition_status,
                    },
                ),
            ),
        )


def decision_lifecycle_handlers(
    *,
    lifecycle_repository: DecisionLifecycleRepository,
    repository_factory: Callable[[Any], DecisionRepository],
    condition_repository: DecisionConditionRepository,
) -> dict[str, CommandHandler]:
    return {
        CreateDecisionCommand.command_type: CreateDecisionHandler(repository=lifecycle_repository),
        FreezeDecisionContextCommand.command_type: FreezeDecisionContextHandler(
            lifecycle_repository=lifecycle_repository,
            repository_factory=repository_factory,
        ),
        ResolveDecisionConditionCommand.command_type: ResolveDecisionConditionHandler(
            repository_factory=repository_factory,
            condition_repository=condition_repository,
        ),
    }


def _reference_token(aggregate_type: str, aggregate_id: UUID, revision: int, role: str) -> str:
    return f"{aggregate_type}:{aggregate_id}:{revision}:{role}"


def _reference_id(reference) -> UUID:
    return UUID(
        sha256(
            _reference_token(
                reference.aggregate_type,
                reference.aggregate_id,
                reference.aggregate_revision,
                reference.reference_role,
            ).encode("utf-8")
        ).hexdigest()[:32]
    )


def _sha256_json(value: dict[str, object]) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()
