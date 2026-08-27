from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from app.modules.pricing.application.import_read import (
    PricingImportBatchProjection,
    PricingImportReadService,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorKind

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)


def test_pricing_import_read_service_uses_application_reader_port() -> None:
    tenant_id = uuid4()
    case_id = uuid4()
    batch_id = uuid4()
    reader = Mock()
    reader.get.return_value = PricingImportBatchProjection(
        batch_id=batch_id,
        case_id=case_id,
        document_kind="BPU",
        state="PREVIEWED",
        aggregate_revision=1,
        row_count=0,
        valid_row_count=0,
        error_count=0,
        total_minor=0,
        rows=(),
    )
    policy = Mock()
    policy.authorize.return_value = SimpleNamespace(allowed=True)
    actor = SimpleNamespace(
        actor_kind=ActorKind.PATRON_ADMIN,
        membership_id=uuid4(),
        tenant_id=tenant_id,
    )

    projection = PricingImportReadService(reader=reader, policy=policy).get(
        actor=actor,
        case_id=case_id,
        batch_id=batch_id,
        now=NOW,
    )

    assert projection.batch_id == batch_id
    reader.get.assert_called_once_with(
        tenant_id=tenant_id,
        case_id=case_id,
        batch_id=batch_id,
    )
    authorization_request = policy.authorize.call_args.kwargs["request"]
    assert authorization_request.action is Capability.FINANCIAL_REPORT_LINE_WRITE
    assert authorization_request.resource.resource_id == batch_id
