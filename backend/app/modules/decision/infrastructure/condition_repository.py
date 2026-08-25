from __future__ import annotations

from typing import cast

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.decision.application.ports import (
    DecisionConditionDraft,
    DecisionConditionRepository,
    DecisionConditionTransitionDraft,
)
from app.modules.decision.infrastructure.models.decision import (
    DecisionConditionRecord,
    DecisionConditionTransitionRecord,
)


class SqlAlchemyDecisionConditionRepository(DecisionConditionRepository):
    """Persists initial conditions and append-only condition transitions."""

    def create_many(self, *, session: object, drafts: tuple[DecisionConditionDraft, ...]) -> None:
        db_session = cast(Session, session)
        db_session.add_all(
            [
                DecisionConditionRecord(
                    id=draft.id,
                    tenant_id=draft.tenant_id,
                    decision_id=draft.decision_id,
                    label=draft.label,
                    owner_actor_id=draft.owner_actor_id,
                    due_at=draft.due_at,
                    due_date_absence_reason=draft.due_date_absence_reason,
                    failure_consequence=draft.failure_consequence,
                    status="OPEN",
                )
                for draft in drafts
            ]
        )

    def transition(self, *, session: object, draft: DecisionConditionTransitionDraft) -> None:
        db_session = cast(Session, session)
        condition = db_session.scalar(
            sa.select(DecisionConditionRecord)
            .where(
                DecisionConditionRecord.tenant_id == draft.tenant_id,
                DecisionConditionRecord.decision_id == draft.decision_id,
                DecisionConditionRecord.id == draft.condition_id,
            )
            .with_for_update()
        )
        if condition is None or condition.status != draft.from_status:
            raise ValueError("DECISION_CONDITION_NOT_OPEN")
        condition.status = draft.to_status
        condition.satisfied_evidence_ref_json = (
            dict(draft.satisfied_evidence_ref_json)
            if draft.satisfied_evidence_ref_json is not None
            else None
        )
        condition.failure_reason = draft.failure_reason
        db_session.add(
            DecisionConditionTransitionRecord(
                id=draft.id,
                tenant_id=draft.tenant_id,
                decision_id=draft.decision_id,
                condition_id=draft.condition_id,
                from_status=draft.from_status,
                to_status=draft.to_status,
                satisfied_evidence_ref_json=(
                    dict(draft.satisfied_evidence_ref_json)
                    if draft.satisfied_evidence_ref_json is not None
                    else None
                ),
                failure_reason=draft.failure_reason,
                aggregate_revision=draft.aggregate_revision,
                actor_id=draft.actor_id,
                membership_id=draft.membership_id,
                command_id=draft.command_id,
                idempotency_key=draft.idempotency_key,
                correlation_id=draft.correlation_id,
            )
        )
