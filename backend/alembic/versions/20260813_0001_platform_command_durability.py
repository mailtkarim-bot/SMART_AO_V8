"""Create DATA-01 platform command durability substrate.

Revision ID: 20260813_0001
Revises:
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260813_0001"
down_revision = None
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())
TIMESTAMPTZ = sa.DateTime(timezone=True)
NOW = sa.text("CURRENT_TIMESTAMP")


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("lifecycle", sa.String(32), nullable=False),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=NOW),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False, server_default=NOW),
        sa.UniqueConstraint("slug", name="uq_tenants__slug"),
        sa.CheckConstraint(
            "lifecycle IN ('ACTIVE', 'SUSPENDED', 'ARCHIVED')",
            name="lifecycle",
        ),
    )
    op.create_index("ix_tenants__lifecycle", "tenants", ["lifecycle"])

    op.create_table(
        "command_receipts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("actor_id", UUID, nullable=False),
        sa.Column("command_id", UUID, nullable=False),
        sa.Column("command_type", sa.String(120), nullable=False),
        sa.Column("idempotency_key", UUID, nullable=False),
        sa.Column("request_hash", sa.CHAR(64), nullable=False),
        sa.Column("correlation_id", UUID, nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("lease_expires_at", TIMESTAMPTZ, nullable=True),
        sa.Column("aggregate_refs_json", JSONB, nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("result_code", sa.String(120), nullable=True),
        sa.Column("response_body_json", JSONB, nullable=True),
        sa.Column(
            "event_ids_json",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("completed_at", TIMESTAMPTZ, nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=NOW),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False, server_default=NOW),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_command_receipts__tenants__tenant_id",
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
    )
    op.create_index("ix_command_receipts_tenant_id", "command_receipts", ["tenant_id"])
    op.create_index(
        "ix_command_receipts__lease_recovery",
        "command_receipts",
        ["status", "lease_expires_at"],
    )
    op.create_index(
        "ix_command_receipts__correlation",
        "command_receipts",
        ["tenant_id", "correlation_id"],
    )

    op.create_table(
        "domain_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("aggregate_type", sa.String(120), nullable=False),
        sa.Column("aggregate_id", UUID, nullable=False),
        sa.Column("aggregate_revision", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("payload_version", sa.Integer(), nullable=False),
        sa.Column("payload_json", JSONB, nullable=False),
        sa.Column("actor_id", UUID, nullable=True),
        sa.Column("command_id", UUID, nullable=True),
        sa.Column("correlation_id", UUID, nullable=True),
        sa.Column("causation_id", UUID, nullable=True),
        sa.Column("occurred_at", TIMESTAMPTZ, nullable=False, server_default=NOW),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=NOW),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False, server_default=NOW),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_domain_events__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_domain_events__tenant_id"),
    )
    op.create_index("ix_domain_events_tenant_id", "domain_events", ["tenant_id"])
    op.create_index(
        "ix_domain_events__tenant_aggregate_occurred",
        "domain_events",
        ["tenant_id", "aggregate_type", "aggregate_id", "occurred_at"],
    )
    op.create_index("ix_domain_events__correlation", "domain_events", ["correlation_id"])

    op.create_table(
        "outbox_messages",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("event_id", UUID, nullable=False),
        sa.Column("topic", sa.String(180), nullable=False),
        sa.Column("payload_version", sa.Integer(), nullable=False),
        sa.Column("payload_json", JSONB, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", TIMESTAMPTZ, nullable=True),
        sa.Column("published_at", TIMESTAMPTZ, nullable=True),
        sa.Column("dedupe_key", sa.String(240), nullable=False),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=NOW),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False, server_default=NOW),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_outbox_messages__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["domain_events.tenant_id", "domain_events.id"],
            name="fk_outbox_messages__domain_events__tenant_event_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("event_id", "topic", name="uq_outbox_messages__event_topic"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PUBLISHED', 'RETRY', 'FAILED')",
            name="status",
        ),
    )
    op.create_index("ix_outbox_messages_tenant_id", "outbox_messages", ["tenant_id"])
    op.create_index(
        "ix_outbox_messages__pending_delivery",
        "outbox_messages",
        ["next_attempt_at"],
        postgresql_where=sa.text("status IN ('PENDING', 'RETRY')"),
    )

    op.create_table(
        "process_inbox",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("process_name", sa.String(120), nullable=False),
        sa.Column("event_id", UUID, nullable=False),
        sa.Column("correlation_id", UUID, nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(120), nullable=True),
        sa.Column("completed_at", TIMESTAMPTZ, nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=NOW),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False, server_default=NOW),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_process_inbox__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["domain_events.tenant_id", "domain_events.id"],
            name="fk_process_inbox__domain_events__tenant_event_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("process_name", "event_id", name="uq_process_inbox__process_event"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'SUCCEEDED', 'RETRY', 'FAILED')",
            name="status",
        ),
    )
    op.create_index("ix_process_inbox_tenant_id", "process_inbox", ["tenant_id"])
    op.create_index(
        "ix_process_inbox__state_retry",
        "process_inbox",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_process_inbox__state_retry", table_name="process_inbox")
    op.drop_index("ix_process_inbox_tenant_id", table_name="process_inbox")
    op.drop_table("process_inbox")
    op.drop_index("ix_outbox_messages__pending_delivery", table_name="outbox_messages")
    op.drop_index("ix_outbox_messages_tenant_id", table_name="outbox_messages")
    op.drop_table("outbox_messages")
    op.drop_index("ix_domain_events__correlation", table_name="domain_events")
    op.drop_index("ix_domain_events_tenant_id", table_name="domain_events")
    op.drop_index(
        "ix_domain_events__tenant_aggregate_occurred",
        table_name="domain_events",
    )
    op.drop_table("domain_events")
    op.drop_index("ix_command_receipts__correlation", table_name="command_receipts")
    op.drop_index("ix_command_receipts_tenant_id", table_name="command_receipts")
    op.drop_index("ix_command_receipts__lease_recovery", table_name="command_receipts")
    op.drop_table("command_receipts")
    op.drop_index("ix_tenants__lifecycle", table_name="tenants")
    op.drop_table("tenants")
