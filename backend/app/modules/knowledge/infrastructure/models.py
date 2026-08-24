"""Persistence records for local retrieval embeddings."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.persistence.base import Base, TenantScopedRecord


class DceFragmentEmbeddingRecord(TenantScopedRecord, Base):
    """One immutable embedding for one extracted DCE fragment and model version."""

    __tablename__ = "dce_fragment_embeddings"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_dce_fragment_embeddings__tenants__tenant_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dce_version_id"],
            ["dce_versions.tenant_id", "dce_versions.id"],
            name="fk_dce_fragment_embeddings__dce_versions__tenant_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["cases.tenant_id", "cases.id"],
            name="fk_dce_fragment_embeddings__cases__tenant_case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "fragment_id"],
            [
                "dce_document_extraction_fragments.tenant_id",
                "dce_document_extraction_fragments.id",
            ],
            name="fk_dce_fragment_embeddings__fragments__tenant_fragment",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_dce_fragment_embeddings__tenant_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "fragment_id",
            "model_id",
            name="uq_dce_fragment_embeddings__fragment_model",
        ),
        sa.CheckConstraint("ordinal > 0", name="ordinal_positive"),
        sa.CheckConstraint("char_length(text) > 0", name="text_nonempty"),
        sa.CheckConstraint(
            "classification IN ('PUBLIC', 'INTERNAL_OPERATIONAL')",
            name="classification_allowed",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(embedding) = 'array'",
            name="embedding_is_array",
        ),
        sa.CheckConstraint("embedding_dimension > 0", name="embedding_dimension_positive"),
        sa.CheckConstraint(
            "jsonb_array_length(embedding) = embedding_dimension",
            name="embedding_length",
        ),
        sa.Index("ix_dce_fragment_embeddings_tenant_id", "tenant_id"),
        sa.Index(
            "ix_dce_fragment_embeddings__tenant_version_model",
            "tenant_id",
            "case_id",
            "dce_version_id",
            "model_id",
        ),
        sa.Index(
            "ix_dce_fragment_embeddings__tenant_fragment_model",
            "tenant_id",
            "fragment_id",
            "model_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    dce_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    fragment_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    model_id: Mapped[str] = mapped_column(sa.String(180), nullable=False)
    ordinal: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    text: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    locator_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    classification: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    text_sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(JSONB, nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
