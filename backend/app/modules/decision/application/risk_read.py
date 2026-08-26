from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.modules.decision.application.ports import DecisionRiskRepository, DecisionRiskSnapshot
from app.platform.security.authorization import (
    AuthorizationPolicyPort,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext, ActorKind, DataClassification


class PatronDecisionRiskReadService:
    """Patron-only read facade for the current treatment of one structured risk."""

    def __init__(
        self,
        *,
        session_factory: Any,
        reader: DecisionRiskRepository,
        policy: AuthorizationPolicyPort,
    ) -> None:
        self._session_factory = session_factory
        self._reader = reader
        self._policy = policy

    def read(
        self, *, actor: ActorContext, case_id: UUID, risk_id: UUID, now: datetime
    ) -> DecisionRiskSnapshot:
        self._authorize(actor=actor, case_id=case_id, now=now)
        with self._session_factory() as session:
            snapshot = self._reader.get_current(
                session=session,
                tenant_id=actor.tenant_id,
                case_id=case_id,
                risk_id=risk_id,
            )
        if snapshot is None:
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        return snapshot

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
