"""Application ports for tenant-scoped Consultation and DceVersion persistence.

The snapshots contain only data owned by their root. They never expose Case or
Decision objects and therefore cannot become a cross-context mutation path.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ConsultationRootSnapshot:
    id: UUID
    tenant_id: UUID
    aggregate_revision: int
    functional_identity_hash: str
    buyer_legal_name: str
    buyer_normalized_id: str | None
    external_reference: str | None
    object_label: str
    location_label: str | None
    source_channel: str
    source_reference: str | None
    source_received_at: datetime
    lifecycle: str
    freshness: str
    metadata_history_json: tuple[Mapping[str, object], ...]


@dataclass(frozen=True, slots=True)
class ConsultationLotSnapshot:
    id: UUID
    lot_number: str
    label: str
    source_reference: str | None


@dataclass(frozen=True, slots=True)
class ConsultationTrancheSnapshot:
    id: UUID
    tranche_reference: str
    tranche_kind: str
    label: str | None
    source_reference: str | None


@dataclass(frozen=True, slots=True)
class ConsultationSnapshot:
    root: ConsultationRootSnapshot
    lots: tuple[ConsultationLotSnapshot, ...]
    tranches: tuple[ConsultationTrancheSnapshot, ...]


@dataclass(frozen=True, slots=True)
class DceVersionRootSnapshot:
    id: UUID
    tenant_id: UUID
    aggregate_revision: int
    consultation_id: UUID
    corpus_hash: str
    predecessor_dce_version_id: UUID | None
    provenance_channel: str
    provenance_reference: str | None
    provenance_url: str | None
    source_received_at: datetime
    lifecycle: str
    integrity: str
    classification_readiness: str
    analysis_readiness: str
    withdrawal_source: str | None
    withdrawal_reason: str | None
    superseded_at: datetime | None
    withdrawn_at: datetime | None


@dataclass(frozen=True, slots=True)
class DceDocumentSnapshot:
    id: UUID
    storage_object_id: UUID
    storage_key: str
    original_filename: str
    media_type: str
    byte_size: int
    sha256: str
    received_from: str


@dataclass(frozen=True, slots=True)
class DceDocumentClassificationSnapshot:
    id: UUID
    dce_document_id: UUID
    classification: str
    rationale: str | None
    source: str
    previous_classification_id: UUID | None
    is_current: bool


@dataclass(frozen=True, slots=True)
class DceDocumentIssueSnapshot:
    id: UUID
    dce_document_id: UUID | None
    issue_kind: str
    impact: str
    locator_json: Mapping[str, object] | None
    reason: str


@dataclass(frozen=True, slots=True)
class DceMissingDocumentSnapshot:
    id: UUID
    expected_document_family: str
    expectation_source_kind: str
    expectation_source_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class DceSourceStatementSnapshot:
    id: UUID
    dce_document_id: UUID
    locator_json: Mapping[str, object]
    excerpt: str
    source_language: str | None
    extraction_origin: str


@dataclass(frozen=True, slots=True)
class DceVersionSnapshot:
    root: DceVersionRootSnapshot
    documents: tuple[DceDocumentSnapshot, ...]
    classifications: tuple[DceDocumentClassificationSnapshot, ...]
    issues: tuple[DceDocumentIssueSnapshot, ...]
    missing_documents: tuple[DceMissingDocumentSnapshot, ...]
    source_statements: tuple[DceSourceStatementSnapshot, ...]


class ConsultationRepository(Protocol):
    """Persists only Consultation and its lot/tranche entities."""

    def get(
        self,
        *,
        tenant_id: UUID | str,
        aggregate_id: UUID | str,
    ) -> ConsultationSnapshot | None: ...

    def update_root(
        self,
        *,
        tenant_id: UUID | str,
        aggregate_id: UUID | str,
        expected_revision: int,
        changes: Mapping[str, object],
    ) -> int: ...


class DceVersionRepository(Protocol):
    """Persists only DceVersion and its admitted-document children."""

    def get(
        self,
        *,
        tenant_id: UUID | str,
        aggregate_id: UUID | str,
    ) -> DceVersionSnapshot | None: ...

    def update_root(
        self,
        *,
        tenant_id: UUID | str,
        aggregate_id: UUID | str,
        expected_revision: int,
        changes: Mapping[str, object],
    ) -> int: ...
