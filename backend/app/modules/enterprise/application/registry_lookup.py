"""Application service for bounded read-only company registry lookup."""

from __future__ import annotations

from app.modules.enterprise.application.ports import CompanyRegistryPort, RegisteredCompany


class EnterpriseRegistryLookupService:
    """Delegates a single company lookup without mutating the enterprise library."""

    def __init__(self, *, registry: CompanyRegistryPort) -> None:
        self._registry = registry

    def find_by_siren(self, *, siren: str) -> RegisteredCompany | None:
        return self._registry.find_by_siren(siren=siren)
