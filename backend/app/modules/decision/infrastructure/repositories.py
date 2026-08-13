"""SQLAlchemy adapter for the Decision application port."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.decision.application.ports import (
    DecisionConditionSnapshot,
    DecisionContextReferenceSnapshot,
    DecisionContextSnapshot,
    DecisionRepository,
    DecisionRootSnapshot,
    DecisionSnapshot,
)
from app.modules.decision.infrastructure.models.decision import (
    DecisionConditionRecord,
    DecisionContextRecord,
    DecisionContextReferenceRecord,
    DecisionRecord,
)
from app.platform.persistence.repository import update_root_with_expected_revision


class SqlAlchemyDecisionRepository(DecisionRepository):
    """Loads and updates only Decision state and Decision-owned entities."""

    _MUTABLE_ROOT_COLUMNS = frozenset(
        {
            "lifecycle",
            "outcome",
            "validity",
            "condition_status",
            "context_status",
            "selected_final_context_id",
            "successor_decision_id",
            "final_justification",
            "finalized_by_actor_id",
            "finalized_at",
            "review_required_reason",
            "review_required_at",
            "cancel_reason",
            "cancelled_at",
            "updated_by_actor_id",
        }
    )

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, *, tenant_id: UUID | str, aggregate_id: UUID | str) -> DecisionSnapshot | None:
        root = self._session.scalar(
            sa.select(DecisionRecord).where(
                DecisionRecord.tenant_id == tenant_id,
                DecisionRecord.id == aggregate_id,
            )
        )
        if root is None:
            return None

        contexts = tuple(
            DecisionContextSnapshot(
                id=record.id,
                sequence_number=record.sequence_number,
                context_fingerprint=record.context_fingerprint,
                canonical_context_json=dict(record.canonical_context_json),
                rationale=record.rationale,
                unknowns_json=tuple(record.unknowns_json),
                prepared_at=record.prepared_at,
                context_state=record.context_state,
                is_selected_final=record.is_selected_final,
            )
            for record in self._session.scalars(
                sa.select(DecisionContextRecord)
                .where(
                    DecisionContextRecord.tenant_id == tenant_id,
                    DecisionContextRecord.decision_id == aggregate_id,
                )
                .order_by(DecisionContextRecord.sequence_number, DecisionContextRecord.id)
            )
        )
        context_references = tuple(
            DecisionContextReferenceSnapshot(
                id=record.id,
                decision_context_id=record.decision_context_id,
                aggregate_type=record.aggregate_type,
                aggregate_id=record.aggregate_id,
                aggregate_revision=record.aggregate_revision,
                content_hash=record.content_hash,
                reference_role=record.reference_role,
            )
            for record in self._session.scalars(
                sa.select(DecisionContextReferenceRecord)
                .join(
                    DecisionContextRecord,
                    sa.and_(
                        DecisionContextRecord.tenant_id
                        == DecisionContextReferenceRecord.tenant_id,
                        DecisionContextRecord.id
                        == DecisionContextReferenceRecord.decision_context_id,
                    ),
                )
                .where(
                    DecisionContextReferenceRecord.tenant_id == tenant_id,
                    DecisionContextRecord.decision_id == aggregate_id,
                )
                .order_by(
                    DecisionContextReferenceRecord.created_at,
                    DecisionContextReferenceRecord.id,
                )
            )
        )
        conditions = tuple(
            DecisionConditionSnapshot(
                id=record.id,
                label=record.label,
                owner_actor_id=record.owner_actor_id,
                due_at=record.due_at,
                due_date_absence_reason=record.due_date_absence_reason,
                failure_consequence=record.failure_consequence,
                status=record.status,
                satisfied_evidence_ref_json=(
                    dict(record.satisfied_evidence_ref_json)
                    if record.satisfied_evidence_ref_json
                    else None
                ),
                failure_reason=record.failure_reason,
                waiver_justification=record.waiver_justification,
            )
            for record in self._session.scalars(
                sa.select(DecisionConditionRecord)
                .where(
                    DecisionConditionRecord.tenant_id == tenant_id,
                    DecisionConditionRecord.decision_id == aggregate_id,
                )
                .order_by(DecisionConditionRecord.created_at, DecisionConditionRecord.id)
            )
        )
        return DecisionSnapshot(
            root=DecisionRootSnapshot(
                id=root.id,
                tenant_id=root.tenant_id,
                aggregate_revision=root.aggregate_revision,
                decision_type=root.decision_type,
                subject_type=root.subject_type,
                subject_id=root.subject_id,
                case_id=root.case_id,
                scope_fingerprint=root.scope_fingerprint,
                decision_key_hash=root.decision_key_hash,
                cycle_number=root.cycle_number,
                lifecycle=root.lifecycle,
                outcome=root.outcome,
                validity=root.validity,
                condition_status=root.condition_status,
                context_status=root.context_status,
                selected_final_context_id=root.selected_final_context_id,
                successor_decision_id=root.successor_decision_id,
                final_justification=root.final_justification,
                finalized_by_actor_id=root.finalized_by_actor_id,
                finalized_at=root.finalized_at,
                review_required_reason=root.review_required_reason,
                review_required_at=root.review_required_at,
                cancel_reason=root.cancel_reason,
                cancelled_at=root.cancelled_at,
            ),
            contexts=contexts,
            context_references=context_references,
            conditions=conditions,
        )

    def update_root(
        self,
        *,
        tenant_id: UUID | str,
        aggregate_id: UUID | str,
        expected_revision: int,
        changes: Mapping[str, object],
    ) -> int:
        return update_root_with_expected_revision(
            self._session,
            table=DecisionRecord.__table__,
            tenant_id=tenant_id,
            aggregate_id=aggregate_id,
            expected_revision=expected_revision,
            changes=changes,
            allowed_columns=self._MUTABLE_ROOT_COLUMNS,
        )
