from __future__ import annotations

from datetime import date
from uuid import uuid4

from app.modules.preparation.application.document_content import (
    ControlledDocumentKind,
    ControlledDraftServerFacts,
    EnterpriseDocumentFact,
    build_controlled_btp_document,
    cross_match_enterprise_documents,
)


def test_cross_match_returns_only_unvalidated_or_expired_requirements() -> None:
    blockers = cross_match_enterprise_documents(
        required_kinds=("INSURANCE", "KBIS", "RIB"),
        documents=(
            EnterpriseDocumentFact("INSURANCE", "VALIDATED", date(2027, 1, 1)),
            EnterpriseDocumentFact("KBIS", "EXPIRED", date(2025, 1, 1)),
        ),
        as_of=date(2026, 8, 25),
    )

    assert blockers == (
        "ENTERPRISE_DOCUMENT_KBIS_NOT_VALIDATED",
        "ENTERPRISE_DOCUMENT_RIB_NOT_VALIDATED",
    )


def test_controlled_server_facts_use_closed_kind_specific_allowlists() -> None:
    facts = ControlledDraftServerFacts(
        case_id=uuid4(),
        dce_version_id=uuid4(),
        readiness_state="READY_WITH_WARNINGS",
        readiness_revision=4,
        confirmed_requirement_ids=(uuid4(), uuid4()),
        blocker_codes=(),
        warning_codes=("TASK_RESULT_MISSING",),
    )

    dc1 = facts.for_kind(ControlledDocumentKind.DC1)
    dc2 = facts.for_kind(ControlledDocumentKind.DC2)
    dc4 = facts.for_kind(ControlledDocumentKind.DC4)

    assert set(dc1) == {
        "case_id",
        "dce_version_id",
        "readiness_state",
        "readiness_revision",
        "confirmed_requirement_count",
        "blocker_codes",
        "warning_codes",
    }
    assert "confirmed_requirement_ids" in dc2
    assert "scope_policy" in dc4
    assert not any("price" in key.lower() or "legal" in key.lower() for key in dc1)
    assert dc1["confirmed_requirement_count"] == "2"
    assert dc4["scope_policy"] == "DCE_REQUIREMENTS_ONLY"


def test_controlled_document_is_deterministic_and_explicitly_non_binding() -> None:
    case_id = uuid4()
    dce_version_id = uuid4()
    facts = {"legal_name": "Entreprise Exemple", "turnover": ""}
    blockers = ("ENTERPRISE_DOCUMENT_KBIS_NOT_VALIDATED",)

    first = build_controlled_btp_document(
        kind=ControlledDocumentKind.DC2,
        case_id=case_id,
        dce_version_id=dce_version_id,
        document_version=1,
        facts=facts,
        blockers=blockers,
    )
    second = build_controlled_btp_document(
        kind=ControlledDocumentKind.DC2,
        case_id=case_id,
        dce_version_id=dce_version_id,
        document_version=1,
        facts=facts,
        blockers=blockers,
    )

    assert first == second
    assert first.kind is ControlledDocumentKind.DC2
    assert "Document de préparation non contractuel" in first.content
    assert "Entreprise Exemple" in first.content
    assert "[À COMPLÉTER]" in first.content
    assert "ENTERPRISE_DOCUMENT_KBIS_NOT_VALIDATED" in first.content
