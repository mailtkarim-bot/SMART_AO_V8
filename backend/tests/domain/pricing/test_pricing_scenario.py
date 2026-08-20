from __future__ import annotations

import pytest
from app.modules.pricing.domain.scenario import calculate_pricing_scenario_amounts


@pytest.mark.domain
def test_pricing_scenario_amounts_use_integer_minor_units() -> None:
    amounts = calculate_pricing_scenario_amounts(
        sales_total_minor=100_000,
        direct_cost_total_minor=40_000,
        overhead_total_minor=10_000,
        subcontracting_total_minor=5_000,
        contingency_total_minor=5_000,
        sales_adjustment_bps=500,
        cost_adjustment_bps=-250,
    )

    assert amounts.sales_total_minor == 105_000
    assert amounts.total_cost_minor == 58_500
    assert amounts.gross_margin_minor == 46_500
    assert amounts.gross_margin_rate_bps == 4_428


@pytest.mark.domain
def test_pricing_scenario_amounts_avoid_division_by_zero() -> None:
    amounts = calculate_pricing_scenario_amounts(
        sales_total_minor=0,
        direct_cost_total_minor=1_000,
        overhead_total_minor=0,
        subcontracting_total_minor=0,
        contingency_total_minor=0,
        sales_adjustment_bps=0,
        cost_adjustment_bps=0,
    )

    assert amounts.sales_total_minor == 0
    assert amounts.total_cost_minor == 1_000
    assert amounts.gross_margin_minor == -1_000
    assert amounts.gross_margin_rate_bps == 0
