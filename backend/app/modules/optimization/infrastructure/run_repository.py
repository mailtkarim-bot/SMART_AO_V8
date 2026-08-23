"""SQLAlchemy adapter for immutable OR-Tools run persistence."""

from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker

from app.modules.optimization.application.run_service import (
    CapacityRunIdempotencyConflict,
    CapacityRunPersistenceResult,
    CapacityRunRecordInput,
)
from app.platform.persistence.models import DomainEventRecord

from .models import OptimizationRunRecord


class SqlAlchemyCapacityRunRepository:
    """Persist a run and its audit event in one database transaction."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def save_or_replay(self, record: CapacityRunRecordInput) -> CapacityRunPersistenceResult:
        with self._session_factory.begin() as session:
            statement = (
                pg_insert(OptimizationRunRecord)
                .values(
                    id=record.run_id,
                    tenant_id=record.tenant_id,
                    case_id=record.case_id,
                    source_revision=record.source_revision,
                    solver_id=record.solver_id,
                    status=record.status.value,
                    input_sha256=record.input_sha256,
                    input_snapshot_json=record.input_snapshot,
                    result_snapshot_json=record.result_snapshot,
                    actor_id=record.actor_id,
                    command_id=record.command_id,
                    idempotency_key=record.idempotency_key,
                    correlation_id=record.correlation_id,
                )
                .on_conflict_do_nothing()
            )
            inserted = session.execute(statement).rowcount == 1
            existing = session.scalar(
                sa.select(OptimizationRunRecord).where(
                    sa.or_(
                        sa.and_(
                            OptimizationRunRecord.tenant_id == record.tenant_id,
                            OptimizationRunRecord.id == record.run_id,
                        ),
                        sa.and_(
                            OptimizationRunRecord.tenant_id == record.tenant_id,
                            OptimizationRunRecord.command_id == record.command_id,
                        ),
                        sa.and_(
                            OptimizationRunRecord.tenant_id == record.tenant_id,
                            OptimizationRunRecord.idempotency_key == record.idempotency_key,
                        ),
                    )
                )
            )
            if existing is None:
                raise RuntimeError("optimization run insert was not durable")
            if not _matches(existing, record):
                raise CapacityRunIdempotencyConflict(
                    "optimization run key was reused with a different request"
                )

            audit_event = session.scalar(
                sa.select(DomainEventRecord).where(
                    DomainEventRecord.tenant_id == record.tenant_id,
                    DomainEventRecord.aggregate_type == "OptimizationRun",
                    DomainEventRecord.aggregate_id == existing.id,
                    DomainEventRecord.event_type == "OPTIMIZATION_RUN_RECORDED",
                )
            )
            if inserted:
                if audit_event is not None:
                    raise RuntimeError("optimization run audit event already exists")
                audit_event = DomainEventRecord(
                    id=uuid4(),
                    tenant_id=record.tenant_id,
                    aggregate_type="OptimizationRun",
                    aggregate_id=record.run_id,
                    aggregate_revision=1,
                    event_type="OPTIMIZATION_RUN_RECORDED",
                    payload_version=1,
                    payload_json={
                        "run_id": str(record.run_id),
                        "case_id": str(record.case_id),
                        "source_revision": record.source_revision,
                        "solver_id": record.solver_id,
                        "status": record.status.value,
                        "input_sha256": record.input_sha256,
                    },
                    actor_id=record.actor_id,
                    command_id=record.command_id,
                    correlation_id=record.correlation_id,
                    causation_id=record.command_id,
                )
                session.add(audit_event)
                session.flush()
            if audit_event is None:
                raise RuntimeError("optimization run audit event was not durable")
            return CapacityRunPersistenceResult(
                run_id=existing.id,
                status=record.status,
                audit_event_id=audit_event.id,
                replayed=not inserted,
            )


def _matches(existing: OptimizationRunRecord, record: CapacityRunRecordInput) -> bool:
    return (
        existing.id == record.run_id
        and existing.tenant_id == record.tenant_id
        and existing.case_id == record.case_id
        and existing.source_revision == record.source_revision
        and existing.input_sha256 == record.input_sha256
        and existing.command_id == record.command_id
        and existing.idempotency_key == record.idempotency_key
    )
