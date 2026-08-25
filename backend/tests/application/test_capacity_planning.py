from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest
from app.modules.optimization.application.capacity_planning import (
    CapacityInputScopeError,
    CaseCapacityPlanInput,
    CaseCapacityPlanningService,
)
from app.modules.optimization.application.resource_assignment import (
    ResourceAssignmentResult,
    ResourceDemand,
    ResourceSupply,
    SolverStatus,
)

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CASE_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001")
DEMAND_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0002")
DEMAND_B = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0003")
SUPPLY_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0004")


@dataclass
class FakeInputPort:
    value: CaseCapacityPlanInput

    def __post_init__(self) -> None:
        self.calls: list[dict[str, UUID]] = []

    def load(self, *, tenant_id: UUID, case_id: UUID) -> CaseCapacityPlanInput:
        self.calls.append({"tenant_id": tenant_id, "case_id": case_id})
        return self.value


class FakeOptimizer:
    solver_id = "fake-solver"

    def __init__(self, result: ResourceAssignmentResult) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def solve(self, *, demands, supplies) -> ResourceAssignmentResult:
        self.calls.append({"demands": demands, "supplies": supplies})
        return self.result


def _input() -> CaseCapacityPlanInput:
    return CaseCapacityPlanInput(
        tenant_id=TENANT_ID,
        case_id=CASE_ID,
        demands=(
            ResourceDemand(id=DEMAND_A, required_units=2),
            ResourceDemand(id=DEMAND_B, required_units=1),
        ),
        supplies=(ResourceSupply(id=SUPPLY_A, capacity_units=3),),
    )


def test_service_loads_case_scoped_inputs_and_returns_safe_plan() -> None:
    source = FakeInputPort(_input())
    optimizer = FakeOptimizer(
        ResourceAssignmentResult(
            status=SolverStatus.OPTIMAL,
            solver_id="fake-solver",
            assignments={DEMAND_A: SUPPLY_A},
            unassigned_demand_ids=(DEMAND_B,),
        )
    )

    plan = CaseCapacityPlanningService(
        input_port=source,
        optimizer=optimizer,
    ).plan(tenant_id=TENANT_ID, case_id=CASE_ID)

    assert source.calls == [{"tenant_id": TENANT_ID, "case_id": CASE_ID}]
    assert optimizer.calls == [{"demands": _input().demands, "supplies": _input().supplies}]
    assert plan.tenant_id == TENANT_ID
    assert plan.case_id == CASE_ID
    assert plan.solver_id == "fake-solver"
    assert plan.status is SolverStatus.OPTIMAL
    assert plan.assignments == ((DEMAND_A, SUPPLY_A),)
    assert plan.unassigned_demand_ids == (DEMAND_B,)
    assert not hasattr(plan, "amount")
    assert not hasattr(plan, "price")
    assert not hasattr(plan, "margin")


def test_service_rejects_adapter_scope_mismatch() -> None:
    source = FakeInputPort(
        CaseCapacityPlanInput(
            tenant_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            case_id=CASE_ID,
            demands=(),
            supplies=(),
        )
    )

    with pytest.raises(CapacityInputScopeError, match="scope"):
        CaseCapacityPlanningService(input_port=source).plan(
            tenant_id=TENANT_ID,
            case_id=CASE_ID,
        )


def test_service_preserves_infeasible_result_without_fallback() -> None:
    source = FakeInputPort(_input())
    optimizer = FakeOptimizer(
        ResourceAssignmentResult(
            status=SolverStatus.INFEASIBLE,
            solver_id="fake-solver",
            assignments={},
            unassigned_demand_ids=(DEMAND_A, DEMAND_B),
        )
    )

    plan = CaseCapacityPlanningService(
        input_port=source,
        optimizer=optimizer,
    ).plan(tenant_id=TENANT_ID, case_id=CASE_ID)

    assert plan.status is SolverStatus.INFEASIBLE
    assert plan.assignments == ()
    assert plan.unassigned_demand_ids == (DEMAND_A, DEMAND_B)
