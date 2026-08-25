from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.persistence.base import Base, TenantScopedRecord


class DecisionRiskRequirementLinkRecord(TenantScopedRecord, Base):
    """Immutable patron link from a registered risk to a confirmed DCE requirement."""

    __tablename__ = "decision_risk_requirement_links"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_decision_risk_links__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_decision_risk_links__case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "risk_id"],
            ["decision_risks.tenant_id", "decision_risks.id"],
            name="fk_decision_risk_links__risk",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "requirement_id"],
            ["dce_requirements.tenant_id", "dce_requirements.id"],
            name="fk_decision_risk_links__requirement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_decision_risk_links__dce_version",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_decision_risk_links__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "functional_key", name="uq_decision_risk_links__functional"
        ),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_decision_risk_links__command"),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_decision_risk_links__idempotency"
        ),
        sa.CheckConstraint(
            "relationship IN ('IMPACTS', 'MITIGATES', 'CONSTRAINS')",
            name="relationship",
        ),
        sa.CheckConstraint("char_length(btrim(rationale)) > 0", name="rationale_nonempty"),
        sa.Index(
            "ix_decision_risk_links__tenant_case_created", "tenant_id", "case_id", "created_at"
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    risk_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    requirement_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    dce_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    functional_key: Mapped[str] = mapped_column(sa.String(180), nullable=False)
    relationship: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    rationale: Mapped[str] = mapped_column(sa.Text, nullable=False)
    source_refs_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
