from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.persistence.base import Base, TenantScopedRecord


class FinancialReportSnapshotRecord(TenantScopedRecord, Base):
    """Immutable patron-owned financial snapshot; only published snapshots are readable."""

    __tablename__ = "financial_report_snapshots"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_financial_snapshot__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_financial_snapshot__case",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_financial_snapshot__tenant_id"),
        sa.CheckConstraint("state IN ('DRAFT', 'PUBLISHED')", name="state"),
        sa.CheckConstraint("currency_code ~ '^[A-Z]{3}$'", name="currency"),
        sa.CheckConstraint("ruleset_version >= 1", name="ruleset_version"),
        sa.CheckConstraint(
            "(state = 'DRAFT' AND published_at IS NULL) OR "
            "(state = 'PUBLISHED' AND published_at IS NOT NULL)",
            name="publication",
        ),
        sa.Index("ix_financial_snapshot__tenant_case", "tenant_id", "case_id", "created_at"),
        sa.Index(
            "uq_financial_snapshot__tenant_case_open_draft",
            "tenant_id",
            "case_id",
            unique=True,
            postgresql_where=sa.text("state = 'DRAFT'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    currency_code: Mapped[str] = mapped_column(sa.CHAR(3), nullable=False)
    ruleset_version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    aggregate_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    calculated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    sales_total_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    direct_cost_total_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    overhead_total_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    subcontracting_total_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    contingency_total_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    gross_margin_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    gross_margin_rate_bps: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    forecast_cashflow_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)

class FinancialReportLineRecord(TenantScopedRecord, Base):
    """Immutable authorized monetary line of one financial report snapshot."""

    __tablename__ = "financial_report_lines"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_financial_line__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "snapshot_id"],
            ["financial_report_snapshots.tenant_id", "financial_report_snapshots.id"],
            name="fk_financial_line__snapshot",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_financial_line__tenant_id"),
        sa.CheckConstraint(
            "category IN ('SALES', 'DIRECT_COST', 'OVERHEAD', 'SUBCONTRACTING', "
            "'CONTINGENCY', 'GROSS_MARGIN', 'FORECAST_CASHFLOW')",
            name="category",
        ),
        sa.CheckConstraint("length(trim(label)) > 0", name="label"),
        sa.Index("ix_financial_line__tenant_snapshot", "tenant_id", "snapshot_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    snapshot_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    category: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    label: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    quantity_decimal: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    unit: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    amount_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)

class PricingScenarioRecord(TenantScopedRecord, Base):
    """Private patron pricing scenario derived from one published snapshot."""

    __tablename__ = "pricing_scenarios"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_pricing_scenarios__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "source_snapshot_id"],
            ["financial_report_snapshots.tenant_id", "financial_report_snapshots.id"],
            name="fk_pricing_scenarios__snapshot",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_pricing_scenarios__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "case_id", "scenario_key", "version", name="uq_pricing_scenario_version"
        ),
        sa.CheckConstraint("version > 0", name="version_positive"),
        sa.CheckConstraint("state IN ('DRAFT', 'SELECTED', 'ARCHIVED')", name="state"),
        sa.CheckConstraint("scenario_type IN ('BASE', 'PRUDENT', 'CUSTOM')", name="scenario_type"),
        sa.Index("ix_pricing_scenarios__tenant_case", "tenant_id", "case_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    source_snapshot_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    scenario_key: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    scenario_type: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    state: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    assumptions_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    sales_total_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    total_cost_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    gross_margin_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    gross_margin_rate_bps: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    source_snapshot_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class FinancialReportPublicationRecord(TenantScopedRecord, Base):
    """One immutable patron act that makes a financial snapshot readable."""

    __tablename__ = "financial_report_publications"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id", "snapshot_id"],
            ["financial_report_snapshots.tenant_id", "financial_report_snapshots.id"],
            name="fk_financial_publication__snapshot",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "patron_membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_financial_publication__patron",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "snapshot_id", name="uq_financial_publication__snapshot"),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_financial_publication__command"),
        sa.Index("ix_financial_publication__tenant_snapshot", "tenant_id", "snapshot_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    snapshot_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    patron_membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    published_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

class PricingImportBatchRecord(TenantScopedRecord, Base):
    """Immutable normalized import batch; the uploaded binary is never stored."""

    __tablename__ = "pricing_import_batches"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_pricing_import_batches__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_pricing_import_batches__case",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_pricing_import_batches__tenant_id"),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_pricing_import_batches__command"),
        sa.CheckConstraint(
            "document_kind IN ('DPGF', 'BPU', 'EXCEL')", name="document_kind"
        ),
        sa.CheckConstraint("state IN ('PREVIEWED', 'COMMITTED')", name="state"),
        sa.CheckConstraint("aggregate_revision > 0", name="aggregate_revision_positive"),
        sa.CheckConstraint("row_count >= 0", name="row_count_non_negative"),
        sa.CheckConstraint(
            "valid_row_count >= 0 AND valid_row_count <= row_count",
            name="valid_rows_bound",
        ),
        sa.CheckConstraint("error_count >= 0", name="error_count_non_negative"),
        sa.CheckConstraint("total_minor >= 0", name="total_minor_non_negative"),
        sa.CheckConstraint("source_sha256 ~ '^[a-f0-9]{64}$'", name="source_sha256"),
        sa.Index("ix_pricing_import_batches__tenant_case", "tenant_id", "case_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    document_kind: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    source_sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    aggregate_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    row_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    valid_row_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    error_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    total_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

class PricingImportRowRecord(TenantScopedRecord, Base):
    """Immutable normalized import row; no original file content is retained."""

    __tablename__ = "pricing_import_rows"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_pricing_import_rows__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "batch_id"],
            ["pricing_import_batches.tenant_id", "pricing_import_batches.id"],
            name="fk_pricing_import_rows__batch",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_pricing_import_rows__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "batch_id", "row_number", name="uq_pricing_import_row_number"
        ),
        sa.CheckConstraint("row_number >= 1", name="row_number_positive"),
        sa.CheckConstraint(
            "designation IS NULL OR length(trim(designation)) > 0", name="designation"
        ),
        sa.CheckConstraint(
            "quantity_decimal IS NULL OR quantity_decimal <> ''", name="quantity_decimal_non_empty"
        ),
        sa.CheckConstraint(
            "unit_price_minor IS NULL OR unit_price_minor >= 0", name="unit_price_non_negative"
        ),
        sa.CheckConstraint("total_minor IS NULL OR total_minor >= 0", name="total_non_negative"),
        sa.Index("ix_pricing_import_rows__tenant_batch", "tenant_id", "batch_id", "row_number"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    batch_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    row_number: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    code: Mapped[str | None] = mapped_column(sa.String(120))
    designation: Mapped[str | None] = mapped_column(sa.String(500))
    unit: Mapped[str | None] = mapped_column(sa.String(32))
    quantity_decimal: Mapped[str | None] = mapped_column(sa.String(32))
    unit_price_minor: Mapped[int | None] = mapped_column(sa.BigInteger)
    total_minor: Mapped[int | None] = mapped_column(sa.BigInteger)
    error_codes_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)

