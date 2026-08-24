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
            "'AUTHZ_SUCCEEDED', 'AUTHZ_DENIED', 'AUTHZ_STEP_UP_REQUIRED', "
            "'SUBMISSION_PACKAGE_EXPORTED'"
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


# Compatibility exports remain available while callers migrate to module-owned models.
from app.modules.enterprise.infrastructure.models.enterprise import (  # noqa: E402, F401
    EnterpriseCompanyRecord,
    EnterpriseDocumentRecord,
    EnterpriseDocumentUploadRecord,
    EnterpriseDocumentVerificationRecord,
)
from app.modules.patron_action.infrastructure.models.patron_action import (  # noqa: E402, F401
    PatronActionRecord,
)
from app.modules.preparation.infrastructure.models.preparation import (  # noqa: E402, F401
    PreparationPackageRecord,
    PreparationReviewRecord,
)
from app.modules.pricing.infrastructure.models.financial import (  # noqa: E402, F401
    FinancialReportLineRecord,
    FinancialReportSnapshotRecord,
    PricingScenarioRecord,
)
from app.modules.submission.infrastructure.models.submission import (  # noqa: E402, F401
    SubmissionEvidenceRecord,
    SubmissionPackageRecord,
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

# Compatibility exports for the remaining module-owned business records.
from app.modules.enterprise.infrastructure.models.enterprise import (  # noqa: E402, F401
    CaseCapabilityGapRecord,
    CaseCapabilityProposalRecord,
    EnterpriseCapabilityProofLinkRecord,
    EnterpriseCapabilityRecord,
    EnterpriseCapabilityVersionRecord,
)
from app.modules.patron_action.infrastructure.models.patron_action import (  # noqa: E402, F401
    PatronActionTransitionRecord,
)
from app.modules.preparation.infrastructure.models.preparation import (  # noqa: E402, F401
    GeneratedTechnicalDocumentRecord,
    PreparationReadinessRecord,
    PreparationReviewCorrectionRecord,
    PreparationSnapshotRecord,
    PreparationTransmissionRecord,
    TechnicalResponseDraftRecord,
)
from app.modules.pricing.infrastructure.models.financial import (  # noqa: E402, F401
    FinancialReportPublicationRecord,
    PricingImportBatchRecord,
    PricingImportRowRecord,
    PricingImportTransitionRecord,
    PricingScenarioTransitionRecord,
)
from app.modules.submission.infrastructure.models.submission import (  # noqa: E402, F401
    SubmissionSignatureRecord,
)
