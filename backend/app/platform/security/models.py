"""SQLAlchemy records for SEC-01 identity and tenant membership persistence."""

from __future__ import annotations

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
        sa.CheckConstraint(
            "state IN ('ACTIVE', 'SUSPENDED', 'ENDED', 'EXPIRED')", name="state"
        ),
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
        sa.CheckConstraint("granted_at >= starts_at", name="granted_after_start"),
        sa.CheckConstraint("ends_at IS NULL OR ends_at > starts_at", name="end_after_start"),
        sa.CheckConstraint(
            "(state IN ('ACTIVE', 'SUSPENDED') AND ended_at IS NULL) OR "
            "(state IN ('ENDED', 'EXPIRED') AND ended_at IS NOT NULL)",
            name="state_timestamps",
        ),
        sa.Index(
            "ux_assignments__active_member_case",
            "tenant_id",
            "membership_id",
            "case_id",
            unique=True,
            postgresql_where=sa.text("state = 'ACTIVE'"),
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
    scope_actions_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    scope_classifications_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    granted_by_membership_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


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
