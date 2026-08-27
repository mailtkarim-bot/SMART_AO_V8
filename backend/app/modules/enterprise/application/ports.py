from __future__ import annotations

from typing import Protocol
from uuid import UUID


class EnterpriseCapabilityContextReader(Protocol):
    """Minimal tenant-scoped lookup required before mutating a capability."""

    def company_id_for_capability(
        self, *, tenant_id: UUID, capability_id: UUID
    ) -> UUID | None: ...
