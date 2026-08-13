"""Technical primitives shared by SQLAlchemy aggregate repositories.

This module deliberately knows neither the BTP domain nor a concrete aggregate.
It centralizes the guarded update convention required by DATA-01: every root
mutation must target one tenant, one aggregate id and one expected revision.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session


class OptimisticRevisionConflictError(RuntimeError):
    """Raised when a root no longer has the caller's expected revision."""


def update_root_with_expected_revision(
    session: Session,
    *,
    table: sa.Table,
    tenant_id: UUID | str,
    aggregate_id: UUID | str,
    expected_revision: int,
    changes: Mapping[str, Any],
    allowed_columns: frozenset[str],
) -> int:
    """Apply a root-only update guarded by tenant and aggregate revision.

    The caller may only alter explicitly whitelisted columns. The root revision
    is incremented atomically in the same SQL statement; a rowcount other than
    one is deliberately indistinguishable between absence and concurrency to
    avoid exposing cross-tenant resource existence.
    """

    if expected_revision < 0:
        raise ValueError("expected_revision must be non-negative")
    if not changes:
        raise ValueError("repository update requires at least one change")

    unexpected_columns = set(changes) - allowed_columns
    if unexpected_columns:
        unexpected = ", ".join(sorted(unexpected_columns))
        raise ValueError(f"repository update contains forbidden columns: {unexpected}")

    statement = (
        sa.update(table)
        .where(
            table.c.tenant_id == tenant_id,
            table.c.id == aggregate_id,
            table.c.aggregate_revision == expected_revision,
        )
        .values(
            **dict(changes),
            aggregate_revision=table.c.aggregate_revision + 1,
            updated_at=sa.func.now(),
        )
    )
    result = session.execute(statement)
    if result.rowcount != 1:
        raise OptimisticRevisionConflictError("aggregate was changed or is unavailable")
    return expected_revision + 1
