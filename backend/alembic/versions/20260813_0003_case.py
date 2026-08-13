"""Create Case persistence and reference histories.

Revision ID: 20260813_0003
Revises: 20260813_0002
Create Date: 2026-08-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260813_0003"
down_revision = "20260813_0002"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())
TIMESTAMPTZ = sa.DateTime(timezone=True)
NOW = sa.text("CURRENT_TIMESTAMP")


def _audit_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=NOW),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False, server_default=NOW),
    ]


def upgrade() -> None:
    op.create_table(
        "cases",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("aggregate_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("functional_identity_hash", sa.CHAR(64), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("object_description", sa.Text(), nullable=True),
        sa.Column("business_origin", sa.String(32), nullable=False),
        sa.Column("origin_reference_id", UUID, nullable=True),
        sa.Column("origin_rationale", sa.Text(), nullable=True),
        sa.Column("consultation_id", UUID, nullable=True),
        sa.Column("scope_kind", sa.String(32), nullable=False),
        sa.Column("scope_json", JSONB, nullable=False),
        sa.Column("scope_fingerprint", sa.CHAR(64), nullable=False),
        sa.Column("applicable_dce_version_id", UUID, nullable=True),
        sa.Column("lifecycle", sa.String(32), nullable=False),
        sa.Column("commercial_stage", sa.String(48), nullable=False),
        sa.Column("decision_readiness", sa.String(32), nullable=False),
        sa.Column("dce_freshness", sa.String(32), nullable=False),
        sa.Column("responsibility_status", sa.String(40), nullable=False),
        sa.Column("stopped_reason", sa.Text(), nullable=True),
        sa.Column("stopped_at", TIMESTAMPTZ, nullable=True),
        sa.Column("archived_reason", sa.Text(), nullable=True),
        sa.Column("archived_at", TIMESTAMPTZ, nullable=True),
        sa.Column("created_by_actor_id", UUID, nullable=True),
        sa.Column("updated_by_actor_id", UUID, nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_cases__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "consultation_id"],
            ["consultations.tenant_id", "consultations.id"],
            name="fk_cases__consultations__tenant_consultation_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "applicable_dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_cases__dce_versions__tenant_applicable_dce_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_cases__tenant_id"),
        sa.CheckConstraint(
            "business_origin IN ('MANUAL', 'OPPORTUNITY', 'IMPORT', 'CLIENT_REQUEST')",
            name="business_origin",
        ),
        sa.CheckConstraint(
            "consultation_id IS NOT NULL OR business_origin = 'MANUAL'",
            name="consultation_required_unless_manual",
        ),
        sa.CheckConstraint(
            "business_origin <> 'MANUAL' OR "
            "NULLIF(BTRIM(origin_rationale), '') IS NOT NULL",
            name="manual_origin_rationale",
        ),
        sa.CheckConstraint(
            "scope_kind IN ('SINGLE_LOT', 'MULTI_LOT', 'TRANCHE', 'VARIANT', 'CUSTOM')",
            name="scope_kind",
        ),
        sa.CheckConstraint(
            "lifecycle IN ('ACTIVE', 'STOPPED', 'ARCHIVED')",
            name="lifecycle",
        ),
        sa.CheckConstraint(
            "commercial_stage IN ("
            "'INTAKE', 'ANALYSIS', 'AWAITING_DECISION', 'OFFER_PREPARATION', "
            "'READY_FOR_PRICING', 'PRICING', 'READY_FOR_FINAL_CONTROL', "
            "'READY_FOR_SUBMISSION', 'SUBMITTED', 'OUTCOME_KNOWN', 'AWARDED', "
            "'EXECUTION'"
            ")",
            name="commercial_stage",
        ),
        sa.CheckConstraint(
            "decision_readiness IN "
            "('NOT_ASSESSED', 'NOT_READY', 'READY_WITH_UNKNOWNS', 'READY')",
            name="decision_readiness",
        ),
        sa.CheckConstraint(
            "dce_freshness IN ('NO_DCE', 'CURRENT', 'REVIEW_REQUIRED')",
            name="dce_freshness",
        ),
        sa.CheckConstraint(
            "responsibility_status IN "
            "('UNASSIGNED', 'ASSIGNED', 'ASSIGNMENT_REVIEW_REQUIRED')",
            name="responsibility_status",
        ),
        sa.CheckConstraint(
            "lifecycle <> 'STOPPED' OR "
            "(stopped_reason IS NOT NULL AND stopped_at IS NOT NULL)",
            name="stopped_reason_when_stopped",
        ),
        sa.CheckConstraint(
            "lifecycle <> 'ARCHIVED' OR "
            "(archived_reason IS NOT NULL AND archived_at IS NOT NULL)",
            name="archived_reason_when_archived",
        ),
    )
    op.create_index("ix_cases_tenant_id", "cases", ["tenant_id"])
    op.create_index(
        "ux_cases__tenant_active_functional_identity",
        "cases",
        ["tenant_id", "functional_identity_hash"],
        unique=True,
        postgresql_where=sa.text("lifecycle <> 'ARCHIVED'"),
    )
    op.create_index(
        "ix_cases__tenant_lifecycle_stage_updated",
        "cases",
        ["tenant_id", "lifecycle", "commercial_stage", sa.text("updated_at DESC")],
    )
    op.create_index(
        "ix_cases__tenant_applicable_dce_version",
        "cases",
        ["tenant_id", "applicable_dce_version_id"],
    )

    op.create_table(
        "case_consultation_links",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("case_id", UUID, nullable=False),
        sa.Column("consultation_id", UUID, nullable=False),
        sa.Column("scope_snapshot_json", JSONB, nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_actor_id", UUID, nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_case_consultation_links__cases__tenant_case_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "consultation_id"],
            ["consultations.tenant_id", "consultations.id"],
            name="fk_case_consult_links__consultation",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_case_consultation_links__tenant_id"),
    )
    op.create_index(
        "ix_case_consultation_links_tenant_id",
        "case_consultation_links",
        ["tenant_id"],
    )
    op.create_index(
        "ux_case_consultation_links__current_case",
        "case_consultation_links",
        ["tenant_id", "case_id"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )

    op.create_table(
        "case_dce_applicability_history",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, nullable=False),
        sa.Column("case_id", UUID, nullable=False),
        sa.Column("dce_version_id", UUID, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("set_by_actor_id", UUID, nullable=True),
        sa.Column("set_at", TIMESTAMPTZ, nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_case_dce_history__cases__tenant_case_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_case_dce_history__dce_versions__tenant_dce_version_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_case_dce_applicability_history__tenant_id",
        ),
    )
    op.create_index(
        "ix_case_dce_applicability_history_tenant_id",
        "case_dce_applicability_history",
        ["tenant_id"],
    )
    op.create_index(
        "ux_case_dce_history__current_case",
        "case_dce_applicability_history",
        ["tenant_id", "case_id"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )


def downgrade() -> None:
    op.drop_index(
        "ux_case_dce_history__current_case",
        table_name="case_dce_applicability_history",
    )
    op.drop_index(
        "ix_case_dce_applicability_history_tenant_id",
        table_name="case_dce_applicability_history",
    )
    op.drop_table("case_dce_applicability_history")
    op.drop_index(
        "ux_case_consultation_links__current_case",
        table_name="case_consultation_links",
    )
    op.drop_index(
        "ix_case_consultation_links_tenant_id",
        table_name="case_consultation_links",
    )
    op.drop_table("case_consultation_links")
    op.drop_index("ix_cases__tenant_applicable_dce_version", table_name="cases")
    op.drop_index("ix_cases__tenant_lifecycle_stage_updated", table_name="cases")
    op.drop_index("ux_cases__tenant_active_functional_identity", table_name="cases")
    op.drop_index("ix_cases_tenant_id", table_name="cases")
    op.drop_table("cases")
