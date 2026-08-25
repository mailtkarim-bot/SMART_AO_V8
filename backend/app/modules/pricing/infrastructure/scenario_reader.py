from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.pricing.application.queries import PricingScenarioProjection
from app.modules.pricing.infrastructure.models import (
    PricingScenarioRecord,
    PricingScenarioTransitionRecord,
)


class SqlAlchemyPricingScenarioReader:
    """Read patron pricing projections without leaking ORM into application services.

    The append-only transitions table owns the current ``state`` and ``version``;
    the scenario row keeps its immutable creation snapshot. Projections merge the
    two so a patron always sees the transitioned state.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_for_case(
        self, *, tenant_id: UUID, case_id: UUID
    ) -> tuple[PricingScenarioProjection, ...]:
        with self._session_factory() as session:
            latest_version = (
                sa.select(sa.func.max(PricingScenarioTransitionRecord.version))
                .where(
                    PricingScenarioTransitionRecord.tenant_id == tenant_id,
                    PricingScenarioTransitionRecord.scenario_id == PricingScenarioRecord.id,
                )
                .correlate(PricingScenarioRecord)
                .scalar_subquery()
            )
            latest_state = (
                sa.select(PricingScenarioTransitionRecord.to_state)
                .where(
                    PricingScenarioTransitionRecord.tenant_id == tenant_id,
                    PricingScenarioTransitionRecord.scenario_id == PricingScenarioRecord.id,
                    PricingScenarioTransitionRecord.version == latest_version,
                )
                .correlate(PricingScenarioRecord)
                .scalar_subquery()
            )
            rows = session.execute(
                sa.select(PricingScenarioRecord)
                .add_columns(
                    sa.func.coalesce(latest_version, PricingScenarioRecord.version).label(
                        "current_version"
                    ),
                    sa.func.coalesce(latest_state, PricingScenarioRecord.state).label(
                        "current_state"
                    ),
                )
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
                version=current_version,
                state=current_state,
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
            for record, current_version, current_state in rows
        )
