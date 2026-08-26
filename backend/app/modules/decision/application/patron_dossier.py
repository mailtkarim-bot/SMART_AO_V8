from dataclasses import dataclass
from uuid import UUID

from app.modules.decision.application.queries import DecisionDossierReader
from app.platform.security.authorization import (
    AuthorizationPolicyPort,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext, ActorKind, DataClassification


@dataclass(frozen=True, slots=True)
class PatronDecisionDossier:
    decision_id: UUID
    aggregate_revision: int
    case_id: UUID
    decision_type: str
    lifecycle: str
    outcome: str
    validity: str
    context_status: str
    final_justification: str | None
    known: tuple[object, ...]
    unknowns: tuple[object, ...]
    risks: tuple[object, ...]
    conditions: tuple[dict[str, object], ...]
    sources: tuple[dict[str, object], ...]
    context_fingerprint: str | None = None


class PatronDecisionDossierService:
    """Read-only patron projection of one frozen decision context."""

    def __init__(self, *, reader: DecisionDossierReader, policy: AuthorizationPolicyPort) -> None:
        self._reader = reader
        self._policy = policy

    def read(self, *, actor: ActorContext, case_id: UUID, now) -> PatronDecisionDossier:
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("PATRON_REQUIRED")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.DECISION_FINALIZE,
                resource=AuthorizationResource(
                    resource_type="DECISION_DOSSIER",
                    resource_id=case_id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                    case_id=case_id,
                ),
                evaluated_at=now,
            ),
        )
        if not decision.allowed:
            raise PermissionError(decision.code)

        lookup = self._reader.read(tenant_id=actor.tenant_id, case_id=case_id)
        if lookup.decision is None:
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        if lookup.context is None:
            return PatronDecisionDossier(
                decision_id=lookup.decision.id,
                aggregate_revision=lookup.decision.aggregate_revision,
                case_id=lookup.decision.case_id,
                decision_type=lookup.decision.decision_type,
                lifecycle=lookup.decision.lifecycle,
                outcome=lookup.decision.outcome,
                validity=lookup.decision.validity,
                context_status=lookup.decision.context_status,
                final_justification=lookup.decision.final_justification,
                known=(),
                unknowns=(),
                risks=(),
                conditions=(),
                sources=(),
                context_fingerprint=None,
            )

        canonical = lookup.context.canonical_context_json
        return PatronDecisionDossier(
            decision_id=lookup.decision.id,
            aggregate_revision=lookup.decision.aggregate_revision,
            case_id=lookup.decision.case_id,
            decision_type=lookup.decision.decision_type,
            lifecycle=lookup.decision.lifecycle,
            outcome=lookup.decision.outcome,
            validity=lookup.decision.validity,
            context_status=lookup.decision.context_status,
            final_justification=lookup.decision.final_justification,
            known=_as_tuple(canonical.get("known", canonical.get("references", []))),
            unknowns=lookup.context.unknowns_json,
            risks=_as_tuple(canonical.get("risks", [])),
            conditions=tuple(
                {
                    "condition_id": str(item.id),
                    "label": item.label,
                    "status": item.status,
                    "due_at": item.due_at.isoformat() if item.due_at else None,
                    "failure_consequence": item.failure_consequence,
                }
                for item in lookup.conditions
            ),
            sources=tuple(
                {
                    "aggregate_type": item.aggregate_type,
                    "aggregate_id": str(item.aggregate_id),
                    "aggregate_revision": item.aggregate_revision,
                    "role": item.reference_role,
                }
                for item in lookup.references
            ),
            context_fingerprint=lookup.context.context_fingerprint,
        )


def _as_tuple(value: object) -> tuple[object, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(value)
    return ()
