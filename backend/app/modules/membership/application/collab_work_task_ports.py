from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from app.platform.security.context import ActorContext


@dataclass(frozen=True, slots=True)
class AssignmentProjection:
    id: UUID
    case_id: UUID


@dataclass(frozen=True, slots=True)
class CollaboratorTaskProjection:
    id: UUID
    case_id: UUID
    assignment_id: UUID
    requirement_id: UUID
    task_kind: str
    title: str
    objective: str
    priority: str
    state: str
    due_at: datetime | None
    aggregate_revision: int


class CollaboratorWorkTaskReader(Protocol):
    def resolve_task_assignment_id(self, *, tenant_id: UUID, task_id: UUID) -> UUID | None: ...

    def resolve_assignment(
        self, *, tenant_id: UUID, membership_id: UUID, assignment_id: UUID
    ) -> AssignmentProjection | None: ...

    def resolve_active_assignment_for_case(
        self, *, tenant_id: UUID, membership_id: UUID, case_id: UUID
    ) -> AssignmentProjection | None: ...

    def list_for_case(
        self, *, tenant_id: UUID, case_id: UUID, assignment_id: UUID
    ) -> tuple[CollaboratorTaskProjection, ...]: ...

    def record_denial(
        self, *, actor: ActorContext, command: Any, now: datetime, reason: str
    ) -> None: ...
