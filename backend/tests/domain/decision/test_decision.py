from dataclasses import fields
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.modules.decision.domain.decision import (
    Decision,
    DecisionCondition,
    DecisionConditionStatus,
    DecisionContext,
    DecisionContextStatus,
    DecisionDraftCreated,
    DecisionLifecycle,
    DecisionOutcome,
    DecisionType,
    DecisionValidity,
    GoDecisionApproved,
)
from app.modules.decision.domain.errors import (
    ConditionConsequenceRequiredError,
    ConditionOwnerRequiredError,
    DecisionAlreadyFinalizedError,
    DecisionContextIncompleteError,
    StaleDecisionContextError,
)


def _draft() -> Decision:
    return Decision.create_draft(
        decision_id=uuid4(),
        tenant_id=uuid4(),
        decision_type=DecisionType.GO_NO_GO,
        subject_reference="CASE:7c755bc0-b4d2-44f6-a70c-6d60699999a1",
        scope_fingerprint="scope:single-lot-01",
        created_by="patron:owner",
    )


def _context(*, tenant_id, context_id=None) -> DecisionContext:
    return DecisionContext.build(
        context_id=context_id or uuid4(),
        tenant_id=tenant_id,
        references=(
            "CASE:7c755bc0-b4d2-44f6-a70c-6d60699999a1@3",
            "DCE:33b62675-38b0-4d50-a514-41a22aaaaaa2@1",
            "READINESS:6bf2a6cb-dce1-4260-9ce8-b8e145555555@2",
        ),
        unknowns=("Validation disponibilité chef de chantier",),
        risks=("Risque délai fournisseur à confirmer",),
        prepared_at=datetime(2026, 8, 13, 10, 0, tzinfo=UTC),
    )


def test_decision_draft_is_tenant_scoped_and_incomplete() -> None:
    decision = _draft()

    assert decision.lifecycle is DecisionLifecycle.DRAFT
    assert decision.outcome is DecisionOutcome.UNDECIDED
    assert decision.context_status is DecisionContextStatus.INCOMPLETE
    assert decision.aggregate_revision == 0
    assert decision.pending_events == (
        DecisionDraftCreated(decision_id=decision.id, tenant_id=decision.tenant_id),
    )


def test_prepare_decision_context_freezes_context_and_fingerprint() -> None:
    decision = _draft()
    context = _context(tenant_id=decision.tenant_id)

    decision.prepare_context(context)

    assert decision.lifecycle is DecisionLifecycle.PENDING_PATRON
    assert decision.context_status is DecisionContextStatus.FROZEN
    assert decision.current_context == context
    assert decision.current_context.fingerprint == context.fingerprint
    assert decision.aggregate_revision == 1


def test_prepare_context_rejects_empty_references() -> None:
    decision = _draft()
    incomplete_context = DecisionContext.build(
        context_id=uuid4(),
        tenant_id=decision.tenant_id,
        references=(),
        unknowns=(),
        risks=(),
        prepared_at=datetime(2026, 8, 13, 10, 0, tzinfo=UTC),
    )

    with pytest.raises(DecisionContextIncompleteError):
        decision.prepare_context(incomplete_context)

    assert decision.lifecycle is DecisionLifecycle.DRAFT


def test_approve_go_finalizes_exact_frozen_context() -> None:
    decision = _draft()
    context = _context(tenant_id=decision.tenant_id)
    decision.prepare_context(context)

    decision.approve_go(
        displayed_fingerprint=context.fingerprint,
        justification="Capacité, DCE et risques revus par le patron.",
        approved_by="patron:owner",
        approved_at=datetime(2026, 8, 13, 10, 5, tzinfo=UTC),
    )

    assert decision.lifecycle is DecisionLifecycle.FINALIZED
    assert decision.outcome is DecisionOutcome.GO
    assert decision.validity is DecisionValidity.CURRENT
    assert decision.condition_status is DecisionConditionStatus.NOT_APPLICABLE
    assert GoDecisionApproved(decision_id=decision.id) in decision.pending_events


def test_approve_go_rejects_stale_displayed_fingerprint_without_finalizing() -> None:
    decision = _draft()
    context = _context(tenant_id=decision.tenant_id)
    decision.prepare_context(context)

    with pytest.raises(StaleDecisionContextError):
        decision.approve_go(
            displayed_fingerprint="0" * 64,
            justification="Tentative avec contexte périmé.",
            approved_by="patron:owner",
            approved_at=datetime(2026, 8, 13, 10, 5, tzinfo=UTC),
        )

    assert decision.lifecycle is DecisionLifecycle.PENDING_PATRON
    assert decision.outcome is DecisionOutcome.UNDECIDED


