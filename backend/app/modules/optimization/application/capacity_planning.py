"""Case-scoped application service for deterministic resource planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.modules.optimization.application.resource_assignment import (
    ResourceAssignmentOptimizer,
    ResourceAssignmentResult,
    ResourceDemand,
    ResourceSupply,
    SolverStatus,
)


@dataclass(frozen=True, slots=True)
class CaseCapacityPlanInput:
    """Trusted, non-financial inputs supplied by a tenant-scoped adapter."""

    tenant_id: UUID
    case_id: UUID
    demands: tuple[ResourceDemand, ...]
    supplies: tuple[ResourceSupply, ...]


class CaseCapacityInputPort(Protocol):
    def load(self, *, tenant_id: UUID, case_id: UUID) -> CaseCapacityPlanInput: ...


@dataclass(frozen=True, slots=True)
class CaseCapacityPlan:
    """Deterministic solver result; it is not a price or a patron decision."""

    tenant_id: UUID
    case_id: UUID
    solver_id: str
    status: SolverStatus
    assignments: tuple[tuple[UUID, UUID], ...]
    unassigned_demand_ids: tuple[UUID, ...]


class CapacityInputScopeError(ValueError):
    """Raised when an adapter returns data for a different tenant or Case."""


class CaseCapacityPlanningService:
    """Connect a tenant-scoped capacity port to the OR-Tools adapter.

    The service deliberately has no persistence and no financial input. A future
    persisted calculation must introduce its own reviewed contract, immutable
    inputs, audit event and optimistic revision boundary.
    """

    def __init__(
        self,
        *,
        input_port: CaseCapacityInputPort,
        optimizer: ResourceAssignmentOptimizer | None = None,
    ) -> None:
        self._input_port = input_port
        self._optimizer = optimizer or ResourceAssignmentOptimizer()

    def plan(self, *, tenant_id: UUID, case_id: UUID) -> CaseCapacityPlan:
        plan_input = self._input_port.load(tenant_id=tenant_id, case_id=case_id)
        if plan_input.tenant_id != tenant_id or plan_input.case_id != case_id:
            raise CapacityInputScopeError("capacity input scope does not match request")
        result = self._optimizer.solve(
            demands=plan_input.demands,
            supplies=plan_input.supplies,
        )
        return _to_plan(
            tenant_id=tenant_id,
            case_id=case_id,
            demands=plan_input.demands,
            result=result,
        )


def _to_plan(
    *,
    tenant_id: UUID,
    case_id: UUID,
    demands: tuple[ResourceDemand, ...],
    result: ResourceAssignmentResult,
) -> CaseCapacityPlan:
    return CaseCapacityPlan(
        tenant_id=tenant_id,
        case_id=case_id,
        solver_id=result.solver_id,
        status=result.status,
        assignments=tuple(
            (demand.id, result.assignments[demand.id])
            for demand in demands
            if demand.id in result.assignments
        ),
        unassigned_demand_ids=result.unassigned_demand_ids,
    )
