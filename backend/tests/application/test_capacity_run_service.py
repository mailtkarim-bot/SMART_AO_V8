from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from app.modules.optimization.application.capacity_planning import (
    CaseCapacityPlan,
    CaseCapacityPlanInput,
)
from app.modules.optimization.application.resource_assignment import (
    ResourceDemand,
    ResourceSupply,
    SolverStatus,
)
from app.modules.optimization.application.run_service import (
    CapacityRunCommand,
    CapacityRunPersistenceResult,
    CapacityRunRecordInput,
    CapacityRunService,
    CapacitySourceRevisionConflict,
)

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CASE_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001")
DEMAND_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0002")
SUPPLY_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0003")


@dataclass
class FakePlanner:
    plan_input: CaseCapacityPlanInput
    plan: CaseCapacityPlan

    def plan_with_input(self, *, tenant_id: UUID, case_id: UUID):
        assert self.plan_input.tenant_id == tenant_id
        assert self.plan_input.case_id == case_id
        return self.plan_input, self.plan


class FakeRepository:
    def __init__(self, *, replayed: bool = False) -> None:
        self.records: list[CapacityRunRecordInput] = []
        self.replayed = replayed

    def save_or_replay(self, record: CapacityRunRecordInput) -> CapacityRunPersistenceResult:
        self.records.append(record)
        return CapacityRunPersistenceResult(
            run_id=record.run_id,
            status=record.status,
            audit_event_id=uuid4(),
            replayed=self.replayed,
        )


def _input(source_revision: int = 4) -> CaseCapacityPlanInput:
    return CaseCapacityPlanInput(
        tenant_id=TENANT_ID,
        case_id=CASE_ID,
        source_revision=source_revision,
        demands=(ResourceDemand(id=DEMAND_ID, required_units=2),),
        supplies=(ResourceSupply(id=SUPPLY_ID, capacity_units=2),),
    )


def _plan() -> CaseCapacityPlan:
    return CaseCapacityPlan(
        tenant_id=TENANT_ID,
        case_id=CASE_ID,
        solver_id="google-ortools-cp-sat",
        status=SolverStatus.OPTIMAL,
        assignments=((DEMAND_ID, SUPPLY_ID),),
        unassigned_demand_ids=(),
    )


def _command(*, expected_revision: int = 4) -> CapacityRunCommand:
    return CapacityRunCommand(
        run_id=uuid4(),
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        actor_id=uuid4(),
        tenant_id=TENANT_ID,
        case_id=CASE_ID,
        expected_source_revision=expected_revision,
    )


def test_service_persists_a_non_financial_canonical_snapshot() -> None:
    repository = FakeRepository()
    result = CapacityRunService(
        planner=FakePlanner(_input(), _plan()),
        repository=repository,
    ).execute(_command())

    assert result.replayed is False
    record = repository.records[0]
    assert record.status is SolverStatus.OPTIMAL
    assert len(record.input_sha256) == 64
    assert record.input_snapshot == {
        "demands": [{"id": str(DEMAND_ID), "required_units": 2}],
        "supplies": [{"id": str(SUPPLY_ID), "capacity_units": 2}],
    }
    assert record.result_snapshot == {
        "assignments": [{"demand_id": str(DEMAND_ID), "supply_id": str(SUPPLY_ID)}],
        "unassigned_demand_ids": [],
    }
    forbidden = str(record.input_snapshot) + str(record.result_snapshot)
    assert all(value not in forbidden.lower() for value in ("amount", "price", "margin", "cost"))


def test_service_rejects_a_stale_source_revision_before_persistence() -> None:
    repository = FakeRepository()
    with pytest.raises(CapacitySourceRevisionConflict, match="revision"):
        CapacityRunService(
            planner=FakePlanner(_input(source_revision=5), _plan()),
            repository=repository,
        ).execute(_command(expected_revision=4))
    assert repository.records == []


def test_service_preserves_repository_replay() -> None:
    repository = FakeRepository(replayed=True)
    result = CapacityRunService(
        planner=FakePlanner(_input(), _plan()),
        repository=repository,
    ).execute(_command())

    assert result.replayed is True
    assert len(repository.records) == 1


def test_command_rejects_non_positive_expected_revision() -> None:
    with pytest.raises(ValueError, match="positive"):
        _command(expected_revision=0)
