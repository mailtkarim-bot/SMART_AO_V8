from dataclasses import dataclass
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.decision.infrastructure.models.decision import (
    DecisionConditionRecord,
    DecisionContextRecord,
    DecisionContextReferenceRecord,
    DecisionRecord,
)
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


class PatronDecisionDossierService:
    """Read-only patron projection of one frozen decision context."""

    def __init__(
        self, *, session_factory: sessionmaker[Session], policy: AuthorizationPolicyPort
    ) -> None:
        self._session_factory = session_factory
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
        with self._session_factory() as session:
            record = session.scalar(
                sa.select(DecisionRecord)
                .where(
                    DecisionRecord.tenant_id == actor.tenant_id,
                    DecisionRecord.case_id == case_id,
                    DecisionRecord.validity == "CURRENT",
                )
                .order_by(DecisionRecord.cycle_number.desc(), DecisionRecord.updated_at.desc())
                .limit(1)
            )
            if record is None:
                raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
            context = session.scalar(
                sa.select(DecisionContextRecord)
                .where(
                    DecisionContextRecord.tenant_id == actor.tenant_id,
                    DecisionContextRecord.decision_id == record.id,
                    DecisionContextRecord.is_selected_final.is_(True),
                )
                .order_by(DecisionContextRecord.sequence_number.desc())
                .limit(1)
            )
            if context is None:
                context = session.scalar(
                    sa.select(DecisionContextRecord)
                    .where(
                        DecisionContextRecord.tenant_id == actor.tenant_id,
                        DecisionContextRecord.decision_id == record.id,
                    )
                    .order_by(DecisionContextRecord.sequence_number.desc())
                    .limit(1)
                )
            if context is None:
                raise PermissionError("DECISION_CONTEXT_NOT_FOUND")
            references = tuple(
                {
                    "aggregate_type": item.aggregate_type,
                    "aggregate_id": str(item.aggregate_id),
                    "aggregate_revision": item.aggregate_revision,
                    "role": item.reference_role,
                }
                for item in session.scalars(
                    sa.select(DecisionContextReferenceRecord).where(
                        DecisionContextReferenceRecord.tenant_id == actor.tenant_id,
                        DecisionContextReferenceRecord.decision_context_id == context.id,
                    )
                ).all()
            )
            conditions = tuple(
                {
                    "condition_id": str(item.id),
                    "label": item.label,
                    "status": item.status,
                    "due_at": item.due_at.isoformat() if item.due_at else None,
                    "failure_consequence": item.failure_consequence,
                }
                for item in session.scalars(
                    sa.select(DecisionConditionRecord).where(
                        DecisionConditionRecord.tenant_id == actor.tenant_id,
                        DecisionConditionRecord.decision_id == record.id,
                    )
                ).all()
            )
            canonical = context.canonical_context_json
            return PatronDecisionDossier(
                decision_id=record.id,
                case_id=record.case_id,
                decision_type=record.decision_type,
                lifecycle=record.lifecycle,
                outcome=record.outcome,
                validity=record.validity,
                context_status=record.context_status,
                final_justification=record.final_justification,
                known=tuple(canonical.get("known", canonical.get("references", []))),
                unknowns=tuple(context.unknowns_json),
                risks=tuple(canonical.get("risks", [])),
                conditions=conditions,
                sources=references,
            )
