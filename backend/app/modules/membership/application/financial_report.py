"""Patron-only projections of published and draft financial reports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.membership.application.queries import FinancialReportReader
from app.platform.security.authorization import (
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext, ActorKind, DataClassification


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
    status: str
    aggregate_revision: int


class PatronFinancialReportService:
    def __init__(self, *, reader: FinancialReportReader, policy) -> None:
        self._reader = reader
        self._policy = policy

    def get(
        self, *, actor: ActorContext, case_id: UUID, report_id: UUID, now: datetime
    ) -> FinancialReportProjection:
        return self._get_by_state(
            actor=actor,
            case_id=case_id,
            report_id=report_id,
            state="PUBLISHED",
            now=now,
        )

    def get_draft(
        self, *, actor: ActorContext, case_id: UUID, report_id: UUID, now: datetime
    ) -> FinancialReportProjection:
        return self._get_by_state(
            actor=actor,
            case_id=case_id,
            report_id=report_id,
            state="DRAFT",
            now=now,
        )

    def _get_by_state(
        self,
        *,
        actor: ActorContext,
        case_id: UUID,
        report_id: UUID,
        state: str,
        now: datetime,
    ) -> FinancialReportProjection:
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("FORBIDDEN")
        projection = self._reader.get(
            tenant_id=actor.tenant_id,
            case_id=case_id,
            report_id=report_id,
            state=state,
        )
        if projection is None:
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.FINANCIAL_REPORT_READ,
                resource=AuthorizationResource(
                    resource_type="CASE_FINANCIAL_REPORT",
                    resource_id=projection.report_id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.FINANCIAL_PRIVATE,
                    case_id=projection.case_id,
                ),
                evaluated_at=now,
            ),
        )
        if not decision.allowed:
            raise PermissionError("FORBIDDEN")
        return projection
