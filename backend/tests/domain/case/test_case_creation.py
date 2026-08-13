from dataclasses import fields
from uuid import uuid4

import pytest
from app.modules.case.domain.case import (
    AggregateReference,
    Case,
    CaseCreated,
    CaseLifecycle,
    CaseOrigin,
    CaseScope,
    CaseStage,
    DceFreshness,
    DecisionReadiness,
    ResponsibilityStatus,
)
from app.modules.case.domain.errors import CaseScopeAmbiguousError, CrossTenantReferenceError


def test_case_created_from_explicit_single_lot_scope_is_active_in_intake() -> None:
    tenant_id = uuid4()
    case = Case.create(
        case_id=uuid4(),
        tenant_id=tenant_id,
        title="Réhabilitation centre technique — lot 01",
        object_description="Création d'une affaire de test pour le gros œuvre.",
        scope=CaseScope.single_lot("01"),
        origin=CaseOrigin.manual("Affaire créée par le patron après identification du DCE."),
    )

    assert case.tenant_id == tenant_id
    assert case.lifecycle is CaseLifecycle.ACTIVE
    assert case.commercial_stage is CaseStage.INTAKE
    assert case.decision_readiness is DecisionReadiness.NOT_ASSESSED
    assert case.dce_freshness is DceFreshness.NO_DCE
    assert case.responsibility_status is ResponsibilityStatus.UNASSIGNED
    assert case.aggregate_revision == 0
    assert case.consultation_reference is None
    assert case.pending_events == (CaseCreated(case_id=case.id, tenant_id=tenant_id),)


@pytest.mark.parametrize(
    ("scope", "expected_message"),
    [
        (CaseScope.multi_lot(("01",), "Réponse groupée"), "at least two lots"),
        (CaseScope.multi_lot(("01", "02"), ""), "source justification"),
        (CaseScope.tranche(""), "tranche reference"),
        (CaseScope.variant(""), "variant reference"),
    ],
)
def test_case_rejects_ambiguous_scope(scope: CaseScope, expected_message: str) -> None:
    with pytest.raises(CaseScopeAmbiguousError, match=expected_message):
        Case.create(
            case_id=uuid4(),
            tenant_id=uuid4(),
            title="Affaire avec périmètre ambigu",
            object_description="La création doit refuser toute portée non justifiée.",
            scope=scope,
            origin=CaseOrigin.manual("Test d'invariant CASE-INV-02."),
        )


def test_case_links_consultation_from_same_tenant_without_changing_stage() -> None:
    tenant_id = uuid4()
    case = Case.create(
        case_id=uuid4(),
        tenant_id=tenant_id,
        title="Extension atelier communal — lot 01",
        object_description="Affaire créée pour vérifier une référence Consultation.",
        scope=CaseScope.single_lot("01"),
        origin=CaseOrigin.manual("Création manuelle justifiée."),
    )
    consultation = AggregateReference(
        aggregate_id=uuid4(),
        aggregate_type="CONSULTATION",
        tenant_id=tenant_id,
        aggregate_revision=3,
    )

    case.register_consultation_link(consultation)

    assert case.consultation_reference == consultation
    assert case.commercial_stage is CaseStage.INTAKE
    assert case.aggregate_revision == 1


def test_case_rejects_cross_tenant_consultation_reference_without_mutating_state() -> None:
    case_tenant_id = uuid4()
    case = Case.create(
        case_id=uuid4(),
        tenant_id=case_tenant_id,
        title="Réfection école — lot 02",
        object_description="Affaire isolée par tenant.",
        scope=CaseScope.single_lot("02"),
        origin=CaseOrigin.manual("Création manuelle justifiée."),
    )
    foreign_consultation = AggregateReference(
        aggregate_id=uuid4(),
        aggregate_type="CONSULTATION",
        tenant_id=uuid4(),
        aggregate_revision=0,
    )

    with pytest.raises(CrossTenantReferenceError):
        case.register_consultation_link(foreign_consultation)

    assert case.tenant_id == case_tenant_id
    assert case.consultation_reference is None
    assert case.aggregate_revision == 0


def test_case_does_not_own_financial_or_cross_aggregate_state() -> None:
    forbidden_owned_attributes = {
        "pricing",
        "pricing_scenario",
        "official_pricing_version",
        "decision",
        "task",
        "tasks",
        "dce_document",
        "dce_documents",
        "evidence",
        "submission",
        "submission_package",
    }
    case_field_names = {field.name for field in fields(Case)}

    assert forbidden_owned_attributes.isdisjoint(case_field_names)
    assert "consultation_reference" in case_field_names
    assert "applicable_dce_version_reference" in case_field_names
