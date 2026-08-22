from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.platform.security.authorization import (
    AuthorizationPolicyPort,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext, ActorKind, DataClassification
from app.platform.security.models import (
    PricingImportBatchRecord,
    PricingImportRowRecord,
    PricingImportTransitionRecord,
)


@dataclass(frozen=True, slots=True)
class PricingImportRowProjection:
    row_number: int
    code: str | None
    designation: str | None
    unit: str | None
    quantity_decimal: str | None
    unit_price_minor: int | None
    total_minor: int | None
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PricingImportBatchProjection:
    batch_id: UUID
    case_id: UUID
    document_kind: str
    state: str
    aggregate_revision: int
    row_count: int
    valid_row_count: int
    error_count: int
    total_minor: int
    rows: tuple[PricingImportRowProjection, ...]


class PricingImportReadService:
    """Read one private normalized pricing preview for a patron."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        policy: AuthorizationPolicyPort,
    ) -> None:
        self._session_factory = session_factory
        self._policy = policy

    def get(
        self,
        *,
        actor: ActorContext,
        case_id: UUID,
        batch_id: UUID,
        now: datetime,
    ) -> PricingImportBatchProjection:
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("FORBIDDEN")

        with self._session_factory() as session:
            batch = session.scalar(
                sa.select(PricingImportBatchRecord).where(
                    PricingImportBatchRecord.tenant_id == actor.tenant_id,
                    PricingImportBatchRecord.case_id == case_id,
                    PricingImportBatchRecord.id == batch_id,
                )
            )
            if batch is None:
                raise PermissionError("NOT_FOUND_OR_FORBIDDEN")

            decision = self._policy.authorize(
                context=actor,
                request=AuthorizationRequest(
                    action=Capability.FINANCIAL_REPORT_LINE_WRITE,
                    resource=AuthorizationResource(
                        resource_type="PRICING_IMPORT",
                        resource_id=batch.id,
                        tenant_id=batch.tenant_id,
                        classification=DataClassification.FINANCIAL_PRIVATE,
                        case_id=batch.case_id,
                    ),
                    evaluated_at=now,
                ),
            )
            if not decision.allowed:
                raise PermissionError("FORBIDDEN")

            latest_transition = session.scalar(
                sa.select(PricingImportTransitionRecord)
                .where(
                    PricingImportTransitionRecord.tenant_id == actor.tenant_id,
                    PricingImportTransitionRecord.batch_id == batch.id,
                )
                .order_by(PricingImportTransitionRecord.version.desc())
                .limit(1)
            )
            current_state = latest_transition.to_state if latest_transition else batch.state
            current_revision = (
                latest_transition.version
                if latest_transition
                else batch.aggregate_revision
            )
            rows = session.scalars(
                sa.select(PricingImportRowRecord)
                .where(
                    PricingImportRowRecord.tenant_id == actor.tenant_id,
                    PricingImportRowRecord.batch_id == batch.id,
                )
                .order_by(PricingImportRowRecord.row_number)
            ).all()
            return PricingImportBatchProjection(
                batch_id=batch.id,
                case_id=batch.case_id,
                document_kind=batch.document_kind,
                state=current_state,
                aggregate_revision=current_revision,
                row_count=batch.row_count,
                valid_row_count=batch.valid_row_count,
                error_count=batch.error_count,
                total_minor=batch.total_minor,
                rows=tuple(
                    PricingImportRowProjection(
                        row_number=row.row_number,
                        code=row.code,
                        designation=row.designation,
                        unit=row.unit,
                        quantity_decimal=row.quantity_decimal,
                        unit_price_minor=row.unit_price_minor,
                        total_minor=row.total_minor,
                        errors=tuple(row.error_codes_json or []),
                    )
                    for row in rows
                ),
            )
