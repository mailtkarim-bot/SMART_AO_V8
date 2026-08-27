from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


class EnterpriseCapabilityContextReader(Protocol):
    """Minimal tenant-scoped lookup required before mutating a capability."""

    def company_id_for_capability(
        self, *, tenant_id: UUID, capability_id: UUID
    ) -> UUID | None: ...


@dataclass(frozen=True, slots=True)
class RegisteredCompany:
    """Allowlisted, non-sensitive projection returned by a company registry."""

    siren: str
    legal_name: str | None
    active: bool | None
    activity_code: str | None
    source: str = "INSEE_SIRENE"


class CompanyRegistryPort(Protocol):
    """Read-only application port for bounded company registry lookup."""

    def find_by_siren(self, *, siren: str) -> RegisteredCompany | None: ...
