from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.platform.security.authorization import (
    AuthorizationPolicy,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.capabilities import Capability, capabilities_for
from app.platform.security.context import (
    ActorContext,
    ActorKind,
    AssignmentScope,
    DataClassification,
    MembershipState,
)

pytestmark = pytest.mark.security

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


def _context(
    *,
    actor_kind: ActorKind,
    capabilities: frozenset[str] | None = None,
    assignment_scopes: tuple[AssignmentScope, ...] = (),
) -> ActorContext:
    return ActorContext(
        actor_id=uuid4(),
        identity_id=uuid4(),
        tenant_id=uuid4(),
        membership_id=uuid4(),
        actor_kind=actor_kind,
        membership_state=MembershipState.ACTIVE,
        capabilities=capabilities if capabilities is not None else capabilities_for(actor_kind),
        assigned_case_ids=frozenset(scope.case_id for scope in assignment_scopes),
        session_id=uuid4(),
        authenticated_at=NOW,
        mfa_verified_at=NOW,
        correlation_id=uuid4(),
        assignment_scopes=assignment_scopes,
    )


def _resource(
    context: ActorContext,
    *,
    classification: DataClassification,
    case_id=None,
) -> AuthorizationResource:
    return AuthorizationResource(
        resource_type="CASE_RESOURCE",
        resource_id=uuid4(),
        tenant_id=context.tenant_id,
        classification=classification,
        case_id=case_id,
    )


def test_patron_admin_receives_server_catalog_but_no_claim_based_authority() -> None:
    capabilities = capabilities_for(ActorKind.PATRON_ADMIN)

    assert Capability.PRICING_READ in capabilities
    assert Capability.DECISION_FINALIZE in capabilities
    assert Capability.SUBMISSION_AUTHORIZE in capabilities
    assert Capability.MEMBERSHIP_MANAGE in capabilities
    assert Capability.CONSULTATION_READ in capabilities
    assert Capability.CASE_DCE_READ in capabilities


def test_collaborator_catalog_never_contains_financial_decision_or_submission_capabilities(
) -> None:
    capabilities = capabilities_for(ActorKind.COLLABORATEUR)

    assert Capability.CONSULTATION_READ in capabilities
    assert Capability.DCE_PREPARE in capabilities
    assert Capability.CASE_DCE_READ in capabilities
    assert Capability.PREPARATION_TRANSMIT in capabilities
    assert Capability.PRICING_READ not in capabilities
    assert Capability.DECISION_FINALIZE not in capabilities
    assert Capability.SUBMISSION_AUTHORIZE not in capabilities
    assert Capability.PRICING_READ not in capabilities


def test_case_dce_read__when_patron_has_catalog_capability__then_allows_case_scoped_read() -> None:
    context = _context(actor_kind=ActorKind.PATRON_ADMIN)
    request = AuthorizationRequest(
        action=Capability.CASE_DCE_READ,
        resource=_resource(
            context,
            classification=DataClassification.INTERNAL_OPERATIONAL,
            case_id=uuid4(),
        ),
    )

    decision = AuthorizationPolicy().authorize(context=context, request=request)

    assert decision.allowed is True
    assert decision.code == "ALLOWED"


def test_case_dce_read__when_collaborator_has_matching_case_scope__then_allows_read() -> None:
    case_id = uuid4()
    context = _context(
        actor_kind=ActorKind.COLLABORATEUR,
        assignment_scopes=(
            AssignmentScope(
                case_id=case_id,
                allowed_actions=frozenset({Capability.CASE_DCE_READ}),
                allowed_classifications=frozenset({DataClassification.INTERNAL_OPERATIONAL}),
            ),
        ),
    )
    request = AuthorizationRequest(
        action=Capability.CASE_DCE_READ,
        resource=_resource(
            context,
            classification=DataClassification.INTERNAL_OPERATIONAL,
            case_id=case_id,
        ),
    )

    decision = AuthorizationPolicy().authorize(context=context, request=request)

    assert decision.allowed is True
    assert decision.code == "ALLOWED"


def test_case_dce_read__when_collaborator_scope_lacks_read_action__then_denies_access() -> None:
    case_id = uuid4()
    context = _context(
        actor_kind=ActorKind.COLLABORATEUR,
        assignment_scopes=(
            AssignmentScope(
                case_id=case_id,
                allowed_actions=frozenset({Capability.DCE_PREPARE}),
                allowed_classifications=frozenset({DataClassification.INTERNAL_OPERATIONAL}),
            ),
        ),
    )
    request = AuthorizationRequest(
        action=Capability.CASE_DCE_READ,
        resource=_resource(
            context,
            classification=DataClassification.INTERNAL_OPERATIONAL,
            case_id=case_id,
        ),
    )

    decision = AuthorizationPolicy().authorize(context=context, request=request)

    assert decision.allowed is False
    assert decision.code == "AUTHORIZATION_DENIED"


def test_delegate_can_only_receive_explicit_capabilities_in_the_delegable_allow_list() -> None:
    capabilities = capabilities_for(
        ActorKind.PATRON_DELEGATE,
        delegated_capabilities=frozenset(
            {
                Capability.CONSULTATION_READ,
                Capability.CASE_DCE_READ,
                Capability.DECISION_FINALIZE,
                Capability.PRICING_READ,
            }
        ),
    )

    assert Capability.CONSULTATION_READ in capabilities
    assert Capability.CASE_DCE_READ in capabilities
    assert Capability.DECISION_FINALIZE in capabilities
    assert Capability.PRICING_READ not in capabilities


def test_collaborator_with_forged_financial_capability_is_denied_by_abac_classification() -> None:
    context = _context(
        actor_kind=ActorKind.COLLABORATEUR,
        capabilities=frozenset({Capability.PRICING_READ}),
    )
    request = AuthorizationRequest(
        action=Capability.PRICING_READ,
        resource=_resource(context, classification=DataClassification.FINANCIAL_PRIVATE),
    )

    decision = AuthorizationPolicy().authorize(context=context, request=request)

    assert decision.allowed is False
    assert decision.code == "AUTHORIZATION_DENIED"


def test_collaborator_requires_assignment_scope_action_and_classification_for_case_resource(
) -> None:
    case_id = uuid4()
    context = _context(
        actor_kind=ActorKind.COLLABORATEUR,
        assignment_scopes=(
            AssignmentScope(
                case_id=case_id,
                allowed_actions=frozenset({Capability.DCE_PREPARE}),
                allowed_classifications=frozenset({DataClassification.PUBLIC_TENDER}),
            ),
        ),
    )
    request = AuthorizationRequest(
        action=Capability.DCE_PREPARE,
        resource=_resource(
            context,
            classification=DataClassification.INTERNAL_OPERATIONAL,
            case_id=case_id,
        ),
    )

    decision = AuthorizationPolicy().authorize(context=context, request=request)

    assert decision.allowed is False
    assert decision.code == "AUTHORIZATION_DENIED"


def test_collaborator_assignment_scope_allows_only_declared_dce_work() -> None:
    case_id = uuid4()
    context = _context(
        actor_kind=ActorKind.COLLABORATEUR,
        assignment_scopes=(
            AssignmentScope(
                case_id=case_id,
                allowed_actions=frozenset({Capability.DCE_PREPARE}),
                allowed_classifications=frozenset({DataClassification.PUBLIC_TENDER}),
            ),
        ),
    )
    request = AuthorizationRequest(
        action=Capability.DCE_PREPARE,
        resource=_resource(
            context,
            classification=DataClassification.PUBLIC_TENDER,
            case_id=case_id,
        ),
    )

    decision = AuthorizationPolicy().authorize(context=context, request=request)

    assert decision.allowed is True


def test_security_restricted_resource_is_denied_to_standard_patron_session() -> None:
    context = _context(actor_kind=ActorKind.PATRON_ADMIN)
    request = AuthorizationRequest(
        action=Capability.CONSULTATION_READ,
        resource=_resource(context, classification=DataClassification.SECURITY_RESTRICTED),
    )

    decision = AuthorizationPolicy().authorize(context=context, request=request)

    assert decision.allowed is False
    assert decision.code == "AUTHORIZATION_DENIED"
