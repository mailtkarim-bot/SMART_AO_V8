"""SQLAlchemy foundation shared by persistence adapters only.

Business aggregates remain framework-free under each module's ``domain`` package.
This module defines physical persistence conventions declared in DATA-01.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s__%(column_0_name)s",
    "ck": "ck_%(table_name)s__%(constraint_name)s",
    "fk": "fk_%(table_name)s__%(referred_table_name)s__%(column_0_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative metadata used by Alembic and infrastructure models."""

    metadata = sa.MetaData(naming_convention=NAMING_CONVENTION)


class TenantScopedRecord:
    """Mixin for durable records that must never exist outside a tenant."""

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


class RevisionedAggregateRecord(TenantScopedRecord):
    """Mixin reserved for aggregate roots persisted with optimistic revision."""

    aggregate_revision: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
