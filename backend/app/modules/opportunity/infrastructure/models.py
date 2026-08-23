"""Persistence records for patron opportunity watch profiles."""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.persistence.base import Base, RevisionedAggregateRecord, TenantScopedRecord


class OpportunityWatchProfileRecord(RevisionedAggregateRecord, Base):
    __tablename__ = "opportunity_watch_profiles"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_opportunity_watch_profiles__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_opportunity_watch_profiles__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "command_id", name="uq_opportunity_watch_profiles__tenant_command"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_opportunity_watch_profiles__tenant_idempotency",
        ),
        sa.CheckConstraint("state IN ('ACTIVE', 'PAUSED')", name="state_allowed"),
        sa.CheckConstraint("current_version >= 1", name="current_version_positive"),
        sa.Index(
            "ix_opportunity_watch_profiles__tenant_state_created",
            "tenant_id",
            "state",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default="ACTIVE")
    current_version: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class OpportunityWatchProfileVersionRecord(TenantScopedRecord, Base):
    __tablename__ = "opportunity_watch_profile_versions"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_opportunity_watch_profile_versions__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "profile_id"],
            ["opportunity_watch_profiles.tenant_id", "opportunity_watch_profiles.id"],
            name="fk_opportunity_watch_profile_versions__profiles__tenant_profile",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "id",
            name="uq_opportunity_watch_profile_versions__tenant_id",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "profile_id",
            "version_number",
            name="uq_opportunity_watch_profile_versions__profile_version",
        ),
        sa.UniqueConstraint(
            "tenant_id", "command_id", name="uq_opportunity_watch_profile_versions__tenant_command"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_opportunity_watch_profile_versions__tenant_idempotency",
        ),
        sa.CheckConstraint("version_number >= 1", name="version_number_positive"),
        sa.CheckConstraint(
            "jsonb_typeof(criteria_json) = 'object'", name="criteria_object"
        ),
        sa.CheckConstraint("criteria_sha256 ~ '^[a-f0-9]{64}$'", name="criteria_sha256_hex"),
        sa.Index(
            "ix_opportunity_watch_profile_versions__tenant_profile_version",
            "tenant_id",
            "profile_id",
            "version_number",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    profile_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    version_number: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    name: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    criteria_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    criteria_sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    command_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
