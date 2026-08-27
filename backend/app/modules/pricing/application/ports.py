from __future__ import annotations

from typing import TYPE_CHECKING, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from app.modules.pricing.application.import_read import PricingImportBatchProjection


class ImportPreviewReader(Protocol):
    """Read a tenant-scoped normalized pricing import preview."""

    def get(
        self, *, tenant_id: UUID, case_id: UUID, batch_id: UUID
    ) -> PricingImportBatchProjection | None: ...


class CaseExistenceReader(Protocol):
    """Minimal tenant-scoped Case lookup required by pricing application services."""

    def exists(self, *, tenant_id: UUID, case_id: UUID) -> bool: ...
