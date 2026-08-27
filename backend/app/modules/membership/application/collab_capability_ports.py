from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AssignmentProjection:
    id: UUID
    case_id: UUID


@dataclass(frozen=True, slots=True)
class CapabilityProposalProjection:
    proposal_id: UUID
    case_id: UUID
    assignment_id: UUID
    capability_id: UUID
    capability_version_id: UUID
    requirement_id: UUID | None
    task_id: UUID | None
    state: str
    validity_state: str
    justification: str
    source_locator: str | None


@dataclass(frozen=True, slots=True)
class CapabilityGapProjection:
    gap_id: UUID
    case_id: UUID
    assignment_id: UUID
    capability_id: UUID | None
    requirement_id: UUID | None
    task_id: UUID | None
    gap_kind: str
    severity: str
    reason: str
    source_locator: str | None
    recommended_action: str


@dataclass(frozen=True, slots=True)
class CollaboratorCapabilityAssessmentProjection:
    proposals: tuple[CapabilityProposalProjection, ...]
    gaps: tuple[CapabilityGapProjection, ...]


class CollaboratorCapabilityReader(Protocol):
    def require_active_assignment(
        self,
        *,
        tenant_id: UUID,
        membership_id: UUID,
        case_id: UUID,
        assignment_id: UUID,
        required_action: str,
        received_at: datetime,
    ) -> AssignmentProjection: ...

    def read_assessments(
        self, *, tenant_id: UUID, case_id: UUID, assignment_id: UUID
    ) -> CollaboratorCapabilityAssessmentProjection: ...
