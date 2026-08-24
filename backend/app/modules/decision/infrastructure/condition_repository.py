from __future__ import annotations

from typing import cast

from sqlalchemy.orm import Session

from app.modules.decision.application.ports import (
    DecisionConditionDraft,
    DecisionConditionRepository,
)
from app.modules.decision.infrastructure.models.decision import DecisionConditionRecord


class SqlAlchemyDecisionConditionRepository(DecisionConditionRepository):
    """Persists the initial immutable condition set for a finalized Decision."""

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
