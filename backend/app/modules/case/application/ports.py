"""Application port for tenant-scoped Case persistence.

Snapshots are persistence-neutral transfer objects. They allow handlers to
rehydrate the pure domain aggregate later without importing SQLAlchemy models.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CaseRootSnapshot:
    id: UUID
    tenant_id: UUID
    aggregate_revision: int
    title: str
    object_description: str | None
    business_origin: str
    origin_reference_id: UUID | None
    origin_rationale: str | None
    consultation_id: UUID | None
    scope_kind: str
    scope_json: Mapping[str, object]
    scope_fingerprint: str
    applicable_dce_version_id: UUID | None
    lifecycle: str
    commercial_stage: str
    decision_readiness: str
    dce_freshness: str
    responsibility_status: str
    stopped_reason: str | None
    stopped_at: datetime | None
    archived_reason: str | None
    archived_at: datetime | None


@dataclass(frozen=True, slots=True)
class CaseConsultationLinkSnapshot:
    id: UUID
    consultation_id: UUID
    scope_snapshot_json: Mapping[str, object]
    rationale: str | None
    is_current: bool


@dataclass(frozen=True, slots=True)
class CaseDceApplicabilitySnapshot:
    id: UUID
    dce_version_id: UUID
    reason: str
    is_current: bool
    set_at: datetime


@dataclass(frozen=True, slots=True)
class CaseSnapshot:
    root: CaseRootSnapshot
    consultation_links: tuple[CaseConsultationLinkSnapshot, ...]
    dce_applicability_history: tuple[CaseDceApplicabilitySnapshot, ...]


class CaseRepository(Protocol):
    """Persists only Case and entities owned internally by Case."""

    def get(self, *, tenant_id: UUID | str, aggregate_id: UUID | str) -> CaseSnapshot | None: ...

    def update_root(
        self,
        *,
        tenant_id: UUID | str,
        aggregate_id: UUID | str,
        expected_revision: int,
        changes: Mapping[str, object],
    ) -> int: ...
