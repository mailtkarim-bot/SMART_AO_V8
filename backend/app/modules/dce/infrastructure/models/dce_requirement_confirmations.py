"""Historical human confirmations for immutable DCE requirements."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.persistence.base import Base, TenantScopedRecord


class DceRequirementConfirmationRecord(TenantScopedRecord, Base):
    __tablename__ = "dce_requirement_confirmations"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_dce_req_conf__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "requirement_id"],
            ["dce_requirements.tenant_id", "dce_requirements.id"],
            name="fk_dce_req_conf__requirement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "previous_confirmation_id"],
            ["dce_requirement_confirmations.tenant_id", "dce_requirement_confirmations.id"],
            name="fk_dce_req_conf__previous",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_dce_req_conf__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "requirement_id", "revision", name="uq_dce_req_conf_revision"
        ),
        sa.CheckConstraint("revision > 0", name="revision_positive"),
        sa.CheckConstraint(
            "outcome IN ('CONFIRMED', 'REVIEW_REQUIRED', 'NOT_APPLICABLE')", name="outcome"
        ),
        sa.CheckConstraint(
            "reason_code IN ('SOURCE_REVIEWED', 'AMBIGUOUS_SOURCE', 'CONTRADICTORY_DCE', "
            "'PATRON_NOT_APPLICABLE', 'NEEDS_EXTERNAL_CLARIFICATION')",
            name="reason",
        ),
        sa.Index(
            "ix_dce_req_conf__tenant_requirement_revision",
            "tenant_id",
            "requirement_id",
            "revision",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    requirement_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    previous_confirmation_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    outcome: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    reason_code: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    confirmed_by_actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class DceRequirementConfirmationCurrentRecord(TenantScopedRecord, Base):
    __tablename__ = "dce_requirement_confirmation_current"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_dce_req_conf_cur__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "requirement_id"],
            ["dce_requirements.tenant_id", "dce_requirements.id"],
            name="fk_dce_req_conf_cur__requirement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "confirmation_id"],
            ["dce_requirement_confirmations.tenant_id", "dce_requirement_confirmations.id"],
            name="fk_dce_req_conf_cur__confirmation",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "requirement_id", name="uq_dce_req_conf_cur_requirement"),
        sa.CheckConstraint("revision > 0", name="revision_positive"),
        sa.CheckConstraint(
            "outcome IN ('CONFIRMED', 'REVIEW_REQUIRED', 'NOT_APPLICABLE')", name="outcome"
        ),
    )

    requirement_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    confirmation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    outcome: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )
