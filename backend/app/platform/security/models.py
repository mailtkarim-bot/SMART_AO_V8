"""SQLAlchemy records for SEC-01 identity and tenant membership persistence."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
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
