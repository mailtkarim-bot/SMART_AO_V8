from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from ortools.sat.python import cp_model


class SolverStatus(StrEnum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"
    MODEL_INVALID = "MODEL_INVALID"


@dataclass(frozen=True, slots=True)
class ResourceDemand:
    id: UUID
    required_units: int

    def __post_init__(self) -> None:
        if self.required_units < 1:
            raise ValueError("required_units must be positive")


@dataclass(frozen=True, slots=True)
class ResourceSupply:
    id: UUID
    capacity_units: int

    def __post_init__(self) -> None:
        if self.capacity_units < 1:
            raise ValueError("capacity_units must be positive")


@dataclass(frozen=True, slots=True)
class ResourceAssignmentResult:
    status: SolverStatus
    solver_id: str
    assignments: dict[UUID, UUID]
    unassigned_demand_ids: tuple[UUID, ...]


class ResourceAssignmentOptimizer:
    """Deterministic CP-SAT adapter for capacity assignment.

    The adapter accepts only integer capacity units. Financial values and domain
    aggregates stay outside the solver boundary, so the solver cannot finalize a
    price or a patron decision.
    """

    solver_id = "google-ortools-cp-sat"

    def __init__(self, *, time_limit_seconds: float = 5.0) -> None:
        if time_limit_seconds <= 0:
            raise ValueError("time_limit_seconds must be positive")
        self._time_limit_seconds = time_limit_seconds

    def solve(
        self,
        *,
        demands: tuple[ResourceDemand, ...],
        supplies: tuple[ResourceSupply, ...],
    ) -> ResourceAssignmentResult:
        _ensure_unique_ids((demand.id for demand in demands), name="demand")
        _ensure_unique_ids((supply.id for supply in supplies), name="supply")
        if not demands:
            return ResourceAssignmentResult(
                status=SolverStatus.OPTIMAL,
                solver_id=self.solver_id,
                assignments={},
                unassigned_demand_ids=(),
            )
        if not supplies:
            return ResourceAssignmentResult(
                status=SolverStatus.INFEASIBLE,
                solver_id=self.solver_id,
                assignments={},
                unassigned_demand_ids=tuple(demand.id for demand in demands),
            )

        model = cp_model.CpModel()
        decision_variables: dict[tuple[int, int], cp_model.IntVar] = {}
        for demand_index, _demand in enumerate(demands):
            for supply_index, _supply in enumerate(supplies):
                decision_variables[(demand_index, supply_index)] = model.new_bool_var(
                    f"assign_{demand_index}_{supply_index}"
                )

        for demand_index, _demand in enumerate(demands):
            model.add(
                sum(
                    decision_variables[(demand_index, supply_index)]
                    for supply_index in range(len(supplies))
                )
                == 1
            )

        for supply_index, supply in enumerate(supplies):
            model.add(
                sum(
                    demand.required_units * decision_variables[(demand_index, supply_index)]
                    for demand_index, demand in enumerate(demands)
                )
                <= supply.capacity_units
            )

        # Stable tie-break: when several assignments are feasible, choose the
        # earliest supply in the caller-provided ordered list.
        model.minimize(
            sum(
                (supply_index + 1) * decision_variables[(demand_index, supply_index)]
                for demand_index in range(len(demands))
                for supply_index in range(len(supplies))
            )
        )
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self._time_limit_seconds
        solver.parameters.num_search_workers = 1
        status = solver.solve(model)
        mapped_status = _map_status(status)
        if mapped_status not in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}:
            return ResourceAssignmentResult(
                status=mapped_status,
                solver_id=self.solver_id,
                assignments={},
                unassigned_demand_ids=tuple(demand.id for demand in demands),
            )

        assignments = {
            demands[demand_index].id: supplies[supply_index].id
            for (demand_index, supply_index), variable in decision_variables.items()
            if solver.value(variable)
        }
        return ResourceAssignmentResult(
            status=mapped_status,
            solver_id=self.solver_id,
            assignments=assignments,
            unassigned_demand_ids=tuple(
                demand.id for demand in demands if demand.id not in assignments
            ),
        )


def _map_status(status: int) -> SolverStatus:
    return {
        cp_model.OPTIMAL: SolverStatus.OPTIMAL,
        cp_model.FEASIBLE: SolverStatus.FEASIBLE,
        cp_model.INFEASIBLE: SolverStatus.INFEASIBLE,
        cp_model.MODEL_INVALID: SolverStatus.MODEL_INVALID,
    }.get(status, SolverStatus.UNKNOWN)


def _ensure_unique_ids(ids, *, name: str) -> None:
    values = tuple(ids)
    if len(values) != len(set(values)):
        raise ValueError(f"{name} ids must be unique")
