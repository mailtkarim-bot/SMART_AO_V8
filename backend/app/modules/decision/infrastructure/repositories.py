"""SQLAlchemy adapter for the Decision application port."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Session

from app.modules.decision.application.ports import (
    DecisionConditionSnapshot,
    DecisionContextDraft,
    DecisionContextReferenceDraft,
    DecisionContextReferenceSnapshot,
    DecisionContextSnapshot,
    DecisionDraft,
    DecisionLifecycleRepository,
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

_CASES_TABLE = sa.table(
    "cases",
    sa.column("id", PG_UUID(as_uuid=True)),
    sa.column("tenant_id", PG_UUID(as_uuid=True)),
    sa.column("aggregate_revision", sa.Integer),
    sa.column("scope_fingerprint", sa.String(64)),
    sa.column("applicable_dce_version_id", PG_UUID(as_uuid=True)),
    sa.column("lifecycle", sa.String(32)),
)
_DCE_VERSIONS_TABLE = sa.table(
    "dce_versions",
    sa.column("id", PG_UUID(as_uuid=True)),
    sa.column("tenant_id", PG_UUID(as_uuid=True)),
    sa.column("aggregate_revision", sa.Integer),
    sa.column("corpus_hash", sa.String(64)),
    sa.column("lifecycle", sa.String(32)),
)
_DCE_REQUIREMENTS_TABLE = sa.table(
    "dce_requirements",
    sa.column("id", PG_UUID(as_uuid=True)),
    sa.column("tenant_id", PG_UUID(as_uuid=True)),
    sa.column("dce_version_id", PG_UUID(as_uuid=True)),
)
_DCE_REQUIREMENT_CONFIRMATIONS_CURRENT_TABLE = sa.table(
    "dce_requirement_confirmation_current",
    sa.column("requirement_id", PG_UUID(as_uuid=True)),
    sa.column("tenant_id", PG_UUID(as_uuid=True)),
    sa.column("revision", sa.Integer),
    sa.column("outcome", sa.String(32)),
)
_DECISION_RISKS_TABLE = sa.table(
    "decision_risks",
    sa.column("id", PG_UUID(as_uuid=True)),
    sa.column("tenant_id", PG_UUID(as_uuid=True)),
    sa.column("case_id", PG_UUID(as_uuid=True)),
    sa.column("dce_version_id", PG_UUID(as_uuid=True)),
)
_PRICING_SCENARIOS_TABLE = sa.table(
    "pricing_scenarios",
    sa.column("id", PG_UUID(as_uuid=True)),
    sa.column("tenant_id", PG_UUID(as_uuid=True)),
    sa.column("case_id", PG_UUID(as_uuid=True)),
    sa.column("version", sa.Integer),
    sa.column("state", sa.String(16)),
)


class SqlAlchemyDecisionLifecycleRepository(DecisionLifecycleRepository):
    def case_exists(self, *, session: object, tenant_id: UUID, case_id: UUID) -> bool:
        db_session = cast(Session, session)
        return (
            db_session.scalar(
                sa.select(_CASES_TABLE.c.id).where(
                    _CASES_TABLE.c.tenant_id == tenant_id,
                    _CASES_TABLE.c.id == case_id,
                    _CASES_TABLE.c.lifecycle == "ACTIVE",
                )
            )
            is not None
        )

    def case_scope_fingerprint(
        self, *, session: object, tenant_id: UUID, case_id: UUID
    ) -> str | None:
        db_session = cast(Session, session)
        return db_session.scalar(
            sa.select(_CASES_TABLE.c.scope_fingerprint).where(
                _CASES_TABLE.c.tenant_id == tenant_id,
                _CASES_TABLE.c.id == case_id,
                _CASES_TABLE.c.lifecycle == "ACTIVE",
            )
        )

    def active_decision_exists(
        self, *, session: object, tenant_id: UUID, decision_key_hash: str
    ) -> bool:
        db_session = cast(Session, session)
        return (
            db_session.scalar(
                sa.select(DecisionRecord.id)
                .where(
                    DecisionRecord.tenant_id == tenant_id,
                    DecisionRecord.decision_key_hash == decision_key_hash,
                    DecisionRecord.validity == "CURRENT",
                    DecisionRecord.lifecycle.notin_(("SUPERSEDED", "CANCELLED")),
                )
                .limit(1)
            )
            is not None
        )

    def next_cycle_number(self, *, session: object, tenant_id: UUID, decision_key_hash: str) -> int:
        db_session = cast(Session, session)
        latest = db_session.scalar(
            sa.select(sa.func.max(DecisionRecord.cycle_number)).where(
                DecisionRecord.tenant_id == tenant_id,
                DecisionRecord.decision_key_hash == decision_key_hash,
            )
        )
        return int(latest or 0) + 1

    def create_root(self, *, session: object, draft: DecisionDraft) -> None:
        db_session = cast(Session, session)
        db_session.add(
            DecisionRecord(
                id=draft.id,
                tenant_id=draft.tenant_id,
                aggregate_revision=0,
                decision_type=draft.decision_type,
                subject_type=draft.subject_type,
                subject_id=draft.subject_id,
                case_id=draft.case_id,
                scope_fingerprint=draft.scope_fingerprint,
                decision_key_hash=draft.decision_key_hash,
                cycle_number=draft.cycle_number,
                lifecycle="DRAFT",
                outcome="UNDECIDED",
                validity="CURRENT",
                condition_status="NOT_APPLICABLE",
                context_status="INCOMPLETE",
                selected_final_context_id=None,
                successor_decision_id=None,
                final_justification=None,
                finalized_by_actor_id=None,
                finalized_at=None,
                review_required_reason=None,
                review_required_at=None,
                cancel_reason=None,
                cancelled_at=None,
                created_by_actor_id=draft.actor_id,
                updated_by_actor_id=draft.actor_id,
            )
        )

    def case_has_applicable_dce(
        self, *, session: object, tenant_id: UUID, case_id: UUID
    ) -> bool:
        db_session = cast(Session, session)
        return (
            db_session.scalar(
                sa.select(_DCE_VERSIONS_TABLE.c.id)
                .join(
                    _CASES_TABLE,
                    sa.and_(
                        _CASES_TABLE.c.tenant_id == _DCE_VERSIONS_TABLE.c.tenant_id,
                        _CASES_TABLE.c.applicable_dce_version_id == _DCE_VERSIONS_TABLE.c.id,
                    ),
                )
                .where(
                    _CASES_TABLE.c.tenant_id == tenant_id,
                    _CASES_TABLE.c.id == case_id,
                    _DCE_VERSIONS_TABLE.c.lifecycle == "ADMITTED",
                )
            )
            is not None
        )

    def context_reference_is_valid(
        self,
        *,
        session: object,
        tenant_id: UUID,
        case_id: UUID,
        aggregate_type: str,
        aggregate_id: UUID,
        aggregate_revision: int,
        content_hash: str | None,
    ) -> bool:
        db_session = cast(Session, session)
        if aggregate_type == "CASE":
            if content_hash is not None:
                return False
            return (
                db_session.scalar(
                    sa.select(_CASES_TABLE.c.id).where(
                        _CASES_TABLE.c.tenant_id == tenant_id,
                        _CASES_TABLE.c.id == case_id,
                        _CASES_TABLE.c.id == aggregate_id,
                        _CASES_TABLE.c.aggregate_revision == aggregate_revision,
                        _CASES_TABLE.c.lifecycle == "ACTIVE",
                    )
                )
                is not None
            )

        if aggregate_type == "DCE_VERSION":
            statement = (
                sa.select(_DCE_VERSIONS_TABLE.c.id)
                .join(
                    _CASES_TABLE,
                    sa.and_(
                        _CASES_TABLE.c.tenant_id == _DCE_VERSIONS_TABLE.c.tenant_id,
                        _CASES_TABLE.c.applicable_dce_version_id == _DCE_VERSIONS_TABLE.c.id,
                    ),
                )
                .where(
                    _DCE_VERSIONS_TABLE.c.tenant_id == tenant_id,
                    _DCE_VERSIONS_TABLE.c.id == aggregate_id,
                    _CASES_TABLE.c.id == case_id,
                    _DCE_VERSIONS_TABLE.c.aggregate_revision == aggregate_revision,
                    _DCE_VERSIONS_TABLE.c.lifecycle == "ADMITTED",
                )
            )
            if content_hash is not None:
                statement = statement.where(
                    sa.func.lower(_DCE_VERSIONS_TABLE.c.corpus_hash) == content_hash.lower()
                )
            return db_session.scalar(statement) is not None

        if aggregate_type == "DCE_REQUIREMENT":
            if content_hash is not None:
                return False
            return (
                db_session.scalar(
                    sa.select(_DCE_REQUIREMENTS_TABLE.c.id)
                    .join(
                        _CASES_TABLE,
                        sa.and_(
                            _CASES_TABLE.c.tenant_id == _DCE_REQUIREMENTS_TABLE.c.tenant_id,
                            _CASES_TABLE.c.applicable_dce_version_id
                            == _DCE_REQUIREMENTS_TABLE.c.dce_version_id,
                        ),
                    )
                    .join(
                        _DCE_REQUIREMENT_CONFIRMATIONS_CURRENT_TABLE,
                        sa.and_(
                            _DCE_REQUIREMENT_CONFIRMATIONS_CURRENT_TABLE.c.tenant_id
                            == _DCE_REQUIREMENTS_TABLE.c.tenant_id,
                            _DCE_REQUIREMENT_CONFIRMATIONS_CURRENT_TABLE.c.requirement_id
                            == _DCE_REQUIREMENTS_TABLE.c.id,
                        ),
                    )
                    .where(
                        _DCE_REQUIREMENTS_TABLE.c.tenant_id == tenant_id,
                        _DCE_REQUIREMENTS_TABLE.c.id == aggregate_id,
                        _CASES_TABLE.c.id == case_id,
                        _DCE_REQUIREMENT_CONFIRMATIONS_CURRENT_TABLE.c.revision
                        == aggregate_revision,
                        _DCE_REQUIREMENT_CONFIRMATIONS_CURRENT_TABLE.c.outcome == "CONFIRMED",
                    )
                )
                is not None
            )

        if aggregate_type == "DECISION_RISK":
            if aggregate_revision != 1 or content_hash is not None:
                return False
            return (
                db_session.scalar(
                    sa.select(_DECISION_RISKS_TABLE.c.id)
                    .join(
                        _CASES_TABLE,
                        sa.and_(
                            _CASES_TABLE.c.tenant_id == _DECISION_RISKS_TABLE.c.tenant_id,
                            _CASES_TABLE.c.id == _DECISION_RISKS_TABLE.c.case_id,
                        ),
                    )
                    .where(
                        _DECISION_RISKS_TABLE.c.tenant_id == tenant_id,
                        _DECISION_RISKS_TABLE.c.id == aggregate_id,
                        _CASES_TABLE.c.id == case_id,
                        _CASES_TABLE.c.lifecycle == "ACTIVE",
                        _CASES_TABLE.c.applicable_dce_version_id
                        == _DECISION_RISKS_TABLE.c.dce_version_id,
                    )
                )
                is not None
            )

        if aggregate_type == "PRICING_SCENARIO":
            if content_hash is not None:
                return False
            return (
                db_session.scalar(
                    sa.select(_PRICING_SCENARIOS_TABLE.c.id).where(
                        _PRICING_SCENARIOS_TABLE.c.tenant_id == tenant_id,
                        _PRICING_SCENARIOS_TABLE.c.id == aggregate_id,
                        _PRICING_SCENARIOS_TABLE.c.case_id == case_id,
                        _PRICING_SCENARIOS_TABLE.c.version == aggregate_revision,
                        _PRICING_SCENARIOS_TABLE.c.state != "ARCHIVED",
                    )
                )
                is not None
            )

        return False

    def create_context(
        self,
        *,
        session: object,
        context: DecisionContextDraft,
        references: tuple[DecisionContextReferenceDraft, ...],
    ) -> None:
        db_session = cast(Session, session)
        db_session.add(
            DecisionContextRecord(
                id=context.id,
                tenant_id=context.tenant_id,
                decision_id=context.decision_id,
                sequence_number=context.sequence_number,
                context_fingerprint=context.context_fingerprint,
                canonical_context_json=dict(context.canonical_context_json),
                rationale=context.rationale,
                unknowns_json=list(context.unknowns_json),
                prepared_at=context.prepared_at,
                context_state="FROZEN",
                is_selected_final=False,
                prepared_by_actor_id=context.prepared_by_actor_id,
            )
        )
        db_session.add_all(
            [
                DecisionContextReferenceRecord(
                    id=reference.id,
                    tenant_id=reference.tenant_id,
                    decision_context_id=reference.decision_context_id,
                    aggregate_type=reference.aggregate_type,
                    aggregate_id=reference.aggregate_id,
                    aggregate_revision=reference.aggregate_revision,
                    content_hash=reference.content_hash,
                    reference_role=reference.reference_role,
                )
                for reference in references
            ]
        )


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
                        DecisionContextRecord.tenant_id == DecisionContextReferenceRecord.tenant_id,
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
