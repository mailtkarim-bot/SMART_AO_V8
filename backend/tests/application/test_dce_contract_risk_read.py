from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.modules.dce.application.contract_risk_read import PatronDceContractRiskReadService
from app.platform.security.context import ActorKind

TENANT_ID = uuid4()
CASE_ID = uuid4()
NOW = datetime(2026, 8, 26, 15, 0, tzinfo=UTC)


def _actor(*, actor_kind: ActorKind = ActorKind.PATRON_ADMIN):
    return SimpleNamespace(
        actor_kind=actor_kind,
        membership_id=uuid4(),
        tenant_id=TENANT_ID,
    )


def _service():
    reader = MagicMock()
    policy = MagicMock()
    policy.authorize.return_value = SimpleNamespace(allowed=True, code="ALLOWED")
    return (
        PatronDceContractRiskReadService(reader=reader, policy=policy),
        reader,
    )


@pytest.mark.application
def test_list_for_case_authorizes_and_forwards_tenant_case_and_limit() -> None:
    service, reader = _service()
    reader.list_for_case.return_value = ()

    result = service.list_for_case(actor=_actor(), case_id=CASE_ID, limit=20, now=NOW)

    assert result == ()
    assert reader.list_for_case.call_args.kwargs == {
        "tenant_id": TENANT_ID,
        "case_id": CASE_ID,
        "limit": 20,
    }


@pytest.mark.application
def test_collaborator_cannot_read_contract_risk_signals() -> None:
    service, reader = _service()

    with pytest.raises(PermissionError, match="PATRON_REQUIRED"):
        service.list_for_case(
            actor=_actor(actor_kind=ActorKind.COLLABORATEUR),
            case_id=CASE_ID,
            limit=20,
            now=NOW,
        )

    reader.list_for_case.assert_not_called()


@pytest.mark.application
def test_invalid_limit_is_rejected_before_reader() -> None:
    service, reader = _service()

    with pytest.raises(ValueError, match="between 1 and 100"):
        service.list_for_case(actor=_actor(), case_id=CASE_ID, limit=101, now=NOW)

    reader.list_for_case.assert_not_called()


@pytest.mark.application
def test_policy_denial_is_not_transformed_into_data() -> None:
    reader = MagicMock()
    policy = MagicMock()
    policy.authorize.return_value = SimpleNamespace(allowed=False, code="CASE_FORBIDDEN")
    service = PatronDceContractRiskReadService(reader=reader, policy=policy)

    with pytest.raises(PermissionError, match="CASE_FORBIDDEN"):
        service.list_for_case(actor=_actor(), case_id=CASE_ID, limit=20, now=NOW)

    reader.list_for_case.assert_not_called()
