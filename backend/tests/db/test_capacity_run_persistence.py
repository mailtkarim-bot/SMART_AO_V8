from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from app.modules.optimization.application.capacity_planning import (
    CaseCapacityPlanInput,
    CaseCapacityPlanningService,
)
from app.modules.optimization.application.resource_assignment import ResourceDemand, ResourceSupply
from app.modules.optimization.application.run_service import CapacityRunCommand, CapacityRunService
from app.modules.optimization.infrastructure.models import OptimizationRunRecord
from app.modules.optimization.infrastructure.run_repository import SqlAlchemyCapacityRunRepository
from app.platform.persistence.models import DomainEventRecord
from sqlalchemy.orm import Session, sessionmaker
from tests.application.test_collab_work_task import _seed

pytest_plugins = ("tests.application.test_collab_work_task",)

DEMAND_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0002")
SUPPLY_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0003")


@dataclass
class MutableInputPort:
    value: CaseCapacityPlanInput

    def load(self, *, tenant_id: UUID, case_id: UUID) -> CaseCapacityPlanInput:
        assert self.value.tenant_id == tenant_id
        assert self.value.case_id == case_id
        return self.value


def _input(tenant_id: UUID, case_id: UUID, required_units: int = 2) -> CaseCapacityPlanInput:
    return CaseCapacityPlanInput(
        tenant_id=tenant_id,
        case_id=case_id,
        source_revision=3,
        demands=(ResourceDemand(id=DEMAND_ID, required_units=required_units),),
        supplies=(ResourceSupply(id=SUPPLY_ID, capacity_units=2),),
    )


def _command(actor, case_id: UUID) -> CapacityRunCommand:
    return CapacityRunCommand(
        run_id=uuid4(),
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        actor_id=actor.actor_id,
        tenant_id=actor.tenant_id,
        case_id=case_id,
        expected_source_revision=3,
    )


@pytest.mark.db
@pytest.mark.security
def test_capacity_run_is_idempotent_audited_and_append_only(
    session_factory: sessionmaker[Session],
) -> None:
    actor, _assignment_id, case_id, _requirement_id = _seed(session_factory)
    input_port = MutableInputPort(_input(actor.tenant_id, case_id))
    service = CapacityRunService(
        planner=CaseCapacityPlanningService(input_port=input_port),
        repository=SqlAlchemyCapacityRunRepository(session_factory),
    )
    command = _command(actor, case_id)

    first = service.execute(command)
    replay = service.execute(command)

    assert first.replayed is False
    assert replay.replayed is True
    assert replay.run_id == first.run_id
    assert replay.audit_event_id == first.audit_event_id

    with session_factory() as session:
        run = session.get(OptimizationRunRecord, first.run_id)
        assert run is not None
        assert run.tenant_id == actor.tenant_id
        assert run.case_id == case_id
        assert run.source_revision == 3
        assert run.status == "OPTIMAL"
        assert run.input_snapshot_json == {
            "demands": [{"id": str(DEMAND_ID), "required_units": 2}],
            "supplies": [{"id": str(SUPPLY_ID), "capacity_units": 2}],
        }
        assert "amount" not in str(run.input_snapshot_json).lower()
        event = session.get(DomainEventRecord, first.audit_event_id)
        assert event is not None
        assert event.aggregate_type == "OptimizationRun"
        assert event.aggregate_id == first.run_id
        assert event.event_type == "OPTIMIZATION_RUN_RECORDED"
        assert event.payload_json == {
            "run_id": str(first.run_id),
            "case_id": str(case_id),
            "source_revision": 3,
            "solver_id": "google-ortools-cp-sat",
            "status": "OPTIMAL",
            "input_sha256": run.input_sha256,
        }
        assert session.scalar(
            sa.select(sa.func.count()).where(
                OptimizationRunRecord.tenant_id == actor.tenant_id,
                OptimizationRunRecord.id == first.run_id,
            )
        ) == 1

    with pytest.raises(sa.exc.ProgrammingError), session_factory.begin() as session:
        session.execute(
            sa.update(OptimizationRunRecord)
            .where(OptimizationRunRecord.id == first.run_id)
            .values(status="FEASIBLE")
        )


@pytest.mark.db
@pytest.mark.security
def test_capacity_run_rejects_idempotency_reuse_with_changed_input(
    session_factory: sessionmaker[Session],
) -> None:
    actor, _assignment_id, case_id, _requirement_id = _seed(session_factory)
    input_port = MutableInputPort(_input(actor.tenant_id, case_id))
    service = CapacityRunService(
        planner=CaseCapacityPlanningService(input_port=input_port),
        repository=SqlAlchemyCapacityRunRepository(session_factory),
    )
    command = _command(actor, case_id)
    service.execute(command)
    input_port.value = _input(actor.tenant_id, case_id, required_units=1)

    with pytest.raises(ValueError, match="idempotency"):
        service.execute(command)

    with session_factory() as session:
        assert session.scalar(
            sa.select(sa.func.count()).where(
                OptimizationRunRecord.tenant_id == actor.tenant_id,
                OptimizationRunRecord.command_id == command.command_id,
            )
        ) == 1
