from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.persistence.base import Base, TenantScopedRecord


class PatronActionRecord(TenantScopedRecord, Base):
    """Current patron action projection; every write is command-durable and versioned."""

    __tablename__ = "patron_actions"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_patron_actions__tenant", ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_patron_actions__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "functional_key", name="uq_patron_actions__functional_key"
        ),
        sa.CheckConstraint("aggregate_revision > 0", name="aggregate_revision_positive"),
        sa.CheckConstraint(
            "state IN ('OPEN', 'IN_PROGRESS', 'WAITING', 'COMPLETED', 'ABANDONED')",
            name="state",
        ),
        sa.CheckConstraint(
            "severity IN ('URGENT', 'BLOCKING', 'AT_RISK', 'MONITOR')", name="severity"
        ),
        sa.CheckConstraint(
            "action_type IN ("
            "'REVIEW_PREPARATION', 'CONTROL_SUBMISSION', 'VALIDATE_PRICE', "
            "'DECIDE_GO_NO_GO'"
            ")",
            name="action_type",
        ),
        sa.Index("ix_patron_actions__tenant_state_due", "tenant_id", "state", "severity", "due_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    case_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    functional_key: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    action_type: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    severity: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    title: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    why_now: Mapped[str] = mapped_column(sa.String(1000), nullable=False)
    impact: Mapped[str] = mapped_column(sa.String(1000), nullable=False)
    recommended_action: Mapped[str] = mapped_column(sa.String(1000), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    source_refs_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    aggregate_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class PatronActionTransitionRecord(TenantScopedRecord, Base):
    """Append-only state transition history for a patron action."""

    __tablename__ = "patron_action_transitions"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id", "action_id"],
            ["patron_actions.tenant_id", "patron_actions.id"],
            name="fk_patron_action_transitions__action",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_patron_action_transitions__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "action_id",
            "aggregate_revision",
            name="uq_patron_action_transitions__revision",
        ),
        sa.UniqueConstraint(
            "tenant_id", "command_id", name="uq_patron_action_transitions__command"
        ),
        sa.CheckConstraint("aggregate_revision > 1", name="aggregate_revision_positive"),
        sa.CheckConstraint(
            "from_state IN ('OPEN', 'IN_PROGRESS', 'WAITING')",
            name="from_state",
        ),
        sa.CheckConstraint(
            "to_state IN ('IN_PROGRESS', 'WAITING', 'COMPLETED', 'ABANDONED')",
            name="to_state",
        ),
        sa.Index(
            "ix_patron_action_transitions__tenant_action_revision",
            "tenant_id",
            "action_id",
            "aggregate_revision",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    action_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    from_state: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    to_state: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    reason_code: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    aggregate_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))

