"""Closed patron-only reads of published immutable financial snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.platform.security.authorization import (
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext, DataClassification
from app.platform.security.models import FinancialReportLineRecord, FinancialReportSnapshotRecord


@dataclass(frozen=True, slots=True)
class FinancialReportLineProjection:
    line_id: UUID
    category: str
    label: str
    quantity_decimal: str
    unit: str
    amount_minor: int
    currency_code: str


@dataclass(frozen=True, slots=True)
class FinancialReportProjection:
    report_id: UUID
    case_id: UUID
    currency_code: str
    calculated_at: datetime
    ruleset_version: int
    summary: dict[str, int]
    lines: tuple[FinancialReportLineProjection, ...]


class PatronFinancialReportService:
    def __init__(self, *, session_factory: sessionmaker[Session], policy) -> None:
        self._session_factory = session_factory
        self._policy = policy

    def get(
        self, *, actor: ActorContext, case_id: UUID, report_id: UUID, now: datetime
    ) -> FinancialReportProjection:
        with self._session_factory() as session:
            snapshot = session.scalar(
                sa.select(FinancialReportSnapshotRecord).where(
                    FinancialReportSnapshotRecord.tenant_id == actor.tenant_id,
                    FinancialReportSnapshotRecord.case_id == case_id,
                    FinancialReportSnapshotRecord.id == report_id,
                    FinancialReportSnapshotRecord.state == "PUBLISHED",
                )
            )
            if snapshot is None:
                raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
            decision = self._policy.authorize(
                context=actor,
                request=AuthorizationRequest(
                    action=Capability.FINANCIAL_REPORT_READ,
                    resource=AuthorizationResource(
                        resource_type="CASE_FINANCIAL_REPORT",
                        resource_id=snapshot.id,
                        tenant_id=snapshot.tenant_id,
                        classification=DataClassification.FINANCIAL_PRIVATE,
                        case_id=snapshot.case_id,
                    ),
                    evaluated_at=now,
                ),
            )
            if not decision.allowed:
                raise PermissionError("FORBIDDEN")
            lines = session.scalars(
                sa.select(FinancialReportLineRecord)
                .where(
                    FinancialReportLineRecord.tenant_id == actor.tenant_id,
                    FinancialReportLineRecord.snapshot_id == snapshot.id,
                )
                .order_by(FinancialReportLineRecord.created_at, FinancialReportLineRecord.id)
            ).all()
            return FinancialReportProjection(
                report_id=snapshot.id,
                case_id=snapshot.case_id,
                currency_code=snapshot.currency_code,
                calculated_at=snapshot.calculated_at,
                ruleset_version=snapshot.ruleset_version,
                summary={
                    "sales_total_minor": snapshot.sales_total_minor,
                    "direct_cost_total_minor": snapshot.direct_cost_total_minor,
                    "overhead_total_minor": snapshot.overhead_total_minor,
                    "subcontracting_total_minor": snapshot.subcontracting_total_minor,
                    "contingency_total_minor": snapshot.contingency_total_minor,
                    "gross_margin_minor": snapshot.gross_margin_minor,
                    "gross_margin_rate_bps": snapshot.gross_margin_rate_bps,
                    "forecast_cashflow_minor": snapshot.forecast_cashflow_minor,
                },
                lines=tuple(
                    FinancialReportLineProjection(
                        line_id=line.id,
                        category=line.category,
                        label=line.label,
                        quantity_decimal=line.quantity_decimal,
                        unit=line.unit,
                        amount_minor=line.amount_minor,
                        currency_code=snapshot.currency_code,
                    )
                    for line in lines
                ),
            )
