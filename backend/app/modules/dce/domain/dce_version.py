"""Pure domain model for a DCE corpus admitted under one Consultation.

A DceVersion owns only its admitted originals, classifications, source anchors
and integrity signals. Parsing, OCR, vectorisation and analytical conclusions
are intentionally outside this aggregate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from .errors import (
    DceVersionUnusableError,
    DocumentOriginalImmutableError,
    SourceLocationRequiredError,
)


class DceLifecycle(StrEnum):
    ADMITTED = "ADMITTED"
    SUPERSEDED = "SUPERSEDED"
    WITHDRAWN = "WITHDRAWN"


class DceIntegrity(StrEnum):
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    UNUSABLE = "UNUSABLE"


class ClassificationReadiness(StrEnum):
    UNCLASSIFIED = "UNCLASSIFIED"
    PARTIALLY_CLASSIFIED = "PARTIALLY_CLASSIFIED"
    CLASSIFIED = "CLASSIFIED"


class AnalysisReadiness(StrEnum):
    NOT_READY = "NOT_READY"
    READY_FOR_ANALYSIS = "READY_FOR_ANALYSIS"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass(frozen=True, slots=True)
class DceDocument:
    document_id: UUID
    original_filename: str
    sha256: str
    media_type: str
    size_bytes: int

    def __post_init__(self) -> None:
        if (
            not self.original_filename.strip()
            or not self.media_type.strip()
            or self.size_bytes <= 0
        ):
            raise DocumentOriginalImmutableError("admitted document metadata is invalid")
        if not _is_sha256(self.sha256):
            raise DocumentOriginalImmutableError("admitted document sha256 must be a valid SHA-256")


@dataclass(frozen=True, slots=True)
class MissingDocument:
    expected_family: str
    reason: str
    source_reference: str


@dataclass(frozen=True, slots=True)
class SourceStatement:
    source_statement_id: UUID
    document_id: UUID
    locator: str
    excerpt: str
    provenance: str


@dataclass(frozen=True, slots=True)
class DceVersionRegistered:
    dce_version_id: UUID
    tenant_id: UUID
    consultation_id: UUID
    corpus_hash: str


@dataclass(frozen=True, slots=True)
class DceDocumentMissingDeclared:
    dce_version_id: UUID
    expected_family: str


@dataclass(frozen=True, slots=True)
class DceVersionSuperseded:
    dce_version_id: UUID
    superseded_by_version_id: UUID


@dataclass(frozen=True, slots=True)
class DceVersionWithdrawn:
    dce_version_id: UUID


@dataclass(frozen=True, slots=True)
class DceSourceStatementRegistered:
    dce_version_id: UUID
    source_statement_id: UUID


@dataclass(slots=True)
class DceVersion:
    """DCE aggregate root with immutable admitted corpus and originals."""

    id: UUID
    tenant_id: UUID
    consultation_id: UUID
    corpus_hash: str
    documents: tuple[DceDocument, ...]
    provenance: str
    received_at: datetime
    supersedes_version_id: UUID | None = None
    supersession_source: str | None = None
    lifecycle: DceLifecycle = DceLifecycle.ADMITTED
    integrity: DceIntegrity = DceIntegrity.VERIFIED
    classification_readiness: ClassificationReadiness = ClassificationReadiness.UNCLASSIFIED
    analysis_readiness: AnalysisReadiness = AnalysisReadiness.NOT_READY
    missing_documents: list[MissingDocument] = field(default_factory=list)
    source_statements: list[SourceStatement] = field(default_factory=list)
    aggregate_revision: int = 0
    _pending_events: list[object] = field(default_factory=list, repr=False)

    @classmethod
    def register(
        cls,
        *,
        dce_version_id: UUID,
        tenant_id: UUID,
        consultation_id: UUID,
        corpus_hash: str,
        documents: tuple[DceDocument, ...],
        provenance: str,
        received_at: datetime,
        supersedes_version_id: UUID | None = None,
        supersession_source: str | None = None,
    ) -> DceVersion:
        normalized_corpus_hash = corpus_hash.lower()
        if not _is_sha256(normalized_corpus_hash):
            raise DocumentOriginalImmutableError("DCE corpus hash must be a valid SHA-256")
        if not documents:
            raise DocumentOriginalImmutableError(
                "DCE version requires at least one admitted original"
            )
        if not provenance.strip():
            raise SourceLocationRequiredError("DCE version requires provenance")
        if supersedes_version_id is not None and not (supersession_source or "").strip():
            raise SourceLocationRequiredError("rectificatif requires supersession source")
        document_ids = [document.document_id for document in documents]
        if len(document_ids) != len(set(document_ids)):
            raise DocumentOriginalImmutableError(
                "DCE version contains duplicate document identifiers"
            )

        version = cls(
            id=dce_version_id,
            tenant_id=tenant_id,
            consultation_id=consultation_id,
            corpus_hash=normalized_corpus_hash,
            documents=documents,
            provenance=provenance.strip(),
            received_at=received_at,
            supersedes_version_id=supersedes_version_id,
            supersession_source=supersession_source.strip() if supersession_source else None,
        )
        version._record(
            DceVersionRegistered(
                dce_version_id=version.id,
                tenant_id=version.tenant_id,
                consultation_id=version.consultation_id,
                corpus_hash=version.corpus_hash,
            )
        )
        return version

    @property
    def pending_events(self) -> tuple[object, ...]:
        return tuple(self._pending_events)

    def replace_admitted_corpus(
        self,
        *,
        corpus_hash: str,
        documents: tuple[DceDocument, ...],
    ) -> None:
        """Reject destructive replacement; a rectificatif must be a new root."""
        del corpus_hash, documents
        raise DocumentOriginalImmutableError(
            "admitted corpus and original documents cannot be replaced"
        )

    def declare_missing_document(
        self,
        *,
        expected_family: str,
        reason: str,
        source_reference: str,
    ) -> None:
        self._ensure_admitted_and_usable()
        if (
            not expected_family.strip()
            or not reason.strip()
            or not source_reference.strip()
        ):
            raise SourceLocationRequiredError(
                "missing document declaration requires family, reason and source reference"
            )
        missing_document = MissingDocument(
            expected_family=expected_family.strip(),
            reason=reason.strip(),
            source_reference=source_reference.strip(),
        )
        self.missing_documents.append(missing_document)
        self.integrity = DceIntegrity.PARTIAL
        self._increment_revision()
        self._record(
            DceDocumentMissingDeclared(
                dce_version_id=self.id,
                expected_family=missing_document.expected_family,
            )
        )

    def register_source_statement(
        self,
        *,
        source_statement_id: UUID,
        document_id: UUID,
        locator: str,
        excerpt: str,
        provenance: str,
    ) -> None:
        self._ensure_admitted_and_usable()
        if document_id not in {document.document_id for document in self.documents}:
            raise SourceLocationRequiredError("source statement document is not in DCE version")
        if not locator.strip() or not excerpt.strip() or not provenance.strip():
            raise SourceLocationRequiredError(
                "source statement requires locator, excerpt and provenance"
            )
        if any(
            statement.source_statement_id == source_statement_id
            for statement in self.source_statements
        ):
            raise SourceLocationRequiredError("source statement identifier is already registered")
        statement = SourceStatement(
            source_statement_id=source_statement_id,
            document_id=document_id,
            locator=locator.strip(),
            excerpt=excerpt.strip(),
            provenance=provenance.strip(),
        )
        self.source_statements.append(statement)
        self._increment_revision()
        self._record(
            DceSourceStatementRegistered(
                dce_version_id=self.id,
                source_statement_id=statement.source_statement_id,
            )
        )

    def mark_superseded_by(self, successor_version_id: UUID) -> None:
        if self.lifecycle is DceLifecycle.WITHDRAWN:
            raise DceVersionUnusableError("withdrawn DCE version cannot be superseded")
        if successor_version_id == self.id:
            raise DocumentOriginalImmutableError("DCE version cannot supersede itself")
        self.lifecycle = DceLifecycle.SUPERSEDED
        self.analysis_readiness = AnalysisReadiness.REVIEW_REQUIRED
        self._increment_revision()
        self._record(
            DceVersionSuperseded(
                dce_version_id=self.id,
                superseded_by_version_id=successor_version_id,
            )
        )

    def withdraw(self, *, reason: str, source_reference: str) -> None:
        if self.lifecycle is not DceLifecycle.ADMITTED:
            raise DceVersionUnusableError("only an admitted DCE version can be withdrawn")
        if not reason.strip() or not source_reference.strip():
            raise SourceLocationRequiredError("DCE withdrawal requires reason and source reference")
        self.lifecycle = DceLifecycle.WITHDRAWN
        self.analysis_readiness = AnalysisReadiness.REVIEW_REQUIRED
        self._increment_revision()
        self._record(DceVersionWithdrawn(dce_version_id=self.id))

    def _ensure_admitted_and_usable(self) -> None:
        if self.lifecycle is DceLifecycle.WITHDRAWN or self.integrity is DceIntegrity.UNUSABLE:
            raise DceVersionUnusableError("DCE version is withdrawn or unusable")
        if self.lifecycle is not DceLifecycle.ADMITTED:
            raise DceVersionUnusableError("operation requires an admitted DCE version")

    def _increment_revision(self) -> None:
        self.aggregate_revision += 1

    def _record(self, event: object) -> None:
        self._pending_events.append(event)


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value.lower())
