from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.pricing.application.queries import PricingScenarioProjection
from app.modules.pricing.infrastructure.models import PricingScenarioRecord


class SqlAlchemyPricingScenarioReader:
    """Read patron pricing projections without leaking ORM into application services."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_for_case(
        self, *, tenant_id: UUID, case_id: UUID
    ) -> tuple[PricingScenarioProjection, ...]:
        with self._session_factory() as session:
            records = session.scalars(
                sa.select(PricingScenarioRecord)
                .where(
                    PricingScenarioRecord.tenant_id == tenant_id,
                    PricingScenarioRecord.case_id == case_id,
                )
                .order_by(PricingScenarioRecord.created_at.desc())
            ).all()
        return tuple(
            PricingScenarioProjection(
                scenario_id=record.id,
                case_id=record.case_id,
                scenario_key=record.scenario_key,
                scenario_type=record.scenario_type,
                version=record.version,
                state=record.state,
                assumptions=record.assumptions_json,
                sales_total_minor=record.sales_total_minor,
                total_cost_minor=record.total_cost_minor,
                gross_margin_minor=record.gross_margin_minor,
                gross_margin_rate_bps=record.gross_margin_rate_bps,
                penalty_reserve_minor=record.penalty_reserve_minor,
                retention_reserve_minor=record.retention_reserve_minor,
                guarantee_reserve_minor=record.guarantee_reserve_minor,
                floor_margin_rate_bps=record.floor_margin_rate_bps,
                target_margin_rate_bps=record.target_margin_rate_bps,
                break_even_sales_minor=record.break_even_sales_minor,
                floor_sales_minor=record.floor_sales_minor,
                target_sales_minor=record.target_sales_minor,
                source_snapshot_revision=record.source_snapshot_revision,
            )
            for record in records
        )
