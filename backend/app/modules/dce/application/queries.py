"""Read port and minimal RYOW projection for Consultation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ConsultationProjection:
    """Read-only Consultation situation safe for the first public API path."""

    id: UUID
    buyer_legal_name: str
    external_reference: str | None
    object_label: str
    location_label: str | None
    lifecycle: str
    freshness: str
    aggregate_revision: int
    lots: tuple[str, ...]
    tranches: tuple[str, ...]
    projection_status: str = "CURRENT"


class ConsultationProjectionReader(Protocol):
    """Read-only, tenant-scoped query port for Consultation."""

    def get(
        self,
        *,
        tenant_id: UUID | str,
        consultation_id: UUID | str,
    ) -> ConsultationProjection | None: ...
