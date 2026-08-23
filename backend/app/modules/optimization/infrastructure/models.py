"""Immutable persistence records for auditable OR-Tools capacity runs."""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.persistence.base import Base, TenantScopedRecord


class OptimizationRunRecord(TenantScopedRecord, Base):
    """One immutable, tenant-scoped execution of the capacity solver."""

    __tablename__ = "optimization_runs"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_optimization_runs__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_optimization_runs__cases__tenant_case",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_optimization_runs__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "command_id", name="uq_optimization_runs__tenant_command"
        ),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_optimization_runs__tenant_idempotency"
        ),
        sa.CheckConstraint(
            "status IN ('OPTIMAL', 'FEASIBLE', 'INFEASIBLE', 'UNKNOWN', 'MODEL_INVALID')",
            name="status_allowed",
        ),
        sa.CheckConstraint("source_revision > 0", name="source_revision_positive"),
        sa.CheckConstraint(
            "jsonb_typeof(input_snapshot_json) = 'object'", name="input_snapshot_object"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(result_snapshot_json) = 'object'", name="result_snapshot_object"
        ),
        sa.CheckConstraint("input_sha256 ~ '^[a-f0-9]{64}$'", name="input_sha256_hex"),
        sa.Index(
            "ix_optimization_runs__tenant_case_created",
            "tenant_id",
            "case_id",
            "created_at",
        ),
        sa.Index(
            "ix_optimization_runs__tenant_case_source_revision",
            "tenant_id",
            "case_id",
            "source_revision",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    source_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    solver_id: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    input_sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    input_snapshot_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    result_snapshot_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
