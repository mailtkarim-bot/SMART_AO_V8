"""SQLAlchemy records owned by the Consultation aggregate.

These records are infrastructure adapters. The pure Consultation aggregate remains
under ``dce.domain`` and is never imported here.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.persistence.base import Base, RevisionedAggregateRecord, TenantScopedRecord


class ConsultationRecord(RevisionedAggregateRecord, Base):
    __tablename__ = "consultations"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_consultations__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_consultations__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "functional_identity_hash",
            name="uq_consultations__tenant_functional_identity",
        ),
        sa.CheckConstraint(
            "lifecycle IN ('OPEN', 'CLOSED', 'ARCHIVED')",
            name="lifecycle",
        ),
        sa.CheckConstraint(
            "freshness IN ('UNKNOWN', 'CURRENT', 'REVIEW_REQUIRED')",
            name="freshness",
        ),
        sa.Index(
            "ux_consultations__tenant_buyer_reference",
            "tenant_id",
            "buyer_normalized_id",
            "external_reference",
            unique=True,
            postgresql_where=sa.text(
                "buyer_normalized_id IS NOT NULL AND external_reference IS NOT NULL"
            ),
        ),
        sa.Index(
            "ix_consultations__tenant_lifecycle_updated",
            "tenant_id",
            "lifecycle",
            sa.text("updated_at DESC"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    functional_identity_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    buyer_legal_name: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    buyer_normalized_id: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    external_reference: Mapped[str | None] = mapped_column(sa.String(240), nullable=True)
    object_label: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    location_label: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    source_channel: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    source_received_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
    )
    lifecycle: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    freshness: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    metadata_history_json: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=sa.text("'[]'::jsonb"),
    )
    created_by_actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    updated_by_actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class ConsultationLotRecord(TenantScopedRecord, Base):
    __tablename__ = "consultation_lots"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id", "consultation_id"],
            ["consultations.tenant_id", "consultations.id"],
            name="fk_consultation_lots__consultations__tenant_consultation_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_consultation_lots__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "consultation_id",
            "lot_number",
            name="uq_consultation_lots__tenant_consultation_lot_number",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    consultation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    lot_number: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    label: Mapped[str] = mapped_column(sa.String(240), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)


class ConsultationTrancheRecord(TenantScopedRecord, Base):
    __tablename__ = "consultation_tranches"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id", "consultation_id"],
            ["consultations.tenant_id", "consultations.id"],
            name="fk_consultation_tranches__consultations__tenant_consultation_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_consultation_tranches__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "consultation_id",
            "tranche_reference",
            name="uq_consultation_tranches__tenant_consultation_tranche_reference",
        ),
        sa.CheckConstraint("length(trim(tranche_kind)) > 0", name="tranche_kind"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    consultation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    tranche_reference: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    tranche_kind: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    label: Mapped[str | None] = mapped_column(sa.String(240), nullable=True)
    source_reference: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
