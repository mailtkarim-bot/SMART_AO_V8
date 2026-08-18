"""SQLAlchemy records for SEC-01 identity and tenant membership persistence."""

from __future__ import annotations

# ruff: noqa: E501
from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.persistence.base import Base, TenantScopedRecord


class IdentityRecord(Base):
    """A person that can authenticate independently from any tenant membership."""

    __tablename__ = "identities"
    __table_args__ = (
        sa.CheckConstraint(
            "email_normalized = lower(email_normalized) AND length(trim(email_normalized)) > 0",
            name="email_normalized",
        ),
        sa.CheckConstraint(
            "lifecycle IN ('PENDING_VERIFICATION', 'ACTIVE', 'SUSPENDED', 'LOCKED', 'ARCHIVED')",
            name="lifecycle",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    email_normalized: Mapped[str] = mapped_column(sa.String(320), nullable=False, unique=True)
    lifecycle: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


class PasswordCredentialRecord(Base):
    """One non-reversible Argon2id credential for an identity."""

    __tablename__ = "password_credentials"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["identity_id"],
            ["identities.id"],
            name="fk_pwdcred__identity",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("identity_id", name="uq_pwdcred__identity"),
        sa.CheckConstraint(
            "algorithm = 'ARGON2ID' AND password_hash LIKE '$argon2id$%'",
            name="argon2id",
        ),
        sa.CheckConstraint("parameters_version >= 1", name="parameters_version"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    identity_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    password_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    algorithm: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    parameters_version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    must_change: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


class TenantMembershipRecord(TenantScopedRecord, Base):
    """The tenant-scoped authorization relationship for one authenticated identity."""

    __tablename__ = "tenant_memberships"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_memberships__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["identity_id"],
            ["identities.id"],
            name="fk_memberships__identity",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "identity_id", name="uq_memberships__tenant_identity"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_memberships__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "id", "identity_id", name="uq_memberships__tenant_id_identity_id"
        ),
        sa.CheckConstraint(
            "role IN ("
            "'PATRON_ADMIN', 'PATRON_DELEGATE', 'COLLABORATEUR', "
            "'PARTENAIRE_EXTERNAL', 'SUPPORT_BREAK_GLASS', 'SYSTEM'"
            ")",
            name="role",
        ),
        sa.CheckConstraint(
            "state IN ('INVITED', 'ACTIVE', 'SUSPENDED', 'REVOKED', 'EXPIRED')",
            name="state",
        ),
        sa.CheckConstraint(
            "(state = 'INVITED' AND activated_at IS NULL AND revoked_at IS NULL) OR "
            "(state IN ('ACTIVE', 'SUSPENDED', 'EXPIRED') "
            "AND activated_at IS NOT NULL AND revoked_at IS NULL) OR "
            "(state = 'REVOKED' AND revoked_at IS NOT NULL)",
            name="timestamps",
        ),
        sa.Index(
            "ux_memberships__active_patron",
            "tenant_id",
            unique=True,
            postgresql_where=sa.text("role = 'PATRON_ADMIN' AND state = 'ACTIVE'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    identity_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    role: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class TenantBootstrapTokenRecord(TenantScopedRecord, Base):
    """The one-time bootstrap secret hash for the first tenant patron."""

    __tablename__ = "tenant_bootstrap_tokens"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_bootstrap__tenant",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", name="uq_bootstrap__tenant"),
        sa.UniqueConstraint("token_hash", name="uq_bootstrap__token_hash"),
        sa.CheckConstraint("token_hash ~ '^[a-f0-9]{64}$'", name="token_hash"),
        sa.CheckConstraint("expires_at > issued_at", name="expiry"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    token_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class SecurityAuditEventRecord(Base):
    """Append-only SEC-01 security event; tenant is nullable only for anonymous attempts."""

    __tablename__ = "security_audit_events"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_security_audit__tenant", ondelete="RESTRICT"
        ),
        sa.CheckConstraint("schema_version >= 1", name="schema_version"),
        sa.CheckConstraint(
            "event_type IN ("
            "'AUTH_LOGIN_SUCCEEDED', 'AUTH_LOGIN_DENIED', "
            "'AUTH_REFRESH_SUCCEEDED', 'AUTH_REFRESH_DENIED', "
            "'AUTH_LOGOUT_SUCCEEDED', 'AUTH_SESSION_REJECTED', "
            "'AUTHZ_SUCCEEDED', 'AUTHZ_DENIED', 'AUTHZ_STEP_UP_REQUIRED'"
            ")",
            name="event_type",
        ),
        sa.CheckConstraint(
            "outcome IN ('SUCCEEDED', 'DENIED', 'FAILED', 'SUSPICIOUS')", name="outcome"
        ),
        sa.CheckConstraint("severity IN ('INFO', 'WARNING', 'CRITICAL')", name="severity"),
        sa.CheckConstraint(
            "actor_kind IS NULL OR actor_kind IN ("
            "'PATRON_ADMIN', 'PATRON_DELEGATE', 'COLLABORATEUR', "
            "'PARTENAIRE_EXTERNAL', 'SUPPORT_BREAK_GLASS', 'SYSTEM'"
            ")",
            name="actor_kind",
        ),
        sa.CheckConstraint(
            "auth_strength IS NULL OR auth_strength IN ('PASSWORD', 'MFA', 'MFA_STEP_UP')",
            name="auth_strength",
        ),
        sa.CheckConstraint(
            "source_ip_hash IS NULL OR source_ip_hash ~ '^[a-f0-9]{64}$'",
            name="source_ip_hash",
        ),
        sa.CheckConstraint("jsonb_typeof(metadata_json) = 'object'", name="metadata_object"),
        sa.Index("ix_security_audit__tenant_occurred", "tenant_id", "occurred_at"),
        sa.Index("ix_security_audit__event_occurred", "event_type", "occurred_at"),
        sa.Index("ix_security_audit__correlation", "correlation_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    schema_version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    tenant_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    identity_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    session_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    actor_kind: Mapped[str | None] = mapped_column(sa.String(32))
    auth_strength: Mapped[str | None] = mapped_column(sa.String(16))
    event_type: Mapped[str] = mapped_column(sa.String(48), nullable=False)
    outcome: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    severity: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    action: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(sa.String(64))
    resource_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    case_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    command_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    request_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    source_ip_hash: Mapped[str | None] = mapped_column(sa.CHAR(64))
    user_agent_family: Mapped[str | None] = mapped_column(sa.String(120))
    reason_code: Mapped[str | None] = mapped_column(sa.String(64))
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)


class CaseAssignmentRecord(TenantScopedRecord, Base):
    """Server-owned ReBAC scope granting one collaborator bounded Case access."""

    __tablename__ = "case_assignments"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_assignments__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_assignments__case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_assignments__membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "granted_by_membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_assignments__granted_by",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_assignments__tenant_id"),
        sa.CheckConstraint("state IN ('ACTIVE', 'SUSPENDED', 'ENDED', 'EXPIRED')", name="state"),
        sa.CheckConstraint(
            "jsonb_typeof(scope_actions_json) = 'array' "
            "AND jsonb_array_length(scope_actions_json) > 0",
            name="actions",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(scope_classifications_json) = 'array' "
            "AND jsonb_array_length(scope_classifications_json) > 0",
            name="classifications",
        ),
        sa.CheckConstraint("ends_at IS NULL OR ends_at > starts_at", name="end_after_start"),
        sa.CheckConstraint(
            "(state IN ('ACTIVE', 'SUSPENDED') AND ended_at IS NULL) OR "
            "(state IN ('ENDED', 'EXPIRED') AND ended_at IS NOT NULL)",
            name="state_timestamps",
        ),
        sa.CheckConstraint("aggregate_revision >= 0", name="aggregate_revision"),
        sa.Index(
            "ux_assignments__open_member_case",
            "tenant_id",
            "membership_id",
            "case_id",
            unique=True,
            postgresql_where=sa.text("state IN ('ACTIVE', 'SUSPENDED')"),
        ),
        sa.Index(
            "ix_assignments__context_resolution",
            "tenant_id",
            "membership_id",
            "state",
            "starts_at",
            "ends_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    aggregate_revision: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    scope_actions_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    scope_classifications_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    granted_by_membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class CaseAssignmentChangeEventRecord(TenantScopedRecord, Base):
    """Immutable patron-owned history of authority changes on one assignment."""

    __tablename__ = "case_assignment_change_events"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_assignment_change__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assignment_id"],
            ["case_assignments.tenant_id", "case_assignments.id"],
            name="fk_assignment_change__assignment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_assignment_change__case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "target_membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_assignment_change__target_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "author_membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_assignment_change__author_membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_assignment_change__tenant_id"),
        sa.CheckConstraint(
            "event_type IN ('ASSIGNMENT_CREATED', 'ASSIGNMENT_SCOPE_AMENDED', "
            "'ASSIGNMENT_SUSPENDED', 'ASSIGNMENT_REACTIVATED', 'ASSIGNMENT_ENDED')",
            name="event_type",
        ),
        sa.CheckConstraint(
            "resulting_revision >= 0 AND (previous_revision IS NULL OR previous_revision >= 0) "
            "AND ((event_type = 'ASSIGNMENT_CREATED' AND previous_revision IS NULL "
            "AND resulting_revision = 0) OR (event_type <> 'ASSIGNMENT_CREATED' "
            "AND previous_revision IS NOT NULL "
            "AND resulting_revision = previous_revision + 1))",
            name="revision",
        ),
        sa.CheckConstraint(
            "(previous_state IS NULL OR previous_state IN ('ACTIVE', 'SUSPENDED', "
            "'ENDED', 'EXPIRED')) AND resulting_state IN ('ACTIVE', 'SUSPENDED', "
            "'ENDED', 'EXPIRED')",
            name="state",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(resulting_scope_actions_json) = 'array' "
            "AND jsonb_array_length(resulting_scope_actions_json) > 0 "
            "AND jsonb_typeof(resulting_scope_classifications_json) = 'array' "
            "AND jsonb_array_length(resulting_scope_classifications_json) > 0",
            name="scope_result",
        ),
        sa.CheckConstraint(
            "(previous_scope_actions_json IS NULL AND previous_scope_classifications_json "
            "IS NULL) OR (jsonb_typeof(previous_scope_actions_json) = 'array' "
            "AND jsonb_array_length(previous_scope_actions_json) > 0 "
            "AND jsonb_typeof(previous_scope_classifications_json) = 'array' "
            "AND jsonb_array_length(previous_scope_classifications_json) > 0)",
            name="scope_previous",
        ),
        sa.CheckConstraint(
            "reason_code IS NULL OR reason_code IN ('PATRON_SUSPENDED', "
            "'WORKLOAD_REALLOCATION', 'CASE_PAUSED', 'ACCESS_REVIEW', 'PATRON_ENDED', "
            "'CASE_STOPPED', 'CASE_ARCHIVED', 'COLLABORATOR_UNAVAILABLE', "
            "'MEMBERSHIP_REVOKED', 'PATRON_REACTIVATED', 'CASE_RESUMED', "
            "'ACCESS_REVIEW_CLEARED')",
            name="reason",
        ),
        sa.Index(
            "ix_assignment_change__tenant_assignment",
            "tenant_id",
            "assignment_id",
            "created_at",
        ),
        sa.Index(
            "ix_assignment_change__tenant_case_target",
            "tenant_id",
            "case_id",
            "target_membership_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    assignment_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    target_membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    author_membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    previous_revision: Mapped[int | None] = mapped_column(sa.Integer)
    resulting_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    previous_state: Mapped[str | None] = mapped_column(sa.String(16))
    resulting_state: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(sa.String(40))
    previous_scope_actions_json: Mapped[list[str] | None] = mapped_column(JSONB(none_as_null=True))
    previous_scope_classifications_json: Mapped[list[str] | None] = mapped_column(
        JSONB(none_as_null=True)
    )
    resulting_scope_actions_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    resulting_scope_classifications_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class CaseAssignmentAcknowledgementRecord(TenantScopedRecord, Base):
    """Immutable collaborator acknowledgement of one assignment revision."""

    __tablename__ = "case_assignment_acknowledgements"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_assignment_ack__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assignment_id"],
            ["case_assignments.tenant_id", "case_assignments.id"],
            name="fk_assignment_ack__assignment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_assignment_ack__membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_assignment_ack__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "assignment_id",
            "actor_id",
            "assignment_revision",
            name="uq_assignment_ack__revision_actor",
        ),
        sa.CheckConstraint("assignment_revision >= 0", name="assignment_revision"),
        sa.Index(
            "ix_assignment_ack__tenant_assignment",
            "tenant_id",
            "assignment_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    assignment_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    assignment_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class AssignmentClarificationRequestRecord(TenantScopedRecord, Base):
    """Immutable operational clarification request linked to one assignment."""

    __tablename__ = "assignment_clarification_requests"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_assignment_clarification__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assignment_id"],
            ["case_assignments.tenant_id", "case_assignments.id"],
            name="fk_assignment_clarification__assignment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_assignment_clarification__case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_assignment_clarification__membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_assignment_clarification__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "functional_key", name="uq_assignment_clarification__functional_key"
        ),
        sa.CheckConstraint(
            "clarification_kind IN ('SCOPE', 'PRIORITY', 'DEADLINE', 'DOCUMENT', "
            "'RESPONSIBILITY', 'OTHER')",
            name="clarification_kind",
        ),
        sa.CheckConstraint("priority IN ('LOW', 'NORMAL', 'HIGH')", name="priority"),
        sa.CheckConstraint("state = 'OPEN'", name="state_open_only"),
        sa.Index(
            "ix_assignment_clarification__tenant_assignment",
            "tenant_id",
            "assignment_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    assignment_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    clarification_kind: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    subject: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    question: Mapped[str] = mapped_column(sa.String(2_000), nullable=False)
    requested_scope: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    priority: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(16), nullable=False, default="OPEN")
    functional_key: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class CaseAssignmentUnavailabilityRecord(TenantScopedRecord, Base):
    """Immutable collaborator unavailability observation for one assignment."""

    __tablename__ = "case_assignment_unavailabilities"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_assignment_unavailability__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assignment_id"],
            ["case_assignments.tenant_id", "case_assignments.id"],
            name="fk_assignment_unavailability__assignment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_assignment_unavailability__membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_assignment_unavailability__tenant_id"),
        sa.CheckConstraint(
            "reason_kind IN ('SICKNESS', 'LEAVE', 'CAPACITY_CONFLICT', 'SKILL_GAP', "
            "'ACCESS_PROBLEM', 'OTHER')",
            name="reason_kind",
        ),
        sa.CheckConstraint(
            "unavailable_until IS NULL OR unavailable_until > unavailable_from",
            name="period_ordered",
        ),
        sa.CheckConstraint(
            "known_deadline_impact = FALSE OR NULLIF(BTRIM(impact_note), '') IS NOT NULL",
            name="impact_note_required",
        ),
        sa.CheckConstraint("assignment_revision >= 0", name="assignment_revision"),
        sa.Index(
            "ix_assignment_unavailability__tenant_assignment",
            "tenant_id",
            "assignment_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    assignment_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    assignment_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    reason_kind: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    reason: Mapped[str] = mapped_column(sa.String(2_000), nullable=False)
    unavailable_from: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    unavailable_until: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    known_deadline_impact: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    impact_note: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class AssignmentInteractionPatronValidationRecord(TenantScopedRecord, Base):
    """Immutable patron acknowledgement of one typed collaborator interaction."""

    __tablename__ = "assignment_interaction_patron_validations"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_assignment_interaction_validation__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assignment_id"],
            ["case_assignments.tenant_id", "case_assignments.id"],
            name="fk_assignment_interaction_validation__assignment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_assignment_interaction_validation__case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "patron_membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_assignment_interaction_validation__patron",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_assignment_interaction_validation__tenant_id",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "interaction_kind",
            "interaction_id",
            name="uq_assignment_interaction_validation__source",
        ),
        sa.CheckConstraint(
            "interaction_kind IN "
            "('ACKNOWLEDGEMENT', 'CLARIFICATION_REQUEST', 'UNAVAILABILITY_REPORT')",
            name="interaction_kind",
        ),
        sa.CheckConstraint(
            "validation_code IN "
            "('ACKNOWLEDGEMENT_NOTED', 'CLARIFICATION_NOTED', 'UNAVAILABILITY_NOTED') "
            "AND ((interaction_kind = 'ACKNOWLEDGEMENT' "
            "AND validation_code = 'ACKNOWLEDGEMENT_NOTED') "
            "OR (interaction_kind = 'CLARIFICATION_REQUEST' "
            "AND validation_code = 'CLARIFICATION_NOTED') "
            "OR (interaction_kind = 'UNAVAILABILITY_REPORT' "
            "AND validation_code = 'UNAVAILABILITY_NOTED'))",
            name="kind_code",
        ),
        sa.Index(
            "ix_assignment_interaction_validation__tenant_assignment",
            "tenant_id",
            "assignment_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    assignment_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    interaction_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    interaction_kind: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    validation_code: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    patron_membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


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


class AuthSessionRecord(TenantScopedRecord, Base):
    """A revocable browser session bound to one tenant membership and identity."""

    __tablename__ = "auth_sessions"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_sessions__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "membership_id", "identity_id"],
            [
                "tenant_memberships.tenant_id",
                "tenant_memberships.id",
                "tenant_memberships.identity_id",
            ],
            name="fk_sessions__membership_identity",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_sessions__tenant_id"),
        sa.CheckConstraint("state IN ('ACTIVE', 'EXPIRED', 'REVOKED')", name="state"),
        sa.CheckConstraint(
            "auth_strength IN ('PASSWORD', 'MFA', 'MFA_STEP_UP')", name="auth_strength"
        ),
        sa.CheckConstraint("token_version >= 1", name="token_version"),
        sa.CheckConstraint("expires_at > issued_at", name="expiry"),
        sa.CheckConstraint("absolute_expires_at > issued_at", name="absolute_expiry"),
        sa.CheckConstraint("expires_at <= absolute_expires_at", name="expiry_bound"),
        sa.CheckConstraint("last_seen_at >= issued_at", name="last_seen"),
        sa.CheckConstraint(
            "(auth_strength = 'PASSWORD' AND mfa_verified_at IS NULL) OR "
            "(auth_strength IN ('MFA', 'MFA_STEP_UP') AND mfa_verified_at IS NOT NULL)",
            name="mfa_verified",
        ),
        sa.CheckConstraint(
            "(state IN ('ACTIVE', 'EXPIRED') AND revoked_at IS NULL AND revoke_reason IS NULL) OR "
            "(state = 'REVOKED' AND revoked_at IS NOT NULL AND revoke_reason IS NOT NULL)",
            name="revocation",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    identity_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    auth_strength: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    token_version: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)
    issued_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    mfa_verified_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(sa.String(64))


class RefreshTokenFamilyRecord(TenantScopedRecord, Base):
    """A single revocable refresh-token lineage for one browser session."""

    __tablename__ = "refresh_token_families"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_refresh_families__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "session_id"],
            ["auth_sessions.tenant_id", "auth_sessions.id"],
            name="fk_refresh_families__session",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_refresh_families__tenant_id"),
        sa.UniqueConstraint("tenant_id", "session_id", name="uq_refresh_families__tenant_session"),
        sa.CheckConstraint(
            "state IN ('ACTIVE', 'COMPROMISED', 'REVOKED', 'EXPIRED')", name="state"
        ),
        sa.CheckConstraint("expires_at > issued_at", name="expiry"),
        sa.CheckConstraint(
            "(state IN ('ACTIVE', 'EXPIRED') AND revoked_at IS NULL AND revoke_reason IS NULL) OR "
            "(state IN ('COMPROMISED', 'REVOKED') "
            "AND revoked_at IS NOT NULL AND revoke_reason IS NOT NULL)",
            name="revocation",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    session_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(sa.String(64))


class RefreshTokenRecord(TenantScopedRecord, Base):
    """One opaque refresh-token hash in a rotating refresh-token family."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_refresh_tokens__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "family_id"],
            ["refresh_token_families.tenant_id", "refresh_token_families.id"],
            name="fk_refresh_tokens__family",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "parent_token_id", "family_id"],
            [
                "refresh_tokens.tenant_id",
                "refresh_tokens.id",
                "refresh_tokens.family_id",
            ],
            name="fk_refresh_tokens__parent",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_refresh_tokens__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "id", "family_id", name="uq_refresh_tokens__tenant_id_family"
        ),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens__token_hash"),
        sa.CheckConstraint("token_hash ~ '^[a-f0-9]{64}$'", name="token_hash"),
        sa.CheckConstraint("state IN ('ACTIVE', 'ROTATED', 'REVOKED', 'EXPIRED')", name="state"),
        sa.CheckConstraint("expires_at > issued_at", name="expiry"),
        sa.CheckConstraint(
            "(state IN ('ACTIVE', 'EXPIRED') AND consumed_at IS NULL AND revoked_at IS NULL) OR "
            "(state = 'ROTATED' AND consumed_at IS NOT NULL AND revoked_at IS NULL) OR "
            "(state = 'REVOKED' AND revoked_at IS NOT NULL)",
            name="lifecycle",
        ),
        sa.Index(
            "ux_refresh_tokens__active_family",
            "family_id",
            unique=True,
            postgresql_where=sa.text("state = 'ACTIVE'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    family_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    parent_token_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    token_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class MfaFactorRecord(Base):
    """An identity-scoped TOTP secret or generated recovery-code factor."""

    __tablename__ = "mfa_factors"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["identity_id"],
            ["identities.id"],
            name="fk_mfa_factors__identity",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("identity_id", "id", name="uq_mfa_factors__identity_id"),
        sa.UniqueConstraint(
            "identity_id", "id", "factor_type", name="uq_mfa_factors__identity_id_type"
        ),
        sa.CheckConstraint("factor_type IN ('TOTP', 'RECOVERY_CODES')", name="factor_type"),
        sa.CheckConstraint("state IN ('PENDING', 'ACTIVE', 'DISABLED')", name="state"),
        sa.CheckConstraint(
            "(factor_type = 'TOTP' AND secret_ciphertext IS NOT NULL "
            "AND encryption_key_version IS NOT NULL AND encryption_key_version >= 1) OR "
            "(factor_type = 'RECOVERY_CODES' AND secret_ciphertext IS NULL "
            "AND encryption_key_version IS NULL)",
            name="secret_storage",
        ),
        sa.CheckConstraint(
            "(state = 'PENDING' AND verified_at IS NULL AND disabled_at IS NULL) OR "
            "(state = 'ACTIVE' AND verified_at IS NOT NULL AND disabled_at IS NULL) OR "
            "(state = 'DISABLED' AND disabled_at IS NOT NULL)",
            name="lifecycle",
        ),
        sa.Index(
            "ux_mfa_factors__active_totp",
            "identity_id",
            unique=True,
            postgresql_where=sa.text("factor_type = 'TOTP' AND state = 'ACTIVE'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    identity_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    factor_type: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    secret_ciphertext: Mapped[str | None] = mapped_column(sa.Text)
    encryption_key_version: Mapped[int | None] = mapped_column(sa.Integer)
    verified_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    disabled_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


class MfaRecoveryCodeRecord(Base):
    """One recovery-code hash, atomically consumed once without plaintext storage."""

    __tablename__ = "mfa_recovery_codes"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["identity_id"],
            ["identities.id"],
            name="fk_mfa_recovery_codes__identity",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["identity_id", "factor_id", "factor_type"],
            [
                "mfa_factors.identity_id",
                "mfa_factors.id",
                "mfa_factors.factor_type",
            ],
            name="fk_mfa_recovery_codes__factor",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("code_hash", name="uq_mfa_recovery_codes__code_hash"),
        sa.CheckConstraint("code_hash ~ '^[a-f0-9]{64}$'", name="code_hash"),
        sa.CheckConstraint("factor_type = 'RECOVERY_CODES'", name="factor_type"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    identity_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    factor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    factor_type: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    code_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


class EnterpriseCompanyRecord(TenantScopedRecord, Base):
    """One patron-owned legal company profile per tenant."""

    __tablename__ = "enterprise_companies"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_enterprise_company__tenant", ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_enterprise_company__tenant_id"),
        sa.UniqueConstraint("tenant_id", name="uq_enterprise_company__tenant"),
        sa.UniqueConstraint("tenant_id", "siren", name="uq_enterprise_company__tenant_siren"),
        sa.UniqueConstraint("tenant_id", "siret", name="uq_enterprise_company__tenant_siret"),
        sa.CheckConstraint("siren ~ '^[0-9]{9}$'", name="siren"),
        sa.CheckConstraint("siret ~ '^[0-9]{14}$'", name="siret"),
        sa.CheckConstraint("vat_number ~ '^[A-Z]{2}[A-Z0-9]{2,30}$'", name="vat_number"),
        sa.CheckConstraint("country_code ~ '^[A-Z]{2}$'", name="country_code"),
        sa.CheckConstraint("aggregate_revision >= 0", name="aggregate_revision"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    aggregate_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    legal_name: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(sa.String(240))
    siren: Mapped[str] = mapped_column(sa.CHAR(9), nullable=False)
    siret: Mapped[str] = mapped_column(sa.CHAR(14), nullable=False)
    vat_number: Mapped[str] = mapped_column(sa.String(34), nullable=False)
    address_line1: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    postal_code: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    city: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    country_code: Mapped[str] = mapped_column(sa.CHAR(2), nullable=False)


class EnterpriseDocumentRecord(TenantScopedRecord, Base):
    """Immutable enterprise proof, insurance certificate or bank document."""

    __tablename__ = "enterprise_documents"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_enterprise_document__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "company_id"],
            ["enterprise_companies.tenant_id", "enterprise_companies.id"],
            name="fk_enterprise_document__company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "registered_by_membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_enterprise_document__membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_enterprise_document__tenant_id"),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_enterprise_document__command"),
        sa.CheckConstraint("document_kind IN ('INSURANCE', 'KBIS', 'RIB')", name="document_kind"),
        sa.CheckConstraint(
            "verification_status IN ('PENDING', 'VALIDATED', 'EXPIRED', 'REJECTED')",
            name="verification_status",
        ),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256"),
        sa.CheckConstraint("expires_at IS NULL OR expires_at > issued_at", name="expiry"),
        sa.CheckConstraint(
            "(document_kind = 'RIB' AND expires_at IS NULL) OR document_kind <> 'RIB'",
            name="rib_expiry",
        ),
        sa.Index(
            "ix_enterprise_document__tenant_company_kind_expiry",
            "tenant_id",
            "company_id",
            "document_kind",
            "expires_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    document_kind: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    document_label: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    storage_object_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    original_filename: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    verification_status: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    registered_by_membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class EnterpriseDocumentUploadRecord(TenantScopedRecord, Base):
    """Private upload ledger; storage_key and scan metadata never form a public projection."""

    __tablename__ = "enterprise_document_uploads"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_enterprise_upload__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "company_id"],
            ["enterprise_companies.tenant_id", "enterprise_companies.id"],
            name="fk_enterprise_upload__company",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_enterprise_upload__tenant_id"),
        sa.UniqueConstraint("storage_key", name="uq_enterprise_upload__storage_key"),
        sa.UniqueConstraint("tenant_id", "document_id", name="uq_enterprise_upload__document"),
        sa.CheckConstraint("document_kind IN ('INSURANCE', 'KBIS', 'RIB')", name="document_kind"),
        sa.CheckConstraint(
            "state IN ('AWAITING_UPLOAD', 'UPLOADING', 'QUARANTINED', 'CLEAN', 'REJECTED', 'EXPIRED')",
            name="state",
        ),
        sa.CheckConstraint("expected_byte_size > 0", name="expected_byte_size_positive"),
        sa.CheckConstraint(
            "actual_byte_size IS NULL OR actual_byte_size > 0", name="actual_byte_size_positive"
        ),
        sa.CheckConstraint("sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$'", name="sha256_lowercase"),
        sa.CheckConstraint(
            "scan_verdict IS NULL OR scan_verdict IN ('CLEAN', 'INFECTED', 'ERROR')",
            name="scan_verdict",
        ),
        sa.CheckConstraint(
            "state <> 'CLEAN' OR (actual_byte_size IS NOT NULL AND sha256 IS NOT NULL "
            "AND media_type IS NOT NULL AND scan_verdict = 'CLEAN' AND scanned_at IS NOT NULL)",
            name="clean_metadata_required",
        ),
        sa.Index("ix_enterprise_upload__tenant_company_state", "tenant_id", "company_id", "state"),
        sa.Index("ix_enterprise_upload__tenant_expiry", "tenant_id", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    document_kind: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    document_label: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    original_filename: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    storage_key: Mapped[str] = mapped_column(sa.String(1000), nullable=False)
    expected_byte_size: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    actual_byte_size: Mapped[int | None] = mapped_column(sa.BigInteger)
    sha256: Mapped[str | None] = mapped_column(sa.CHAR(64))
    media_type: Mapped[str | None] = mapped_column(sa.String(180))
    state: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    scan_verdict: Mapped[str | None] = mapped_column(sa.String(32))
    scanner_name: Mapped[str | None] = mapped_column(sa.String(120))
    scanner_signature_version: Mapped[str | None] = mapped_column(sa.String(240))
    scanned_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    rejection_code: Mapped[str | None] = mapped_column(sa.String(120))
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    created_by_membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


class EnterpriseDocumentVerificationRecord(TenantScopedRecord, Base):
    """Append-only human decision history for one enterprise document."""

    __tablename__ = "enterprise_document_verifications"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_enterprise_verification__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["enterprise_documents.tenant_id", "enterprise_documents.id"],
            name="fk_enterprise_verification__document",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_enterprise_verification__membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_enterprise_verification__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "document_id", "revision", name="uq_enterprise_verification__revision"
        ),
        sa.CheckConstraint("revision >= 0", name="revision_nonnegative"),
        sa.CheckConstraint("outcome IN ('VALIDATED', 'REJECTED')", name="outcome"),
        sa.CheckConstraint(
            "reason_code IN ('DOCUMENT_ACCEPTED', 'DOCUMENT_ILLEGIBLE', 'DOCUMENT_EXPIRED', 'DOCUMENT_MISMATCH', 'DOCUMENT_DUPLICATE')",
            name="reason_code",
        ),
        sa.Index(
            "ix_enterprise_verification__tenant_document",
            "tenant_id",
            "document_id",
            "revision",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    outcome: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    reason_code: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class CollaboratorTaskRecord(TenantScopedRecord, Base):
    """Mutable operational task bounded by one active collaborator assignment."""

    __tablename__ = "collaborator_tasks"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_collab_tasks__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_collab_tasks__case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assignment_id"],
            ["case_assignments.tenant_id", "case_assignments.id"],
            name="fk_collab_tasks__assignment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "requirement_id"],
            ["dce_requirements.tenant_id", "dce_requirements.id"],
            name="fk_collab_tasks__requirement",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_collab_tasks__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "assignment_id", "functional_key", name="uq_collab_task__functional"
        ),
        sa.CheckConstraint(
            "state IN ('READY', 'IN_PROGRESS', 'BLOCKED', 'COMPLETED', 'ABANDONED')", name="state"
        ),
        sa.CheckConstraint("aggregate_revision >= 0", name="aggregate_revision"),
        sa.CheckConstraint("priority IN ('LOW', 'NORMAL', 'HIGH', 'CRITICAL')", name="priority"),
        sa.Index(
            "ix_collab_tasks__tenant_assignment_state",
            "tenant_id",
            "assignment_id",
            "state",
            "created_at",
        ),
        sa.Index(
            "ix_collab_tasks__tenant_case_state",
            "tenant_id",
            "case_id",
            "state",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    assignment_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    requirement_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    task_kind: Mapped[str] = mapped_column(sa.String(48), nullable=False)
    title: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    objective: Mapped[str] = mapped_column(sa.String(2_000), nullable=False)
    priority: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default="NORMAL")
    state: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default="READY")
    functional_key: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    aggregate_revision: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0, server_default="0"
    )
    claimed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class CollaboratorTaskResultRecord(TenantScopedRecord, Base):
    """Append-only operational result history for one collaborator task."""

    __tablename__ = "collaborator_task_results"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_collab_task_results__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["collaborator_tasks.tenant_id", "collaborator_tasks.id"],
            name="fk_collab_task_results__task",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_collab_task_results__membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_collab_task_results__tenant_id"),
        sa.CheckConstraint(
            "outcome IN ('RECORDED', 'NOT_APPLICABLE', 'UNABLE_TO_COMPLETE')", name="outcome"
        ),
        sa.CheckConstraint("task_revision >= 0", name="task_revision"),
        sa.CheckConstraint("length(trim(result_text)) > 0", name="result_text_nonempty"),
        sa.Index(
            "ix_collab_task_results__tenant_task_revision", "tenant_id", "task_id", "task_revision"
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    task_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    task_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    outcome: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    result_text: Mapped[str] = mapped_column(sa.String(8_000), nullable=False)
    source_locator: Mapped[str | None] = mapped_column(sa.String(500))
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class CollaboratorInformationRequestRecord(TenantScopedRecord, Base):
    """Operational information request bounded by one collaborator task."""

    __tablename__ = "collaborator_information_requests"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_collab_info_requests__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["collaborator_tasks.tenant_id", "collaborator_tasks.id"],
            name="fk_collab_info_requests__task",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_collab_info_requests__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "task_id", "functional_key", name="uq_collab_info_request__functional"
        ),
        sa.CheckConstraint(
            "request_kind IN ('MISSING_SOURCE', 'CLARIFICATION', 'OWNER_CONFIRMATION', 'DEADLINE_CONFIRMATION')",
            name="request_kind",
        ),
        sa.CheckConstraint("priority IN ('LOW', 'NORMAL', 'HIGH', 'CRITICAL')", name="priority"),
        sa.CheckConstraint("state IN ('OPEN', 'ANSWERED', 'CLOSED', 'CANCELLED')", name="state"),
        sa.CheckConstraint("aggregate_revision >= 0", name="aggregate_revision"),
        sa.Index(
            "ix_collab_info_requests__tenant_task_state",
            "tenant_id",
            "task_id",
            "state",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    task_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    request_kind: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    subject: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    question: Mapped[str] = mapped_column(sa.String(4_000), nullable=False)
    requested_object: Mapped[str] = mapped_column(sa.String(1_000), nullable=False)
    reason: Mapped[str] = mapped_column(sa.String(2_000), nullable=False)
    priority: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default="NORMAL")
    state: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default="OPEN")
    functional_key: Mapped[str] = mapped_column(sa.String(700), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    aggregate_revision: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0, server_default="0"
    )
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class CollaboratorInformationResponseRecord(TenantScopedRecord, Base):
    """Append-only versioned response for one information request."""

    __tablename__ = "collaborator_information_responses"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_collab_info_responses__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "request_id"],
            ["collaborator_information_requests.tenant_id", "collaborator_information_requests.id"],
            name="fk_collab_info_responses__request",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_collab_info_responses__tenant_id"),
        sa.CheckConstraint(
            "outcome IN ('ANSWERED', 'NOT_AVAILABLE', 'NEEDS_CLARIFICATION')", name="outcome"
        ),
        sa.CheckConstraint("request_revision >= 0", name="request_revision"),
        sa.CheckConstraint("length(trim(response_text)) > 0", name="response_text_nonempty"),
        sa.Index(
            "ix_collab_info_responses__tenant_request_revision",
            "tenant_id",
            "request_id",
            "request_revision",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    request_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    request_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    outcome: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    response_text: Mapped[str] = mapped_column(sa.String(8_000), nullable=False)
    source_locator: Mapped[str | None] = mapped_column(sa.String(500))
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class CollaboratorTaskBlockerRecord(TenantScopedRecord, Base):
    """Mutable blocker state owned by a collaborator task."""

    __tablename__ = "collaborator_task_blockers"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_collab_task_blockers__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["collaborator_tasks.tenant_id", "collaborator_tasks.id"],
            name="fk_collab_task_blockers__task",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_collab_task_blockers__tenant_id"),
        sa.CheckConstraint(
            "blocker_kind IN ('MISSING_INFORMATION', 'EXTERNAL_DEPENDENCY', 'SOURCE_CONFLICT', 'REVIEW_REQUIRED')",
            name="blocker_kind",
        ),
        sa.CheckConstraint(
            "resolution_owner IN ('COLLABORATEUR', 'PATRON_ADMIN', 'EXTERNAL_PARTY')",
            name="resolution_owner",
        ),
        sa.CheckConstraint("state IN ('OPEN', 'RESOLVED')", name="state"),
        sa.CheckConstraint(
            "state <> 'RESOLVED' OR (resolution_note IS NOT NULL AND resolved_at IS NOT NULL)",
            name="resolution_fields",
        ),
        sa.Index(
            "ix_collab_task_blockers__tenant_task_state",
            "tenant_id",
            "task_id",
            "state",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    task_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    task_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    blocker_kind: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    description: Mapped[str] = mapped_column(sa.String(4_000), nullable=False)
    source_locator: Mapped[str | None] = mapped_column(sa.String(500))
    resolution_owner: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default="OPEN")
    resolution_note: Mapped[str | None] = mapped_column(sa.String(4_000))
    resolved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class PreparationPackageRecord(TenantScopedRecord, Base):
    """Mutable preparation package owned by one case assignment and DCE version."""

    __tablename__ = "preparation_packages"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_prep_packages__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assignment_id"],
            ["case_assignments.tenant_id", "case_assignments.id"],
            name="fk_prep_packages__assignment",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_prep_packages__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "case_id",
            "assignment_id",
            "dce_version_id",
            name="uq_prep_package_identity",
        ),
        sa.CheckConstraint(
            "state IN ('IN_PREPARATION', 'A_REVIEW', 'READY', 'BLOCKED', 'GENERATED')", name="state"
        ),
        sa.CheckConstraint("aggregate_revision >= 0", name="aggregate_revision"),
        sa.Index("ix_prep_packages__tenant_case_state", "tenant_id", "case_id", "state"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    assignment_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    dce_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    state: Mapped[str] = mapped_column(
        sa.String(24), nullable=False, server_default="IN_PREPARATION"
    )
    aggregate_revision: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0, server_default="0"
    )
    created_by_actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)


class PreparationReadinessRecord(TenantScopedRecord, Base):
    """Append-only deterministic completeness evaluation."""

    __tablename__ = "preparation_readiness"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_prep_readiness__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "package_id"],
            ["preparation_packages.tenant_id", "preparation_packages.id"],
            name="fk_prep_readiness__package",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_prep_readiness__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "package_id", "revision", name="uq_prep_readiness_revision"
        ),
        sa.CheckConstraint("revision > 0", name="revision_positive"),
        sa.CheckConstraint("state IN ('READY', 'READY_WITH_WARNINGS', 'BLOCKED')", name="state"),
        sa.CheckConstraint("checked_requirement_count >= 0", name="requirements_nonnegative"),
        sa.CheckConstraint("checked_task_count >= 0", name="tasks_nonnegative"),
        sa.Index(
            "ix_prep_readiness__tenant_package_revision", "tenant_id", "package_id", "revision"
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    package_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    state: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    blocker_codes_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    warning_codes_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    checked_requirement_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    checked_task_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    input_manifest_sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    evaluator_id: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    evaluator_version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class GeneratedTechnicalDocumentRecord(TenantScopedRecord, Base):
    """Immutable generated technical document metadata; content stays private."""

    __tablename__ = "generated_technical_documents"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_generated_docs__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "package_id"],
            ["preparation_packages.tenant_id", "preparation_packages.id"],
            name="fk_generated_docs__package",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "readiness_id"],
            ["preparation_readiness.tenant_id", "preparation_readiness.id"],
            name="fk_generated_docs__readiness",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_generated_docs__tenant_id"),
        sa.UniqueConstraint("tenant_id", "package_id", "version", name="uq_generated_doc_version"),
        sa.CheckConstraint("version > 0", name="version_positive"),
        sa.CheckConstraint("document_kind IN ('TECHNICAL_RESPONSE')", name="document_kind"),
        sa.CheckConstraint("state IN ('GENERATED', 'FAILED_SAFE')", name="state"),
        sa.Index("ix_generated_docs__tenant_package_version", "tenant_id", "package_id", "version"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    package_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    readiness_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    document_kind: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    content_sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(sa.String(700), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


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
            "action_type IN ('REVIEW_PREPARATION', 'CONTROL_SUBMISSION', 'VALIDATE_PRICE', 'DECIDE_GO_NO_GO')",
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


class PreparationSnapshotRecord(TenantScopedRecord, Base):
    """Immutable non-financial preparation facts frozen for patron review."""

    __tablename__ = "preparation_snapshots"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_prep_snapshots__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "package_id"],
            ["preparation_packages.tenant_id", "preparation_packages.id"],
            name="fk_prep_snapshots__package",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "readiness_id"],
            ["preparation_readiness.tenant_id", "preparation_readiness.id"],
            name="fk_prep_snapshots__readiness",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "technical_document_id"],
            ["generated_technical_documents.tenant_id", "generated_technical_documents.id"],
            name="fk_prep_snapshots__document",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_prep_snapshots__tenant_id"),
        sa.UniqueConstraint("tenant_id", "package_id", "version", name="uq_prep_snapshot__version"),
        sa.CheckConstraint("version > 0", name="version_positive"),
        sa.CheckConstraint("state IN ('READY_FOR_PATRON_REVIEW')", name="state"),
        sa.Index("ix_prep_snapshots__tenant_package_version", "tenant_id", "package_id", "version"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    package_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    dce_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    readiness_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    technical_document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    technical_document_version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    state: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    manifest_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class PreparationTransmissionRecord(TenantScopedRecord, Base):
    """Append-only handoff of one immutable preparation snapshot to the patron."""

    __tablename__ = "preparation_transmissions"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_prep_transmissions__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "package_id"],
            ["preparation_packages.tenant_id", "preparation_packages.id"],
            name="fk_prep_transmissions__package",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "snapshot_id"],
            ["preparation_snapshots.tenant_id", "preparation_snapshots.id"],
            name="fk_prep_transmissions__snapshot",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_prep_transmissions__tenant_id"),
        sa.UniqueConstraint("tenant_id", "snapshot_id", name="uq_prep_transmission__snapshot"),
        sa.CheckConstraint("state IN ('TRANSMITTED_TO_PATRON')", name="state"),
        sa.Index("ix_prep_transmissions__tenant_package", "tenant_id", "package_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    package_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    snapshot_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class SubmissionPackageRecord(TenantScopedRecord, Base):
    """Immutable patron-controlled package prepared for human submission."""

    __tablename__ = "submission_packages"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_submission_package__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "preparation_package_id"],
            ["preparation_packages.tenant_id", "preparation_packages.id"],
            name="fk_submission_package__preparation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "technical_document_id"],
            ["generated_technical_documents.tenant_id", "generated_technical_documents.id"],
            name="fk_submission_package__document",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "financial_snapshot_id"],
            ["financial_report_snapshots.tenant_id", "financial_report_snapshots.id"],
            name="fk_submission_package__financial_snapshot",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_submission_package__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "preparation_package_id",
            "version",
            name="uq_submission_package__preparation_version",
        ),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_submission_package__command"),
        sa.CheckConstraint("version > 0", name="version_positive"),
        sa.CheckConstraint(
            "state IN ('PRET_CONTROLE', 'AUTORISE_DEPOT')",
            name="state",
        ),
        sa.CheckConstraint("technical_document_version > 0", name="technical_document_version"),
        sa.CheckConstraint("financial_snapshot_revision >= 0", name="financial_snapshot_revision"),
        sa.Index(
            "ix_submission_packages__tenant_preparation_version",
            "tenant_id",
            "preparation_package_id",
            "version",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    preparation_package_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    dce_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    technical_document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    technical_document_version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    financial_snapshot_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    financial_snapshot_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    state: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    manifest_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class SubmissionEvidenceRecord(TenantScopedRecord, Base):
    """Human-provided evidence; it never asserts automated external submission success."""

    __tablename__ = "submission_evidence"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id", "submission_package_id"],
            ["submission_packages.tenant_id", "submission_packages.id"],
            name="fk_submission_evidence__package",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_submission_evidence__tenant_id"),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_submission_evidence__command"),
        sa.CheckConstraint(
            "evidence_type IN ('MANUAL_RECEIPT', 'MANUAL_PORTAL_REFERENCE')", name="evidence_type"
        ),
        sa.CheckConstraint("status IN ('RECEIVED', 'REJECTED')", name="status"),
        sa.Index("ix_submission_evidence__tenant_package", "tenant_id", "submission_package_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    submission_package_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    evidence_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    external_reference_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    notes_redacted: Mapped[str | None] = mapped_column(sa.String(1000))
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class EnterpriseCapabilityRecord(TenantScopedRecord, Base):
    """Patron-owned reusable capability root, separate from any Case assessment."""

    __tablename__ = "enterprise_capabilities"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_enterprise_capability__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "company_id"],
            ["enterprise_companies.tenant_id", "enterprise_companies.id"],
            name="fk_enterprise_capability__company",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_enterprise_capability__tenant_id"),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_enterprise_capability__command"),
        sa.UniqueConstraint(
            "tenant_id",
            "company_id",
            "capability_kind",
            "name",
            name="uq_enterprise_capability__identity",
        ),
        sa.Index(
            "ix_enterprise_capabilities__tenant_company_kind_state",
            "tenant_id",
            "company_id",
            "capability_kind",
            "state",
        ),
        sa.CheckConstraint(
            "capability_kind IN ('QUALIFICATION', 'REFERENCE', 'EQUIPMENT', 'TEAM', 'METHOD')",
            name="capability_kind",
        ),
        sa.CheckConstraint("state IN ('ACTIVE', 'SUSPENDED', 'RETIRED')", name="state"),
        sa.CheckConstraint("aggregate_revision >= 0", name="aggregate_revision"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    aggregate_revision: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0, server_default="0"
    )
    capability_kind: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    summary: Mapped[str] = mapped_column(sa.String(1000), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class EnterpriseCapabilityVersionRecord(TenantScopedRecord, Base):
    """Immutable dated version of one enterprise capability."""

    __tablename__ = "enterprise_capability_versions"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id", "capability_id"],
            ["enterprise_capabilities.tenant_id", "enterprise_capabilities.id"],
            name="fk_enterprise_capability_version__capability",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by_membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_enterprise_capability_version__membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_enterprise_capability_version__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "command_id", name="uq_enterprise_capability_version__command"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "capability_id",
            "version_number",
            name="uq_enterprise_capability_version__number",
        ),
        sa.Index(
            "ix_enterprise_capability_versions__tenant_capability_validity",
            "tenant_id",
            "capability_id",
            "valid_until",
        ),
        sa.CheckConstraint("version_number > 0", name="version_number"),
        sa.CheckConstraint("valid_until IS NULL OR valid_until > valid_from", name="validity"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    capability_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    version_number: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    title: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    usage_scope: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    created_by_membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class EnterpriseCapabilityProofLinkRecord(TenantScopedRecord, Base):
    """Immutable link from a capability version to an enterprise document proof."""

    __tablename__ = "enterprise_capability_proof_links"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id", "capability_version_id"],
            ["enterprise_capability_versions.tenant_id", "enterprise_capability_versions.id"],
            name="fk_enterprise_capability_proof_link__version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["enterprise_documents.tenant_id", "enterprise_documents.id"],
            name="fk_enterprise_capability_proof_link__document",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "tenant_id", "id", name="uq_enterprise_capability_proof_link__tenant_id"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "capability_version_id",
            "document_id",
            name="uq_enterprise_capability_proof_link__identity",
        ),
        sa.CheckConstraint("length(trim(relation_label)) > 0", name="relation_label"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    capability_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    relation_label: Mapped[str] = mapped_column(sa.String(240), nullable=False)


class CaseCapabilityProposalRecord(TenantScopedRecord, Base):
    """Collaborator candidate use of an enterprise capability for one Case."""

    __tablename__ = "case_capability_proposals"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_case_capability_proposal__case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assignment_id"],
            ["case_assignments.tenant_id", "case_assignments.id"],
            name="fk_case_capability_proposal__assignment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "capability_id"],
            ["enterprise_capabilities.tenant_id", "enterprise_capabilities.id"],
            name="fk_case_capability_proposal__capability",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "capability_version_id"],
            ["enterprise_capability_versions.tenant_id", "enterprise_capability_versions.id"],
            name="fk_case_capability_proposal__version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "requirement_id"],
            ["dce_requirements.tenant_id", "dce_requirements.id"],
            name="fk_case_capability_proposal__requirement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["collaborator_tasks.tenant_id", "collaborator_tasks.id"],
            name="fk_case_capability_proposal__task",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "proposed_by_membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_case_capability_proposal__membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_case_capability_proposal__tenant_id"),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_case_capability_proposal__command"),
        sa.UniqueConstraint(
            "tenant_id", "functional_key", name="uq_case_capability_proposal__functional"
        ),
        sa.CheckConstraint("state IN ('PROPOSED', 'TO_REVIEW')", name="state"),
        sa.CheckConstraint(
            "validity_state IN ('CURRENT', 'EXPIRED', 'UNKNOWN')", name="validity_state"
        ),
        sa.CheckConstraint(
            "requirement_id IS NOT NULL OR task_id IS NOT NULL", name="source_required"
        ),
        sa.Index(
            "ix_case_capability_proposals__tenant_case_state",
            "tenant_id",
            "case_id",
            "state",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    assignment_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    capability_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    capability_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    requirement_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    task_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    state: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default="PROPOSED")
    validity_state: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    justification: Mapped[str] = mapped_column(sa.String(2000), nullable=False)
    source_locator: Mapped[str | None] = mapped_column(sa.String(500))
    functional_key: Mapped[str] = mapped_column(sa.String(700), nullable=False)
    proposed_by_membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class CaseCapabilityGapRecord(TenantScopedRecord, Base):
    """Collaborator finding that a Case capability/proof is missing or unusable."""

    __tablename__ = "case_capability_gaps"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_case_capability_gap__case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assignment_id"],
            ["case_assignments.tenant_id", "case_assignments.id"],
            name="fk_case_capability_gap__assignment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "capability_id"],
            ["enterprise_capabilities.tenant_id", "enterprise_capabilities.id"],
            name="fk_case_capability_gap__capability",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "requirement_id"],
            ["dce_requirements.tenant_id", "dce_requirements.id"],
            name="fk_case_capability_gap__requirement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["collaborator_tasks.tenant_id", "collaborator_tasks.id"],
            name="fk_case_capability_gap__task",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "reported_by_membership_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.id"],
            name="fk_case_capability_gap__membership",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_case_capability_gap__tenant_id"),
        sa.UniqueConstraint("tenant_id", "command_id", name="uq_case_capability_gap__command"),
        sa.UniqueConstraint(
            "tenant_id", "functional_key", name="uq_case_capability_gap__functional"
        ),
        sa.CheckConstraint(
            "gap_kind IN ('MISSING', 'EXPIRED', 'UNAUTHORIZED', 'INSUFFICIENT')", name="gap_kind"
        ),
        sa.CheckConstraint(
            "severity IN ('INFORMATIONAL', 'IMPORTANT', 'BLOCKING')", name="severity"
        ),
        sa.CheckConstraint(
            "requirement_id IS NOT NULL OR task_id IS NOT NULL", name="source_required"
        ),
        sa.Index(
            "ix_case_capability_gaps__tenant_case_severity",
            "tenant_id",
            "case_id",
            "severity",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    assignment_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    capability_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    requirement_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    task_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    gap_kind: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    severity: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    reason: Mapped[str] = mapped_column(sa.String(2000), nullable=False)
    source_locator: Mapped[str | None] = mapped_column(sa.String(500))
    recommended_action: Mapped[str] = mapped_column(sa.String(1000), nullable=False)
    functional_key: Mapped[str] = mapped_column(sa.String(700), nullable=False)
    reported_by_membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class PreparationReviewRecord(TenantScopedRecord, Base):
    """Immutable state transition for a versioned preparation target review."""

    __tablename__ = "preparation_reviews"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_preparation_review__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "package_id"],
            ["preparation_packages.tenant_id", "preparation_packages.id"],
            name="fk_preparation_review__package",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "target_document_id"],
            ["generated_technical_documents.tenant_id", "generated_technical_documents.id"],
            name="fk_preparation_review__document",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_preparation_review__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "review_id", "revision", name="uq_preparation_review__revision"
        ),
        sa.CheckConstraint(
            "state IN ('REQUESTED', 'ACCEPTED', 'RETURNED_WITH_CORRECTIONS', 'REJECTED')",
            name="state",
        ),
        sa.CheckConstraint("revision > 0", name="revision_positive"),
        sa.CheckConstraint("target_version > 0", name="target_version_positive"),
        sa.CheckConstraint(
            "decision_code IS NULL OR decision_code IN ('ACCEPTED', 'CORRECTIONS_REQUIRED', 'REJECTED')",
            name="decision_code",
        ),
        sa.Index(
            "ix_preparation_reviews__tenant_target", "tenant_id", "target_document_id", "revision"
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    review_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    package_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    target_document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    target_version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    state: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    decision_code: Mapped[str | None] = mapped_column(sa.String(32))
    decision_note: Mapped[str | None] = mapped_column(sa.String(2000))
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class PreparationReviewCorrectionRecord(TenantScopedRecord, Base):
    """Immutable targeted correction attached to a review transition."""

    __tablename__ = "preparation_review_corrections"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_preparation_correction__tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "review_id", "review_revision"],
            [
                "preparation_reviews.tenant_id",
                "preparation_reviews.review_id",
                "preparation_reviews.revision",
            ],
            name="fk_preparation_correction__review",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "target_document_id"],
            ["generated_technical_documents.tenant_id", "generated_technical_documents.id"],
            name="fk_preparation_correction__document",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_preparation_correction__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "review_id", "revision", name="uq_preparation_correction__revision"
        ),
        sa.CheckConstraint("revision > 0", name="revision_positive"),
        sa.CheckConstraint("review_revision > 0", name="review_revision_positive"),
        sa.CheckConstraint(
            "correction_code IN ('SOURCE_MISSING', 'SOURCE_WRONG', 'SECTION_INCOMPLETE', 'WORDING_UNCLEAR')",
            name="correction_code",
        ),
        sa.Index("ix_preparation_corrections__tenant_review", "tenant_id", "review_id", "revision"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    review_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    review_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    target_document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    revision: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    correction_code: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    instruction: Mapped[str] = mapped_column(sa.String(2000), nullable=False)
    source_locator: Mapped[str | None] = mapped_column(sa.String(500))
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class TechnicalResponseDraftRecord(TenantScopedRecord, Base):
    """Immutable, non-financial, versioned response draft metadata."""

    __tablename__ = "technical_response_drafts"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_technical_draft__tenant", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "package_id"],
            ["preparation_packages.tenant_id", "preparation_packages.id"],
            name="fk_technical_draft__package",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "source_document_id"],
            ["generated_technical_documents.tenant_id", "generated_technical_documents.id"],
            name="fk_technical_draft__document",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_technical_draft__tenant_id"),
        sa.UniqueConstraint("tenant_id", "draft_id", "version", name="uq_technical_draft__version"),
        sa.CheckConstraint("version > 0", name="version_positive"),
        sa.CheckConstraint(
            "state IN ('DRAFT', 'SUBMITTED_FOR_REVIEW', 'RETURNED_WITH_CORRECTIONS', 'ACCEPTED_CANDIDATE')",
            name="state",
        ),
        sa.CheckConstraint(
            "responsible_role IN ('COLLABORATEUR', 'PATRON_REVIEWER')",
            name="responsible_role",
        ),
        sa.Index("ix_technical_drafts__tenant_package", "tenant_id", "package_id", "version"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    draft_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    package_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    source_document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    state: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    section_codes_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    source_refs_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    responsible_role: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    content_sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(sa.String(700), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
