from __future__ import annotations

from typing import Protocol
from uuid import UUID


class CaseExistenceReader(Protocol):
    """Minimal tenant-scoped Case lookup required by pricing application services."""

    def exists(self, *, tenant_id: UUID, case_id: UUID) -> bool: ...
