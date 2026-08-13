from dataclasses import fields
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.modules.dce.domain.dce_version import (
    DceDocument,
    DceIntegrity,
    DceLifecycle,
    DceVersion,
    DceVersionRegistered,
    DceVersionSuperseded,
    DceVersionWithdrawn,
)
from app.modules.dce.domain.errors import (
    DceVersionUnusableError,
    DocumentOriginalImmutableError,
    SourceLocationRequiredError,
)


def _document(document_id=None) -> DceDocument:
    return DceDocument(
        document_id=document_id or uuid4(),
        original_filename="RC.pdf",
        sha256="a" * 64,
        media_type="application/pdf",
        size_bytes=1024,
    )


def _registered_version(*, tenant_id=None, consultation_id=None) -> DceVersion:
    return DceVersion.register(
        dce_version_id=uuid4(),
        tenant_id=tenant_id or uuid4(),
        consultation_id=consultation_id or uuid4(),
        corpus_hash="b" * 64,
        documents=(_document(),),
        provenance="DCE téléchargé depuis la plateforme acheteur",
        received_at=datetime(2026, 8, 13, 9, 0, tzinfo=UTC),
    )


def test_dce_version_admission_creates_immutable_admitted_corpus() -> None:
    dce_version = _registered_version()

    assert dce_version.lifecycle is DceLifecycle.ADMITTED
    assert dce_version.integrity is DceIntegrity.VERIFIED
    assert dce_version.aggregate_revision == 0
    assert len(dce_version.documents) == 1
    assert dce_version.pending_events == (
        DceVersionRegistered(
            dce_version_id=dce_version.id,
            tenant_id=dce_version.tenant_id,
            consultation_id=dce_version.consultation_id,
            corpus_hash="b" * 64,
        ),
    )


def test_dce_version_rejects_replacement_of_corpus_hash_or_original_documents() -> None:
    dce_version = _registered_version()
    original_revision = dce_version.aggregate_revision
    original_documents = dce_version.documents

    with pytest.raises(DocumentOriginalImmutableError):
        dce_version.replace_admitted_corpus(
            corpus_hash="c" * 64,
            documents=(_document(),),
        )

    assert dce_version.corpus_hash == "b" * 64
    assert dce_version.documents == original_documents
    assert dce_version.aggregate_revision == original_revision


def test_dce_version_declares_sourced_missing_document_as_partial() -> None:
    dce_version = _registered_version()

    dce_version.declare_missing_document(
        expected_family="CCTP",
        reason="Le RC liste un CCTP absent du corpus admis.",
        source_reference="RC page 2",
    )

    assert dce_version.integrity is DceIntegrity.PARTIAL
    assert dce_version.missing_documents[0].expected_family == "CCTP"


def test_dce_version_rejects_missing_document_declaration_without_source_or_reason() -> None:
    dce_version = _registered_version()

    with pytest.raises(SourceLocationRequiredError):
        dce_version.declare_missing_document(
            expected_family="CCTP",
            reason="",
            source_reference="",
        )


def test_rectificatif_creates_new_root_and_supersedes_prior_version_without_rewrite() -> None:
    tenant_id = uuid4()
    consultation_id = uuid4()
    initial = _registered_version(tenant_id=tenant_id, consultation_id=consultation_id)

    rectificatif = DceVersion.register(
        dce_version_id=uuid4(),
        tenant_id=tenant_id,
        consultation_id=consultation_id,
        corpus_hash="c" * 64,
        documents=(_document(),),
        provenance="Rectificatif officiel de l'acheteur",
        received_at=datetime(2026, 8, 14, 9, 0, tzinfo=UTC),
        supersedes_version_id=initial.id,
        supersession_source="Avis rectificatif portail acheteur",
    )
    initial.mark_superseded_by(rectificatif.id)

    assert rectificatif.id != initial.id
    assert rectificatif.supersedes_version_id == initial.id
    assert rectificatif.lifecycle is DceLifecycle.ADMITTED
    assert initial.lifecycle is DceLifecycle.SUPERSEDED
    assert initial.corpus_hash == "b" * 64
    assert DceVersionSuperseded(
        dce_version_id=initial.id,
        superseded_by_version_id=rectificatif.id,
    ) in initial.pending_events


def test_withdrawn_dce_version_remains_auditable_but_cannot_register_source_statement() -> None:
    dce_version = _registered_version()

    dce_version.withdraw(
        reason="Retrait officiel de la consultation par l'acheteur",
        source_reference="Avis de retrait portail acheteur",
    )

    assert dce_version.lifecycle is DceLifecycle.WITHDRAWN
    assert len(dce_version.documents) == 1
    assert DceVersionWithdrawn(dce_version_id=dce_version.id) in dce_version.pending_events
    with pytest.raises(DceVersionUnusableError):
        dce_version.register_source_statement(
            source_statement_id=uuid4(),
            document_id=dce_version.documents[0].document_id,
            locator="page:1",
            excerpt="Extrait de contrôle",
            provenance="Vérification humaine",
        )


def test_dce_version_does_not_own_case_decision_pricing_or_submission() -> None:
    forbidden_owned_attributes = {
        "case",
        "decision",
        "pricing",
        "submission",
        "requirement",
        "source_assertion",
    }
    dce_version_field_names = {field.name for field in fields(DceVersion)}

    assert forbidden_owned_attributes.isdisjoint(dce_version_field_names)
    assert "documents" in dce_version_field_names
    assert "source_statements" in dce_version_field_names
