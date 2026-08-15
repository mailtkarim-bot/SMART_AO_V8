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


@dataclass(frozen=True, slots=True)
class PatronAssignmentCockpitItemProjection:
    """One patron-authorized assignment row without identity, audit or financial data."""

    assignment_id: UUID
    case_id: UUID
    case_title: str
    case_lifecycle: str
    state: str
    aggregate_revision: int
    starts_at: datetime
    ends_at: datetime | None
    ended_at: datetime | None
    scope_actions: tuple[str, ...]
    scope_classifications: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PatronAssignmentJournalItemProjection:
    """One immutable patron authority fact stripped of actor and command metadata."""

    record_id: UUID
    recorded_at: datetime
    event_type: str
    previous_revision: int | None
    resulting_revision: int
    previous_state: str | None
    resulting_state: str
    reason_code: str | None
    previous_scope_actions: tuple[str, ...] | None
    previous_scope_classifications: tuple[str, ...] | None
    resulting_scope_actions: tuple[str, ...]
    resulting_scope_classifications: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PatronAssignmentJournalLookup:
    """One tenant-scoped assignment header and its bounded patron authority journal."""

    assignment: PatronAssignmentCockpitItemProjection
    items: tuple[PatronAssignmentJournalItemProjection, ...]


@dataclass(frozen=True, slots=True)
class PatronAssignmentInteractionsLookup:
    """One tenant-scoped assignment and its bounded closed collaborator interaction facts."""

    assignment_id: UUID
    case_id: UUID
    case_lifecycle: str
    items: tuple[AssignmentHistoryItemProjection, ...]


class PatronAssignmentCockpitReader(Protocol):
    """Read only tenant-owned assignment cockpit projections for a patron."""

    def list(
        self,
        *,
        tenant_id: UUID,
        case_id: UUID | None,
        state: str | None,
        limit: int,
    ) -> tuple[PatronAssignmentCockpitItemProjection, ...]: ...

    def get_journal(
        self,
        *,
        tenant_id: UUID,
        assignment_id: UUID,
        limit: int,
    ) -> PatronAssignmentJournalLookup | None: ...