class PricingImportTransitionRecord(TenantScopedRecord, Base):
    """Append-only lifecycle transition for one normalized pricing import batch."""

    __tablename__ = "pricing_import_transitions"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_pricing_import_transitions__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "batch_id"],
            ["pricing_import_batches.tenant_id", "pricing_import_batches.id"],
            name="fk_pricing_import_transitions__batch",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_pricing_import_transitions__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "batch_id", "version", name="uq_pricing_import_transition_version"
        ),
        sa.UniqueConstraint(
            "tenant_id", "command_id", name="uq_pricing_import_transition_command"
        ),
        sa.CheckConstraint("version > 1", name="version_positive"),
        sa.CheckConstraint("from_state = 'PREVIEWED'", name="from_state"),
        sa.CheckConstraint("to_state = 'COMMITTED'", name="to_state"),
        sa.Index(
            "ix_pricing_import_transitions__tenant_batch_version",
            "tenant_id",
            "batch_id",
            "version",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    batch_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    from_state: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    to_state: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

class PricingScenarioTransitionRecord(TenantScopedRecord, Base):
    """Append-only selection/archive history for a private pricing scenario."""

    __tablename__ = "pricing_scenario_transitions"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id", "scenario_id"],
            ["pricing_scenarios.tenant_id", "pricing_scenarios.id"],
            name="fk_pricing_scenario_transitions__scenario",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_pricing_scenario_transitions__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "scenario_id", "version", name="uq_pricing_scenario_transitions__version"
        ),
        sa.UniqueConstraint(
            "tenant_id", "command_id", name="uq_pricing_scenario_transitions__command"
        ),
        sa.CheckConstraint("version > 1", name="version_positive"),
        sa.CheckConstraint("from_state IN ('DRAFT', 'SELECTED')", name="from_state"),
        sa.CheckConstraint("to_state IN ('SELECTED', 'ARCHIVED')", name="to_state"),
        sa.Index(
            "ix_pricing_scenario_transitions__tenant_scenario_version",
            "tenant_id",
            "scenario_id",
            "version",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    scenario_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    from_state: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    to_state: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    reason_code: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

