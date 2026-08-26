from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.modules.dce.application.queries import (
    DceContractRiskSignalProjection,
    DceContractRiskSignalReader,
)
from app.platform.security.authorization import (
    AuthorizationPolicyPort,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext, ActorKind, DataClassification


class PatronDceContractRiskReadService:
    """Patron-only read facade for detected CCAP/CCTP contract-risk signals."""

    def __init__(
        self,
        *,
        reader: DceContractRiskSignalReader,
        policy: AuthorizationPolicyPort,
    ) -> None:
        self._reader = reader
        self._policy = policy

    def list_for_case(
        self,
        *,
        actor: ActorContext,
        case_id: UUID,
        limit: int,
        now: datetime,
    ) -> tuple[DceContractRiskSignalProjection, ...]:
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("PATRON_REQUIRED")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.CASE_DCE_READ,
                resource=AuthorizationResource(
                    resource_type="CASE_DCE_READING",
                    resource_id=case_id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                    case_id=case_id,
                ),
                evaluated_at=now,
            ),
        )
        if not decision.allowed:
            raise PermissionError(decision.code)
        return self._reader.list_for_case(
            tenant_id=actor.tenant_id,
            case_id=case_id,
            limit=limit,
        )
