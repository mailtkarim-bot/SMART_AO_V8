"""Physical records for the DATA-01 command durability substrate.

These records deliberately contain no Case, Consultation, DceVersion or Decision
business state. They provide tenant isolation, durable idempotence and the
post-commit event delivery boundary used by future application handlers.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantScopedRecord


class TenantRecord(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        sa.CheckConstraint(
            "lifecycle IN ('ACTIVE', 'SUSPENDED', 'ARCHIVED')",
            name="lifecycle",
        ),
        sa.Index("ix_tenants__lifecycle", "lifecycle"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    slug: Mapped[str] = mapped_column(sa.String(120), nullable=False, unique=True)
    lifecycle: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


class CommandReceiptRecord(TenantScopedRecord, Base):
    __tablename__ = "command_receipts"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="tenant",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "actor_id",
            "command_type",
            "idempotency_key",
            name="uq_command_receipts__tenant_actor_type_key",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "command_id",
            name="uq_command_receipts__tenant_command_id",
        ),
        sa.CheckConstraint(
            "status IN ('PROCESSING', 'SUCCEEDED', 'REJECTED', "
            "'FAILED_RETRYABLE', 'EXPIRED')",
            name="status",
        ),
        sa.Index("ix_command_receipts__lease_recovery", "status", "lease_expires_at"),
        sa.Index("ix_command_receipts__correlation", "tenant_id", "correlation_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_type: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    request_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    lease_expires_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    aggregate_refs_json: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    http_status: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    result_code: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    response_body_json: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    event_ids_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class DomainEventRecord(TenantScopedRecord, Base):
    __tablename__ = "domain_events"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="tenant",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_domain_events__tenant_id"),
        sa.Index(
            "ix_domain_events__tenant_aggregate_occurred",
            "tenant_id",
            "aggregate_type",
            "aggregate_id",
            "occurred_at",
        ),
        sa.Index("ix_domain_events__correlation", "correlation_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    aggregate_type: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    aggregate_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    payload_version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    command_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    causation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class OutboxMessageRecord(TenantScopedRecord, Base):
    __tablename__ = "outbox_messages"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["domain_events.tenant_id", "domain_events.id"],
            name="tenant_event",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("event_id", "topic", name="uq_outbox_messages__event_topic"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PUBLISHED', 'RETRY', 'FAILED')",
            name="status",
        ),
        sa.Index(
            "ix_outbox_messages__pending_delivery",
            "next_attempt_at",
            postgresql_where=sa.text("status IN ('PENDING', 'RETRY')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    event_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    topic: Mapped[str] = mapped_column(sa.String(180), nullable=False)
    payload_version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    attempt_count: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0, server_default="0"
    )
    next_attempt_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(sa.String(240), nullable=False)


class ProcessInboxRecord(TenantScopedRecord, Base):
    __tablename__ = "process_inbox"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["domain_events.tenant_id", "domain_events.id"],
            name="tenant_event",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "process_name",
            "event_id",
            name="uq_process_inbox__process_event",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'SUCCEEDED', 'RETRY', 'FAILED')",
            name="status",
        ),
        sa.Index("ix_process_inbox__state_retry", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    process_name: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    event_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    attempt_count: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0, server_default="0"
    )
    last_error_code: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