def test_conditional_go_requires_condition_owner() -> None:
    decision = _draft()
    context = _context(tenant_id=decision.tenant_id)
    decision.prepare_context(context)
    condition_without_owner = DecisionCondition.proposed(
        condition_id=uuid4(),
        label="Obtenir l'accord fournisseur sur le délai.",
        owner=None,
        due_at=datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
        due_date_absence_reason=None,
        failure_consequence="Risque délai à réexaminer avant prix.",
    )

    with pytest.raises(ConditionOwnerRequiredError):
        decision.approve_conditional_go(
            displayed_fingerprint=context.fingerprint,
            justification="Go sous réserve fournisseur.",
            conditions=(condition_without_owner,),
            approved_by="patron:owner",
            approved_at=datetime(2026, 8, 13, 10, 5, tzinfo=UTC),
        )


def test_conditional_go_requires_due_date_or_reason_and_failure_consequence() -> None:
    decision = _draft()
    context = _context(tenant_id=decision.tenant_id)
    decision.prepare_context(context)
    invalid_condition = DecisionCondition.proposed(
        condition_id=uuid4(),
        label="Vérifier la capacité du sous-traitant.",
        owner="patron:owner",
        due_at=None,
        due_date_absence_reason=None,
        failure_consequence="",
    )

    with pytest.raises(ConditionConsequenceRequiredError):
        decision.approve_conditional_go(
            displayed_fingerprint=context.fingerprint,
            justification="Go conditionnel.",
            conditions=(invalid_condition,),
            approved_by="patron:owner",
            approved_at=datetime(2026, 8, 13, 10, 5, tzinfo=UTC),
        )


def test_conditional_go_conditions_can_be_satisfied_without_rewriting_outcome() -> None:
    decision = _draft()
    context = _context(tenant_id=decision.tenant_id)
    decision.prepare_context(context)
    condition = DecisionCondition.proposed(
        condition_id=uuid4(),
        label="Obtenir l'accord fournisseur sur le délai.",
        owner="patron:owner",
        due_at=datetime.now(UTC) + timedelta(days=2),
        due_date_absence_reason=None,
        failure_consequence="Réexaminer la décision avant prix.",
    )
    decision.approve_conditional_go(
        displayed_fingerprint=context.fingerprint,
        justification="Go sous réserve fournisseur.",
        conditions=(condition,),
        approved_by="patron:owner",
        approved_at=datetime(2026, 8, 13, 10, 5, tzinfo=UTC),
    )

    decision.record_condition_satisfied(
        condition_id=condition.id,
        evidence_reference="EVIDENCE:ed8b9a96-0798-4704-a0e4-7c1233333333@1",
        observed_at=datetime(2026, 8, 14, 10, 0, tzinfo=UTC),
    )

    assert decision.outcome is DecisionOutcome.CONDITIONAL_GO
    assert decision.condition_status is DecisionConditionStatus.SATISFIED


def test_finalized_decision_rejects_context_replacement() -> None:
    decision = _draft()
    context = _context(tenant_id=decision.tenant_id)
    decision.prepare_context(context)
    decision.approve_no_go(
        displayed_fingerprint=context.fingerprint,
        justification="Capacité indisponible dans le délai imposé.",
        approved_by="patron:owner",
        approved_at=datetime(2026, 8, 13, 10, 5, tzinfo=UTC),
    )

    with pytest.raises(DecisionAlreadyFinalizedError):
        decision.prepare_context(_context(tenant_id=decision.tenant_id))


def test_mark_review_required_preserves_finalized_choice_and_context() -> None:
    decision = _draft()
    context = _context(tenant_id=decision.tenant_id)
    decision.prepare_context(context)
    decision.approve_go(
        displayed_fingerprint=context.fingerprint,
        justification="Dossier validé au moment de la décision.",
        approved_by="patron:owner",
        approved_at=datetime(2026, 8, 13, 10, 5, tzinfo=UTC),
    )

    decision.mark_review_required(reason="Rectificatif DCE impactant le délai.")

    assert decision.outcome is DecisionOutcome.GO
    assert decision.validity is DecisionValidity.REVIEW_REQUIRED
    assert decision.context_status is DecisionContextStatus.STALE
    assert decision.current_context == context


def test_superseded_decision_preserves_history_and_successor_reference() -> None:
    decision = _draft()
    context = _context(tenant_id=decision.tenant_id)
    decision.prepare_context(context)
    decision.approve_no_go(
        displayed_fingerprint=context.fingerprint,
        justification="Refus initial documenté.",
        approved_by="patron:owner",
        approved_at=datetime(2026, 8, 13, 10, 5, tzinfo=UTC),
    )
    successor_id = uuid4()

    decision.supersede(successor_decision_id=successor_id, rationale="Nouvelle analyse complète.")

    assert decision.lifecycle is DecisionLifecycle.SUPERSEDED
    assert decision.validity is DecisionValidity.SUPERSEDED
    assert decision.successor_decision_id == successor_id
    assert decision.current_context == context


def test_decision_does_not_own_case_dce_pricing_task_or_submission() -> None:
    forbidden_owned_attributes = {
        "case",
        "dce_version",
        "pricing",
        "task",
        "submission",
        "source_assertion",
    }
    decision_field_names = {field.name for field in fields(Decision)}

    assert forbidden_owned_attributes.isdisjoint(decision_field_names)
    assert "subject_reference" in decision_field_names
    assert "context_history" in decision_field_names
