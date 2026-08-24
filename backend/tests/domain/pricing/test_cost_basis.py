from __future__ import annotations

import pytest
from app.modules.pricing.domain.cost_basis import (
    CostBasisInput,
    CostBasisValidationError,
    calculate_cost_basis,
)


def test_cost_basis_calculates_exact_costs_and_price_thresholds() -> None:
    result = calculate_cost_basis(
        CostBasisInput(
            sales_total_minor=100_000,
            direct_cost_total_minor=40_000,
            overhead_total_minor=10_000,
            subcontracting_total_minor=5_000,
            contingency_total_minor=2_000,
            penalty_reserve_minor=1_000,
            retention_reserve_minor=500,
            guarantee_reserve_minor=500,
            floor_margin_rate_bps=1_000,
            target_margin_rate_bps=2_000,
        )
    )

    assert result.total_cost_minor == 59_000
    assert result.gross_margin_minor == 41_000
    assert result.gross_margin_rate_bps == 4_100
    assert result.break_even_sales_minor == 59_000
    assert result.floor_sales_minor == 65_556
    assert result.target_sales_minor == 73_750


def test_cost_basis_uses_ceiling_for_a_non_integer_minimum_sales() -> None:
    result = calculate_cost_basis(
        CostBasisInput(
            sales_total_minor=1_000,
            direct_cost_total_minor=1,
            overhead_total_minor=0,
            subcontracting_total_minor=0,
            contingency_total_minor=0,
            floor_margin_rate_bps=3_333,
            target_margin_rate_bps=3_333,
        )
    )

    assert result.floor_sales_minor == 2
    assert result.target_sales_minor == 2


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("direct_cost_total_minor", -1),
        ("penalty_reserve_minor", True),
        ("target_margin_rate_bps", 10_000),
        ("floor_margin_rate_bps", -1),
    ],
)
def test_cost_basis_rejects_invalid_inputs(field_name: str, value: object) -> None:
    kwargs: dict[str, object] = {
        "sales_total_minor": 100,
        "direct_cost_total_minor": 10,
        "overhead_total_minor": 0,
        "subcontracting_total_minor": 0,
        "contingency_total_minor": 0,
    }
    kwargs[field_name] = value

    with pytest.raises(CostBasisValidationError, match=field_name):
        calculate_cost_basis(CostBasisInput(**kwargs))


def test_cost_basis_rejects_floor_margin_above_target_margin() -> None:
    with pytest.raises(CostBasisValidationError, match="cannot exceed"):
        calculate_cost_basis(
            CostBasisInput(
                sales_total_minor=100,
                direct_cost_total_minor=10,
                overhead_total_minor=0,
                subcontracting_total_minor=0,
                contingency_total_minor=0,
                floor_margin_rate_bps=2_000,
                target_margin_rate_bps=1_000,
            )
        )
