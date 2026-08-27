from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from app.modules.pricing.application.service import PricingScenarioService
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorKind

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)


def test_pricing_scenario_facade_uses_reader_and_dispatcher_without_session_factory() -> None:
    tenant_id = uuid4()
    case_id = uuid4()
    scenario_id = uuid4()
    actor = SimpleNamespace(
        actor_kind=ActorKind.PATRON_ADMIN,
        membership_id=uuid4(),
        tenant_id=tenant_id,
        actor_id=uuid4(),
        identity_id=uuid4(),
        session_id=uuid4(),
        correlation_id=uuid4(),
    )
    command = SimpleNamespace(scenario_id=scenario_id, case_id=case_id)
    reader = Mock()
    reader.list_for_case.return_value = ()
    policy = Mock()
    policy.authorize.return_value = SimpleNamespace(allowed=True)
    dispatcher = Mock()
    dispatcher.dispatch.return_value = SimpleNamespace(result_code="PRICING_SCENARIO_CREATED")
    service = PricingScenarioService(reader=reader, dispatcher=dispatcher, policy=policy)

    result = service.execute(actor=actor, command=command, now=NOW)
    scenarios = service.list_for_case(actor=actor, case_id=case_id, now=NOW)

    assert result.result_code == "PRICING_SCENARIO_CREATED"
    assert scenarios == ()
    reader.list_for_case.assert_called_once_with(tenant_id=tenant_id, case_id=case_id)
    dispatcher.dispatch.assert_called_once()
    authorization_request = policy.authorize.call_args.kwargs["request"]
    assert authorization_request.action is Capability.PRICING_WRITE
