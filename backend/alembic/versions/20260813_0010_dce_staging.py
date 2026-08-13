"""Create DCE-STAGING-01 secure staging registry.

Revision ID: 20260813_0010
Revises: 20260813_0009
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260813_0010"
down_revision = "20260813_0009"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
TIMESTAMPTZ = sa.DateTime(timezone=True)
NOW = sa.text("CURRENT_TIMESTAMP")


def _audit_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=NOW),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False, server_default=NOW),
    ]


def upgrade() -> None:
    op.create_table(
        "dce_staged_objects",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("consultation_id", UUID, nullable=False),
        sa.Column("storage_key", sa.String(1000), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("expected_byte_size", sa.BigInteger(), nullable=False),
        sa.Column("actual_byte_size", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.CHAR(64), nullable=True),
        sa.Column("media_type", sa.String(180), nullable=True),
        sa.Column("source_channel", sa.String(120), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("scan_verdict", sa.String(32), nullable=True),
        sa.Column("scanner_name", sa.String(120), nullable=True),
        sa.Column("scanner_signature_version", sa.String(240), nullable=True),
        sa.Column("scanned_at", TIMESTAMPTZ, nullable=True),
        sa.Column("rejection_code", sa.String(120), nullable=True),
        sa.Column("expires_at", TIMESTAMPTZ, nullable=False),
        sa.Column("consumed_by_dce_version_id", UUID, nullable=True),
        sa.Column("consumed_at", TIMESTAMPTZ, nullable=True),
        sa.Column("created_by_actor_id", UUID, nullable=True),
        sa.Column("updated_by_actor_id", UUID, nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_dce_staged_objects__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "consultation_id"],
            ["consultations.tenant_id", "consultations.id"],
            name="fk_dce_staged_objects__consultations__tenant_consultation_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "consumed_by_dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_dce_staged_objects__dce_versions__tenant_consumed_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_dce_staged_objects__tenant_id"),
        sa.UniqueConstraint("storage_key", name="uq_dce_staged_objects__storage_key"),
        sa.CheckConstraint("expected_byte_size > 0", name="expected_byte_size_positive"),
        sa.CheckConstraint(
            "actual_byte_size IS NULL OR actual_byte_size > 0",
            name="actual_byte_size_positive",
        ),
        sa.CheckConstraint(
            "sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$'",
            name="sha256_lowercase",
        ),
        sa.CheckConstraint(
            "state IN ('AWAITING_UPLOAD', 'QUARANTINED', 'CLEAN', 'REJECTED', "
            "'CONSUMED', 'EXPIRED')",
            name="state",
        ),
        sa.CheckConstraint(
            "scan_verdict IS NULL OR scan_verdict IN ('CLEAN', 'INFECTED', 'ERROR')",
            name="scan_verdict",
        ),
        sa.CheckConstraint(
            "state <> 'CONSUMED' OR "
            "(consumed_by_dce_version_id IS NOT NULL AND consumed_at IS NOT NULL)",
            name="consumed_fields_required",
        ),
        sa.CheckConstraint(
            "state = 'CONSUMED' OR "
            "(consumed_by_dce_version_id IS NULL AND consumed_at IS NULL)",
            name="consumed_fields_only_when_consumed",
        ),
        sa.CheckConstraint(
            "state <> 'CLEAN' OR "
            "(actual_byte_size IS NOT NULL AND sha256 IS NOT NULL AND media_type IS NOT NULL "
            "AND scan_verdict = 'CLEAN' AND scanner_name IS NOT NULL "
            "AND scanner_signature_version IS NOT NULL AND scanned_at IS NOT NULL)",
            name="clean_metadata_required",
        ),
    )
    op.create_index(
        "ix_dce_staged_objects_tenant_id",
        "dce_staged_objects",
        ["tenant_id"],
    )
    op.create_index(
        "ix_dce_staged_objects__tenant_consultation_state",
        "dce_staged_objects",
        ["tenant_id", "consultation_id", "state"],
    )
    op.create_index(
        "ix_dce_staged_objects__tenant_expiry",
        "dce_staged_objects",
        ["tenant_id", "expires_at"],
    )
    op.create_foreign_key(
        "fk_dce_documents__dce_staged_objects__tenant_storage_object_id",
        "dce_documents",
        "dce_staged_objects",
        ["tenant_id", "storage_object_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )

    op.execute(
        """
        CREATE FUNCTION protect_dce_staged_object_identity() RETURNS trigger AS $$
        BEGIN
          IF OLD.tenant_id IS DISTINCT FROM NEW.tenant_id
             OR OLD.consultation_id IS DISTINCT FROM NEW.consultation_id
             OR OLD.storage_key IS DISTINCT FROM NEW.storage_key
             OR OLD.original_filename IS DISTINCT FROM NEW.original_filename
             OR OLD.expected_byte_size IS DISTINCT FROM NEW.expected_byte_size
             OR OLD.source_channel IS DISTINCT FROM NEW.source_channel
             OR OLD.expires_at IS DISTINCT FROM NEW.expires_at THEN
            RAISE EXCEPTION 'DCE_STAGED_OBJECT_IDENTITY_IMMUTABLE';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE FUNCTION enforce_dce_staged_object_transition() RETURNS trigger AS $$
        BEGIN
          IF OLD.state = 'AWAITING_UPLOAD'
             AND NEW.state IN ('QUARANTINED', 'REJECTED', 'EXPIRED') THEN
            RETURN NEW;
          ELSIF OLD.state = 'QUARANTINED'
             AND NEW.state IN ('CLEAN', 'REJECTED', 'EXPIRED') THEN
            RETURN NEW;
          ELSIF OLD.state = 'CLEAN'
             AND NEW.state IN ('CONSUMED', 'EXPIRED') THEN
            RETURN NEW;
          ELSIF OLD.state = 'REJECTED' AND NEW.state = 'EXPIRED' THEN
            RETURN NEW;
          END IF;
          RAISE EXCEPTION 'DCE_STAGED_OBJECT_INVALID_TRANSITION';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_dce_staged_objects_immutable_identity
        BEFORE UPDATE ON dce_staged_objects
        FOR EACH ROW EXECUTE FUNCTION protect_dce_staged_object_identity();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_dce_staged_objects_state_transition
        BEFORE UPDATE ON dce_staged_objects
        FOR EACH ROW EXECUTE FUNCTION enforce_dce_staged_object_transition();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_dce_staged_objects_state_transition ON dce_staged_objects"
    )
    op.execute("DROP FUNCTION IF EXISTS enforce_dce_staged_object_transition()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_dce_staged_objects_immutable_identity ON dce_staged_objects"
    )
    op.execute("DROP FUNCTION IF EXISTS protect_dce_staged_object_identity()")
    op.drop_constraint(
        "fk_dce_documents__dce_staged_objects__tenant_storage_object_id",
        "dce_documents",
        type_="foreignkey",
    )
    op.drop_index("ix_dce_staged_objects__tenant_expiry", table_name="dce_staged_objects")
    op.execute("DROP INDEX IF EXISTS ix_dce_staged_objects_tenant_id")
    op.drop_index(
        "ix_dce_staged_objects__tenant_consultation_state",
        table_name="dce_staged_objects",
    )
    op.drop_table("dce_staged_objects")
