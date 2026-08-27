from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from app.modules.enterprise.application.enterprise_library import EnterpriseCompanyProjection


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


class EnterpriseLibraryReader(Protocol):
    """Read-only application port for the tenant enterprise library projection."""

    def read_company(self, *, tenant_id: UUID) -> EnterpriseCompanyProjection | None: ...
