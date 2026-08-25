from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PricingScenarioProjection:
    scenario_id: UUID
    case_id: UUID
    scenario_key: str
    scenario_type: str
    version: int
    state: str
    assumptions: dict[str, object]
    sales_total_minor: int
    total_cost_minor: int
    gross_margin_minor: int
    gross_margin_rate_bps: int
    penalty_reserve_minor: int
    retention_reserve_minor: int
    guarantee_reserve_minor: int
    floor_margin_rate_bps: int
    target_margin_rate_bps: int
    break_even_sales_minor: int
    floor_sales_minor: int
    target_sales_minor: int
    source_snapshot_revision: int


class PricingScenarioReader(Protocol):
    """Read tenant-scoped patron pricing projections."""

    def list_for_case(
        self, *, tenant_id: UUID, case_id: UUID
    ) -> tuple[PricingScenarioProjection, ...]: ...
