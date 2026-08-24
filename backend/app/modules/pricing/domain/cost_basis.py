"""Exact, tenant-agnostic cost-basis calculations for patron pricing decisions."""

from __future__ import annotations

from dataclasses import dataclass


class CostBasisValidationError(ValueError):
    """Raised when a cost basis contains an invalid financial input."""


@dataclass(frozen=True, slots=True)
class CostBasisInput:
    """Financial inputs expressed only in integer minor currency units."""

    sales_total_minor: int
    direct_cost_total_minor: int
    overhead_total_minor: int
    subcontracting_total_minor: int
    contingency_total_minor: int
    penalty_reserve_minor: int = 0
    retention_reserve_minor: int = 0
    guarantee_reserve_minor: int = 0
    target_margin_rate_bps: int = 0
    floor_margin_rate_bps: int = 0

    def validate(self) -> None:
        monetary_fields = (
            ("sales_total_minor", self.sales_total_minor),
            ("direct_cost_total_minor", self.direct_cost_total_minor),
            ("overhead_total_minor", self.overhead_total_minor),
            ("subcontracting_total_minor", self.subcontracting_total_minor),
            ("contingency_total_minor", self.contingency_total_minor),
            ("penalty_reserve_minor", self.penalty_reserve_minor),
            ("retention_reserve_minor", self.retention_reserve_minor),
            ("guarantee_reserve_minor", self.guarantee_reserve_minor),
        )
        for field_name, value in monetary_fields:
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise CostBasisValidationError(f"{field_name} must be a non-negative integer")
        for field_name, value in (
            ("target_margin_rate_bps", self.target_margin_rate_bps),
            ("floor_margin_rate_bps", self.floor_margin_rate_bps),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 10_000:
                raise CostBasisValidationError(f"{field_name} must be an integer from 0 to 9999")
        if self.floor_margin_rate_bps > self.target_margin_rate_bps:
            raise CostBasisValidationError(
                "floor_margin_rate_bps cannot exceed target_margin_rate_bps"
            )


@dataclass(frozen=True, slots=True)
class CostBasisResult:
    """Deterministic cost and price-floor outputs in minor units and basis points."""

    sales_total_minor: int
    direct_cost_total_minor: int
    overhead_total_minor: int
    subcontracting_total_minor: int
    contingency_total_minor: int
    penalty_reserve_minor: int
    retention_reserve_minor: int
    guarantee_reserve_minor: int
    total_cost_minor: int
    gross_margin_minor: int
    gross_margin_rate_bps: int
    break_even_sales_minor: int
    floor_sales_minor: int
    target_sales_minor: int


def calculate_cost_basis(inputs: CostBasisInput) -> CostBasisResult:
    """Calculate cost basis, break-even and minimum sales without floating point arithmetic."""

    inputs.validate()
    total_cost = sum(
        (
            inputs.direct_cost_total_minor,
            inputs.overhead_total_minor,
            inputs.subcontracting_total_minor,
            inputs.contingency_total_minor,
            inputs.penalty_reserve_minor,
            inputs.retention_reserve_minor,
            inputs.guarantee_reserve_minor,
        )
    )
    gross_margin = inputs.sales_total_minor - total_cost
    gross_margin_rate_bps = (
        gross_margin * 10_000 // inputs.sales_total_minor
        if inputs.sales_total_minor
        else 0
    )
    return CostBasisResult(
        sales_total_minor=inputs.sales_total_minor,
        direct_cost_total_minor=inputs.direct_cost_total_minor,
        overhead_total_minor=inputs.overhead_total_minor,
        subcontracting_total_minor=inputs.subcontracting_total_minor,
        contingency_total_minor=inputs.contingency_total_minor,
        penalty_reserve_minor=inputs.penalty_reserve_minor,
        retention_reserve_minor=inputs.retention_reserve_minor,
        guarantee_reserve_minor=inputs.guarantee_reserve_minor,
        total_cost_minor=total_cost,
        gross_margin_minor=gross_margin,
        gross_margin_rate_bps=gross_margin_rate_bps,
        break_even_sales_minor=total_cost,
        floor_sales_minor=_minimum_sales_for_margin(
            total_cost, inputs.floor_margin_rate_bps
        ),
        target_sales_minor=_minimum_sales_for_margin(
            total_cost, inputs.target_margin_rate_bps
        ),
    )


def _minimum_sales_for_margin(total_cost_minor: int, margin_rate_bps: int) -> int:
    denominator = 10_000 - margin_rate_bps
    return (total_cost_minor * 10_000 + denominator - 1) // denominator
