from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.pricing.application.ports import ImportPreviewReader
from app.platform.security.authorization import (
    AuthorizationPolicyPort,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext, ActorKind, DataClassification


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
        reader: ImportPreviewReader,
        policy: AuthorizationPolicyPort,
    ) -> None:
        self._reader = reader
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

        projection = self._reader.get(
            tenant_id=actor.tenant_id,
            case_id=case_id,
            batch_id=batch_id,
        )
        if projection is None:
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")

        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.FINANCIAL_REPORT_LINE_WRITE,
                resource=AuthorizationResource(
                    resource_type="PRICING_IMPORT",
                    resource_id=projection.batch_id,
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
