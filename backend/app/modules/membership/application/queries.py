"""Closed read contracts for collaborator-owned Assignment histories."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AssignmentHistoryItemProjection:
    """One history fact stripped of free text, audit and identity metadata."""

    record_id: UUID
    kind: str
    recorded_at: datetime
    assignment_revision: int | None
    operational_state: str
    clarification_kind: str | None = None
    priority: str | None = None
    reason_kind: str | None = None
    unavailable_from: datetime | None = None
    unavailable_until: datetime | None = None
    known_deadline_impact: bool | None = None


@dataclass(frozen=True, slots=True)
class AssignmentHistoryLookup:
    """Tenant- and membership-scoped history candidate before ReBAC authorization."""

    assignment_id: UUID
    case_id: UUID
    case_lifecycle: str
    items: tuple[AssignmentHistoryItemProjection, ...]


class AssignmentHistoryReader(Protocol):
    """Read only an assignment owned by a trusted tenant and membership."""

    def get(
        self,
        *,
        tenant_id: UUID,
        membership_id: UUID,
        assignment_id: UUID,
        limit: int,
    ) -> AssignmentHistoryLookup | None: ...
