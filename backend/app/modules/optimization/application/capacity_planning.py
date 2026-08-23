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
    source_revision: int = 1
    demands: tuple[ResourceDemand, ...] = ()
    supplies: tuple[ResourceSupply, ...] = ()

    def __post_init__(self) -> None:
        if self.source_revision < 1:
            raise ValueError("source_revision must be positive")


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
        return self.plan_with_input(tenant_id=tenant_id, case_id=case_id)[1]

    def plan_with_input(
        self,
        *,
        tenant_id: UUID,
        case_id: UUID,
    ) -> tuple[CaseCapacityPlanInput, CaseCapacityPlan]:
        plan_input = self._input_port.load(tenant_id=tenant_id, case_id=case_id)
        if plan_input.tenant_id != tenant_id or plan_input.case_id != case_id:
            raise CapacityInputScopeError("capacity input scope does not match request")
        result = self._optimizer.solve(
            demands=plan_input.demands,
            supplies=plan_input.supplies,
        )
        return plan_input, _to_plan(
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
