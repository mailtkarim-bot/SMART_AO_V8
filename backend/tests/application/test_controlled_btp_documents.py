from __future__ import annotations

from datetime import date
from uuid import uuid4

from app.modules.preparation.application.document_content import (
    ControlledDocumentKind,
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


def test_controlled_document_is_deterministic_and_explicitly_non_binding() -> None:
    case_id = uuid4()
    dce_version_id = uuid4()
    kwargs = {
        "kind": ControlledDocumentKind.DC2,
        "case_id": case_id,
        "dce_version_id": dce_version_id,
        "document_version": 1,
        "facts": {"legal_name": "Entreprise Exemple", "turnover": ""},
        "blockers": ("ENTERPRISE_DOCUMENT_KBIS_NOT_VALIDATED",),
    }

    first = build_controlled_btp_document(**kwargs)
    second = build_controlled_btp_document(**kwargs)

    assert first == second
    assert first.kind is ControlledDocumentKind.DC2
    assert "Document de préparation non contractuel" in first.content
    assert "Entreprise Exemple" in first.content
    assert "[À COMPLÉTER]" in first.content
    assert "ENTERPRISE_DOCUMENT_KBIS_NOT_VALIDATED" in first.content
