from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from app.platform.security.context import ActorContext


@dataclass(frozen=True, slots=True)
class AssignmentProjection:
    case_id: UUID


@dataclass(frozen=True, slots=True)
class TaskProjection:
    id: UUID
    state: str
    aggregate_revision: int


@dataclass(frozen=True, slots=True)
class InformationRequestProjection:
    id: UUID
    task_id: UUID
    request_kind: str
    subject: str
    question: str
    requested_object: str
    reason: str
    priority: str
    state: str
    due_at: datetime | None
    aggregate_revision: int


@dataclass(frozen=True, slots=True)
class InformationResponseProjection:
    id: UUID
    request_id: UUID
    request_revision: int
    outcome: str
    response_text: str
    source_locator: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class TaskBlockerProjection:
    id: UUID
    task_id: UUID
    task_revision: int
    blocker_kind: str
    description: str
    source_locator: str | None
    resolution_owner: str
    state: str
    resolution_note: str | None
    resolved_at: datetime | None


class CollaboratorInfoBlockerReader(Protocol):
    def resolve_task_id(self, *, tenant_id: UUID, request_id: UUID) -> UUID | None: ...

    def resolve_assignment(
        self, *, tenant_id: UUID, membership_id: UUID, task_id: UUID
    ) -> AssignmentProjection | None: ...

    def read_workflow(
        self, *, tenant_id: UUID, task_id: UUID
    ) -> tuple[
        TaskProjection,
        tuple[InformationRequestProjection, ...],
        tuple[InformationResponseProjection, ...],
        tuple[TaskBlockerProjection, ...],
    ]: ...

    def record_denial(
        self, *, actor: ActorContext, command: Any, now: datetime, reason: str
    ) -> None: ...
