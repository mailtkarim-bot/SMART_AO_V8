from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.interfaces.http.error_mapping import authorization_http_exception
from app.platform.security.authorization import (
    AuthorizationPolicy,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.context import (
    ActorContext,
    ActorKind,
    DataClassification,
    MembershipState,
)

pytestmark = pytest.mark.security


def _context(
    *,
    actor_kind: ActorKind = ActorKind.PATRON_ADMIN,
    capabilities: frozenset[str] = frozenset({"consultation.read", "decision.finalize"}),
    assigned_case_ids: frozenset = frozenset(),
    mfa_verified_at: datetime | None = None,
) -> ActorContext:
    now = datetime(2026, 8, 13, 10, 0, tzinfo=UTC)
    return ActorContext(
        actor_id=uuid4(),
        identity_id=uuid4(),
        tenant_id=uuid4(),
        membership_id=uuid4(),
        actor_kind=actor_kind,
        membership_state=MembershipState.ACTIVE,
        capabilities=capabilities,
        assigned_case_ids=assigned_case_ids,
        session_id=uuid4(),
        authenticated_at=now,
        mfa_verified_at=mfa_verified_at,
        correlation_id=uuid4(),
    )


def _resource(
    context: ActorContext,
    *,
    tenant_id=None,
    classification: DataClassification = DataClassification.PUBLIC_TENDER,
    case_id=None,
) -> AuthorizationResource:
    return AuthorizationResource(
        resource_type="CONSULTATION",
        resource_id=uuid4(),
        tenant_id=tenant_id or context.tenant_id,
        classification=classification,
        case_id=case_id,
    )


def test_actor_context__when_constructed__then_is_immutable_and_has_no_client_roles() -> None:
    context = _context()

    with pytest.raises(FrozenInstanceError):
        context.tenant_id = uuid4()  # type: ignore[misc]

    assert context.membership_state is MembershipState.ACTIVE
    assert not hasattr(context, "client_role")
    assert not hasattr(context, "permission_payload")


def test_authorization__when_resource_belongs_to_another_tenant__then_returns_neutral_denial(
) -> None:
    context = _context()
    request = AuthorizationRequest(
        action="consultation.read",
        resource=_resource(context, tenant_id=uuid4()),
    )

    decision = AuthorizationPolicy().authorize(context=context, request=request)

    assert decision.allowed is False
    assert decision.code == "NOT_FOUND_OR_FORBIDDEN"
    assert decision.http_status_code == 404
    assert decision.reason is None


def test_authorization__when_capability_is_missing__then_denies_by_default() -> None:
    context = _context(capabilities=frozenset())
    request = AuthorizationRequest(action="consultation.read", resource=_resource(context))

    decision = AuthorizationPolicy().authorize(context=context, request=request)

    assert decision.allowed is False
    assert decision.code == "AUTHORIZATION_DENIED"
    assert decision.http_status_code == 403


def test_authorization__when_collaborator_is_not_assigned_to_case__then_denies_access() -> None:
    context = _context(
        actor_kind=ActorKind.COLLABORATEUR,
        capabilities=frozenset({"consultation.read"}),
        assigned_case_ids=frozenset(),
    )
    request = AuthorizationRequest(
        action="consultation.read",
        resource=_resource(context, case_id=uuid4()),
    )

    decision = AuthorizationPolicy().authorize(context=context, request=request)

    assert decision.allowed is False
    assert decision.code == "AUTHORIZATION_DENIED"


def test_authorization__when_collaborator_requests_financial_data__then_denies_even_with_capability(
) -> None:
    context = _context(
        actor_kind=ActorKind.COLLABORATEUR,
        capabilities=frozenset({"pricing.read"}),
    )
    request = AuthorizationRequest(
        action="pricing.read",
        resource=_resource(context, classification=DataClassification.FINANCIAL_PRIVATE),
    )

    decision = AuthorizationPolicy().authorize(context=context, request=request)

    assert decision.allowed is False
    assert decision.code == "AUTHORIZATION_DENIED"


def test_authorization__when_sensitive_action_has_stale_mfa__then_requires_step_up() -> None:
    now = datetime(2026, 8, 13, 10, 0, tzinfo=UTC)
    context = _context(mfa_verified_at=now - timedelta(minutes=16))
    request = AuthorizationRequest(
        action="decision.finalize",
        resource=_resource(context),
        mfa_required=True,
        evaluated_at=now,
    )

    decision = AuthorizationPolicy().authorize(context=context, request=request)

    assert decision.allowed is False
    assert decision.code == "STEP_UP_REQUIRED"
    assert decision.http_status_code == 403


def test_authorization__when_patron_has_capability_and_recent_mfa__then_allows_sensitive_action(
) -> None:
    now = datetime(2026, 8, 13, 10, 0, tzinfo=UTC)
    context = _context(mfa_verified_at=now - timedelta(minutes=14))
    request = AuthorizationRequest(
        action="decision.finalize",
        resource=_resource(context),
        mfa_required=True,
        evaluated_at=now,
    )

    decision = AuthorizationPolicy().authorize(context=context, request=request)

    assert decision.allowed is True
    assert decision.code == "ALLOWED"


def test_error_mapping__when_tenant_denial__then_exposes_only_neutral_code() -> None:
    context = _context()
    decision = AuthorizationPolicy().authorize(
        context=context,
        request=AuthorizationRequest(
            action="consultation.read",
            resource=_resource(context, tenant_id=uuid4()),
        ),
    )

    error = authorization_http_exception(decision)

    assert error.status_code == 404
    assert error.detail == "NOT_FOUND_OR_FORBIDDEN"
