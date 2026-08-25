from __future__ import annotations

from dataclasses import dataclass

from .cost_basis import CostBasisInput, calculate_cost_basis


@dataclass(frozen=True, slots=True)
class PricingScenarioAmounts:
    """Deterministic monetary outputs expressed in minor currency units and basis points."""

    sales_total_minor: int
    total_cost_minor: int
    gross_margin_minor: int
    gross_margin_rate_bps: int


def calculate_pricing_scenario_amounts(
    *,
    sales_total_minor: int,
    direct_cost_total_minor: int,
    overhead_total_minor: int,
    subcontracting_total_minor: int,
    contingency_total_minor: int,
    sales_adjustment_bps: int,
    cost_adjustment_bps: int,
) -> PricingScenarioAmounts:
    """Calculate scenario amounts with integer arithmetic and no persistence coupling."""

    sales = sales_total_minor * (10000 + sales_adjustment_bps) // 10000
    base_costs = (
        direct_cost_total_minor
        + overhead_total_minor
        + subcontracting_total_minor
        + contingency_total_minor
    )
    costs = base_costs * (10000 + cost_adjustment_bps) // 10000
    basis = calculate_cost_basis(
        CostBasisInput(
            sales_total_minor=sales,
            direct_cost_total_minor=costs,
            overhead_total_minor=0,
            subcontracting_total_minor=0,
            contingency_total_minor=0,
        )
    )
    margin = basis.gross_margin_minor
    margin_bps = basis.gross_margin_rate_bps
    return PricingScenarioAmounts(
        sales_total_minor=sales,
        total_cost_minor=costs,
        gross_margin_minor=margin,
        gross_margin_rate_bps=margin_bps,
    )
