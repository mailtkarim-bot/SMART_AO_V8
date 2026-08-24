from __future__ import annotations

from uuid import UUID

import pytest
from app.modules.optimization.application.resource_assignment import (
    ResourceAssignmentOptimizer,
    ResourceDemand,
    ResourceSupply,
    SolverStatus,
)

T1 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa1001")
T2 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa1002")
R1 = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbb1001")
R2 = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbb1002")


def test_cp_sat_assigns_each_demand_once_without_exceeding_capacity() -> None:
    result = ResourceAssignmentOptimizer().solve(
        demands=(
            ResourceDemand(id=T1, required_units=2),
            ResourceDemand(id=T2, required_units=1),
        ),
        supplies=(
            ResourceSupply(id=R1, capacity_units=2),
            ResourceSupply(id=R2, capacity_units=1),
        ),
    )

    assert result.status is SolverStatus.OPTIMAL
    assert result.solver_id == "google-ortools-cp-sat"
    assert set(result.assignments) == {T1, T2}
    assert result.assignments[T1] == R1
    assert result.assignments[T2] == R2
    assert result.unassigned_demand_ids == ()


def test_cp_sat_is_deterministic_for_same_inputs() -> None:
    optimizer = ResourceAssignmentOptimizer()
    inputs = {
        "demands": (ResourceDemand(id=T1, required_units=1),),
        "supplies": (
            ResourceSupply(id=R1, capacity_units=1),
            ResourceSupply(id=R2, capacity_units=1),
        ),
    }

    first = optimizer.solve(**inputs)
    second = optimizer.solve(**inputs)

    assert first == second


def test_cp_sat_reports_infeasible_when_demand_cannot_fit() -> None:
    result = ResourceAssignmentOptimizer().solve(
        demands=(ResourceDemand(id=T1, required_units=3),),
        supplies=(ResourceSupply(id=R1, capacity_units=2),),
    )

    assert result.status is SolverStatus.INFEASIBLE
    assert result.assignments == {}
    assert result.unassigned_demand_ids == (T1,)


def test_solver_rejects_invalid_integer_inputs() -> None:
    with pytest.raises(ValueError, match="required_units"):
        ResourceDemand(id=T1, required_units=0)

    with pytest.raises(ValueError, match="capacity_units"):
        ResourceSupply(id=R1, capacity_units=-1)

    with pytest.raises(ValueError, match="time_limit"):
        ResourceAssignmentOptimizer(time_limit_seconds=0)
