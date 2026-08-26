from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.decision.application.queries import (
    DecisionDossierCondition,
    DecisionDossierContext,
    DecisionDossierDecision,
    DecisionDossierLookup,
    DecisionDossierReference,
)
from app.modules.decision.infrastructure.models.decision import (
    DecisionConditionRecord,
    DecisionContextRecord,
    DecisionContextReferenceRecord,
    DecisionRecord,
)


class SqlAlchemyDecisionDossierReader:
    """SQLAlchemy adapter for the tenant-scoped patron decision dossier."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def read(self, *, tenant_id: UUID, case_id: UUID) -> DecisionDossierLookup:
        with self._session_factory() as session:
            record = session.scalar(
                sa.select(DecisionRecord)
                .where(
                    DecisionRecord.tenant_id == tenant_id,
                    DecisionRecord.case_id == case_id,
                    DecisionRecord.validity == "CURRENT",
                )
                .order_by(DecisionRecord.cycle_number.desc(), DecisionRecord.updated_at.desc())
                .limit(1)
            )
            if record is None:
                return DecisionDossierLookup(
                    decision=None,
                    context=None,
                    references=(),
                    conditions=(),
                )

            decision = DecisionDossierDecision(
                id=record.id,
                aggregate_revision=record.aggregate_revision,
                case_id=record.case_id,
                decision_type=record.decision_type,
                lifecycle=record.lifecycle,
                outcome=record.outcome,
                validity=record.validity,
                context_status=record.context_status,
                final_justification=record.final_justification,
            )
            context = session.scalar(
                sa.select(DecisionContextRecord)
                .where(
                    DecisionContextRecord.tenant_id == tenant_id,
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
                        DecisionContextRecord.tenant_id == tenant_id,
                        DecisionContextRecord.decision_id == record.id,
                    )
                    .order_by(DecisionContextRecord.sequence_number.desc())
                    .limit(1)
                )
            if context is None:
                return DecisionDossierLookup(
                    decision=decision,
                    context=None,
                    references=(),
                    conditions=(),
                )

            references = tuple(
                DecisionDossierReference(
                    aggregate_type=item.aggregate_type,
                    aggregate_id=item.aggregate_id,
                    aggregate_revision=item.aggregate_revision,
                    reference_role=item.reference_role,
                )
                for item in session.scalars(
                    sa.select(DecisionContextReferenceRecord)
                    .where(
                        DecisionContextReferenceRecord.tenant_id == tenant_id,
                        DecisionContextReferenceRecord.decision_context_id == context.id,
                    )
                    .order_by(DecisionContextReferenceRecord.id)
                ).all()
            )
            conditions = tuple(
                DecisionDossierCondition(
                    id=item.id,
                    label=item.label,
                    status=item.status,
                    due_at=item.due_at,
                    failure_consequence=item.failure_consequence,
                )
                for item in session.scalars(
                    sa.select(DecisionConditionRecord)
                    .where(
                        DecisionConditionRecord.tenant_id == tenant_id,
                        DecisionConditionRecord.decision_id == record.id,
                    )
                    .order_by(DecisionConditionRecord.id)
                ).all()
            )
            return DecisionDossierLookup(
                decision=decision,
                context=DecisionDossierContext(
                    id=context.id,
                    canonical_context_json=context.canonical_context_json,
                    unknowns_json=tuple(context.unknowns_json),
                    context_fingerprint=context.context_fingerprint,
                ),
                references=references,
                conditions=conditions,
            )
