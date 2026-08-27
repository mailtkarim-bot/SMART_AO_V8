from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from app.modules.pricing.application.import_commands import CommitPricingImportCommand
from app.modules.pricing.application.import_service import PricingImportService
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorKind

NOW = datetime(2026, 8, 27, 14, 0, tzinfo=UTC)


def test_pricing_import_service_dispatches_without_session_factory() -> None:
    tenant_id = uuid4()
    case_id = uuid4()
    batch_id = uuid4()
    report_id = uuid4()
    actor = SimpleNamespace(
        actor_kind=ActorKind.PATRON_ADMIN,
        membership_id=uuid4(),
        tenant_id=tenant_id,
        actor_id=uuid4(),
        identity_id=uuid4(),
        session_id=uuid4(),
        correlation_id=uuid4(),
    )
    command = CommitPricingImportCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        case_id=case_id,
        report_id=report_id,
        batch_id=batch_id,
        expected_batch_revision=1,
        expected_report_revision=0,
    )
    policy = Mock()
    policy.authorize.return_value = SimpleNamespace(allowed=True)
    dispatcher = Mock()
    dispatcher.dispatch.return_value = SimpleNamespace(result_code="PRICING_IMPORT_COMMITTED")

    result = PricingImportService(dispatcher=dispatcher, policy=policy).commit(
        actor=actor,
        command=command,
        now=NOW,
    )

    assert result.result_code == "PRICING_IMPORT_COMMITTED"
    authorization_request = policy.authorize.call_args.kwargs["request"]
    assert authorization_request.action is Capability.FINANCIAL_REPORT_LINE_WRITE
    dispatcher.dispatch.assert_called_once()
    context = dispatcher.dispatch.call_args.kwargs["context"]
    assert context.tenant_id == tenant_id
    assert context.case_id == case_id
