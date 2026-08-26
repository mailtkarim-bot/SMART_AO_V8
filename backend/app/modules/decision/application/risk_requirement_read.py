from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.modules.decision.application.pagination import decode_cursor
from app.modules.decision.application.queries import (
    DecisionCctpPricingCrossingProjection,
    DecisionCctpPricingCrossingReader,
    DecisionDocumentContradictionProjection,
    DecisionDocumentContradictionReader,
    DecisionPricingReconciliationProjection,
    DecisionPricingReconciliationReader,
    DecisionRiskRequirementPage,
    DecisionRiskRequirementReader,
)
from app.platform.security.authorization import (
    AuthorizationPolicyPort,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext, ActorKind, DataClassification


class PatronDecisionRiskRequirementReadService:
    """Patron-only read facade for verified links and non-financial pricing candidates."""

    def __init__(
        self,
        *,
        reader: DecisionRiskRequirementReader,
        pricing_reader: DecisionPricingReconciliationReader,
        policy: AuthorizationPolicyPort,
        crossing_reader: DecisionCctpPricingCrossingReader | None = None,
        contradiction_reader: DecisionDocumentContradictionReader | None = None,
    ) -> None:
        self._reader = reader
        self._pricing_reader = pricing_reader
        self._crossing_reader = crossing_reader
        self._contradiction_reader = contradiction_reader
        self._policy = policy

    def list_links(
        self,
        *,
        actor: ActorContext,
        case_id: UUID,
        limit: int,
        cursor: str | None,
        now: datetime,
    ) -> DecisionRiskRequirementPage:
        self._authorize(actor=actor, case_id=case_id, now=now)
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        after_created_at = None
        after_id = None
        if cursor:
            after_created_at, after_id = decode_cursor(cursor)
        return self._reader.list_for_case(
            tenant_id=actor.tenant_id,
            case_id=case_id,
            limit=limit,
            after_created_at=after_created_at,
            after_id=after_id,
        )

    def reconcile_pricing(
        self,
        *,
        actor: ActorContext,
        case_id: UUID,
        link_id: UUID,
        search: str,
        limit: int,
        now: datetime,
    ) -> tuple[DecisionPricingReconciliationProjection, ...]:
        self._authorize(actor=actor, case_id=case_id, now=now)
        normalized_search = search.strip()
        if not 2 <= len(normalized_search) <= 120:
            raise ValueError("search must contain between 2 and 120 characters")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        result = self._pricing_reader.reconcile(
            tenant_id=actor.tenant_id,
            case_id=case_id,
            link_id=link_id,
            search=normalized_search,
            limit=limit,
        )
        if result is None:
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        return result

    def cross_cctp_pricing(
        self,
        *,
        actor: ActorContext,
        case_id: UUID,
        limit: int,
        now: datetime,
    ) -> tuple[DecisionCctpPricingCrossingProjection, ...]:
        self._authorize(actor=actor, case_id=case_id, now=now)
        if self._crossing_reader is None:
            raise RuntimeError("CCTP_PRICING_CROSSING_NOT_CONFIGURED")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        return self._crossing_reader.cross(
            tenant_id=actor.tenant_id,
            case_id=case_id,
            limit=limit,
        )

    def detect_document_contradictions(
        self,
        *,
        actor: ActorContext,
        case_id: UUID,
        limit: int,
        now: datetime,
    ) -> tuple[DecisionDocumentContradictionProjection, ...]:
        self._authorize(actor=actor, case_id=case_id, now=now)
        if self._contradiction_reader is None:
            raise RuntimeError("DOCUMENT_CONTRADICTION_READER_NOT_CONFIGURED")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        return self._contradiction_reader.detect(
            tenant_id=actor.tenant_id,
            case_id=case_id,
            limit=limit,
        )

    def _authorize(self, *, actor: ActorContext, case_id: UUID, now: datetime) -> None:
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("PATRON_REQUIRED")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.DECISION_RISK_READ,
                resource=AuthorizationResource(
                    resource_type="DECISION_RISK_REGISTER",
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
