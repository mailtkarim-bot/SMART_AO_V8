"""Framework-free authorization contracts and SEC-01 baseline policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from .context import ActorContext, ActorKind, DataClassification


@dataclass(frozen=True, slots=True)
class AuthorizationResource:
    """The minimum server-owned attributes needed to authorize one resource."""

    resource_type: str
    resource_id: UUID
    tenant_id: UUID
    classification: DataClassification
    case_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    """An authorization question asked before an application action."""

    action: str
    resource: AuthorizationResource
    mfa_required: bool = False
    evaluated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    """A decision whose public code is intentionally safe for HTTP transport."""

    allowed: bool
    code: str
    http_status_code: int
    reason: str | None = None

    @classmethod
    def allow(cls) -> AuthorizationDecision:
        return cls(allowed=True, code="ALLOWED", http_status_code=200)

    @classmethod
    def not_found_or_forbidden(cls) -> AuthorizationDecision:
        return cls(
            allowed=False,
            code="NOT_FOUND_OR_FORBIDDEN",
            http_status_code=404,
        )

    @classmethod
    def denied(cls, *, reason: str | None = None) -> AuthorizationDecision:
        return cls(
            allowed=False,
            code="AUTHORIZATION_DENIED",
            http_status_code=403,
            reason=reason,
        )

    @classmethod
    def step_up_required(cls) -> AuthorizationDecision:
        return cls(allowed=False, code="STEP_UP_REQUIRED", http_status_code=403)


class AuthorizationPolicyPort(Protocol):
    """Application-facing policy port implemented without HTTP or ORM concerns."""

    def authorize(
        self,
        *,
        context: ActorContext,
        request: AuthorizationRequest,
    ) -> AuthorizationDecision: ...


class AuthorizationPolicy:
    """The deliberately small S02-A baseline policy.

    It provides a single deny-by-default path that future module policies can
    compose with. It does not replace future business-state rules; handlers keep
    ownership of those transitions.
    """

    def authorize(
        self,
        *,
        context: ActorContext,
        request: AuthorizationRequest,
    ) -> AuthorizationDecision:
        resource = request.resource

        if context.tenant_id != resource.tenant_id:
            return AuthorizationDecision.not_found_or_forbidden()
        if not context.membership_is_active:
            return AuthorizationDecision.denied(reason="membership is not active")
        if request.action not in context.capabilities:
            return AuthorizationDecision.denied(reason="capability is missing")
        if resource.classification in {
            DataClassification.SECURITY_RESTRICTED,
            DataClassification.SUPPORT_RESTRICTED,
        }:
            return AuthorizationDecision.denied(
                reason="restricted classification requires a dedicated flow"
            )
        if (
            resource.classification is DataClassification.FINANCIAL_PRIVATE
            and context.actor_kind is not ActorKind.PATRON_ADMIN
        ):
            return AuthorizationDecision.denied(reason="financial data requires patron access")
        if context.actor_kind is ActorKind.COLLABORATEUR:
            if resource.case_id is None:
                return AuthorizationDecision.denied(
                    reason="collaborator resource has no case scope"
                )
            assignment_scope = context.assignment_scope_for(case_id=resource.case_id)
            if assignment_scope is None:
                return AuthorizationDecision.denied(reason="case assignment is missing")
            if request.action not in assignment_scope.allowed_actions:
                return AuthorizationDecision.denied(reason="assignment action is missing")
            if resource.classification not in assignment_scope.allowed_classifications:
                return AuthorizationDecision.denied(reason="assignment classification is missing")
        if request.mfa_required and (
            request.evaluated_at is None
            or not context.has_recent_mfa(evaluated_at=request.evaluated_at)
        ):
            return AuthorizationDecision.step_up_required()
        return AuthorizationDecision.allow()
