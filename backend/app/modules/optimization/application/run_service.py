"""Application service for immutable, auditable OR-Tools runs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.modules.optimization.application.capacity_planning import (
    CaseCapacityPlanInput,
    CaseCapacityPlanningService,
)
from app.modules.optimization.application.resource_assignment import SolverStatus


@dataclass(frozen=True, slots=True)
class CapacityRunCommand:
    run_id: UUID
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None
    actor_id: UUID
    tenant_id: UUID
    case_id: UUID
    expected_source_revision: int

    def __post_init__(self) -> None:
        if self.expected_source_revision < 1:
            raise ValueError("expected_source_revision must be positive")


@dataclass(frozen=True, slots=True)
class CapacityRunRecordInput:
    run_id: UUID
    tenant_id: UUID
    case_id: UUID
    source_revision: int
    solver_id: str
    status: SolverStatus
    input_sha256: str
    input_snapshot: dict[str, object]
    result_snapshot: dict[str, object]
    actor_id: UUID
    command_id: UUID
    idempotency_key: UUID
    correlation_id: UUID | None


@dataclass(frozen=True, slots=True)
class CapacityRunPersistenceResult:
    run_id: UUID
    status: SolverStatus
    audit_event_id: UUID
    replayed: bool


class CapacityRunRepositoryPort(Protocol):
    def save_or_replay(self, record: CapacityRunRecordInput) -> CapacityRunPersistenceResult: ...


class CapacitySourceRevisionConflict(ValueError):
    """Raised when the input changed after the caller's expected revision."""


class CapacityRunIdempotencyConflict(ValueError):
    """Raised when a run key is reused with a different immutable request."""


class CapacityRunService:
    """Persist one deterministic capacity plan and its audit event atomically."""

    def __init__(
        self,
        *,
        planner: CaseCapacityPlanningService,
        repository: CapacityRunRepositoryPort,
    ) -> None:
        self._planner = planner
        self._repository = repository

    def execute(self, command: CapacityRunCommand) -> CapacityRunPersistenceResult:
        plan_input, plan = self._planner.plan_with_input(
            tenant_id=command.tenant_id,
            case_id=command.case_id,
        )
        if plan_input.source_revision != command.expected_source_revision:
            raise CapacitySourceRevisionConflict("capacity source revision does not match request")

        input_snapshot = _input_snapshot(plan_input)
        result_snapshot = {
            "assignments": [
                {"demand_id": str(demand_id), "supply_id": str(supply_id)}
                for demand_id, supply_id in plan.assignments
            ],
            "unassigned_demand_ids": [str(value) for value in plan.unassigned_demand_ids],
        }
        payload = _canonical_json(input_snapshot)
        record = CapacityRunRecordInput(
            run_id=command.run_id,
            tenant_id=command.tenant_id,
            case_id=command.case_id,
            source_revision=plan_input.source_revision,
            solver_id=plan.solver_id,
            status=plan.status,
            input_sha256=hashlib.sha256(payload).hexdigest(),
            input_snapshot=input_snapshot,
            result_snapshot=result_snapshot,
            actor_id=command.actor_id,
            command_id=command.command_id,
            idempotency_key=command.idempotency_key,
            correlation_id=command.correlation_id,
        )
        return self._repository.save_or_replay(record)


def _input_snapshot(plan_input: CaseCapacityPlanInput) -> dict[str, object]:
    return {
        "demands": [
            {"id": str(demand.id), "required_units": demand.required_units}
            for demand in plan_input.demands
        ],
        "supplies": [
            {"id": str(supply.id), "capacity_units": supply.capacity_units}
            for supply in plan_input.supplies
        ],
    }


def _canonical_json(value: dict[str, object]) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
