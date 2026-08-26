from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.modules.decision.application.queries import DecisionCctpPricingCrossingProjection
from app.modules.decision.application.risk_requirement_read import (
    PatronDecisionRiskRequirementReadService,
)
from app.platform.security.context import ActorKind

TENANT_ID = uuid4()
CASE_ID = uuid4()
NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)


def _actor(*, actor_kind: ActorKind = ActorKind.PATRON_ADMIN):
    return SimpleNamespace(
        actor_kind=actor_kind,
        membership_id=uuid4(),
        tenant_id=TENANT_ID,
    )


def _service(*, crossing_reader=None):
    reader = MagicMock()
    pricing_reader = MagicMock()
    crossing_reader = crossing_reader or MagicMock()
    policy = MagicMock()
    policy.authorize.return_value = SimpleNamespace(allowed=True, code="ALLOWED")
    service = PatronDecisionRiskRequirementReadService(
        reader=reader,
        pricing_reader=pricing_reader,
        crossing_reader=crossing_reader,
        policy=policy,
    )
    return service, crossing_reader


@pytest.mark.application
def test_crossing_forwards_tenant_case_and_bounded_limit() -> None:
    crossing_reader = MagicMock()
    item = DecisionCctpPricingCrossingProjection(
        dce_version_id=uuid4(),
        source_fragment_id=uuid4(),
        source_locator_label="CCTP · page 4",
        source_start_byte_offset=0,
        source_end_byte_offset=32,
        batch_id=uuid4(),
        document_kind="DPGF",
        row_number=3,
        code="BET-001",
        designation="Béton de structure",
        unit="m3",
        match_score_bps=10_000,
        match_basis="CODE_EXACT",
        verification_status="REVIEW_REQUIRED",
    )
    crossing_reader.cross.return_value = (item,)
    service, _ = _service(crossing_reader=crossing_reader)

    result = service.cross_cctp_pricing(actor=_actor(), case_id=CASE_ID, limit=25, now=NOW)

    assert result == (item,)
    assert crossing_reader.cross.call_args.kwargs == {
        "tenant_id": TENANT_ID,
        "case_id": CASE_ID,
        "limit": 25,
    }


@pytest.mark.application
def test_crossing_rejects_collaborator_before_reader() -> None:
    service, crossing_reader = _service()

    with pytest.raises(PermissionError, match="PATRON_REQUIRED"):
        service.cross_cctp_pricing(
            actor=_actor(actor_kind=ActorKind.COLLABORATEUR),
            case_id=CASE_ID,
            limit=25,
            now=NOW,
        )

    crossing_reader.cross.assert_not_called()


@pytest.mark.application
def test_crossing_rejects_invalid_limit_before_reader() -> None:
    service, crossing_reader = _service()

    with pytest.raises(ValueError, match="between 1 and 100"):
        service.cross_cctp_pricing(actor=_actor(), case_id=CASE_ID, limit=0, now=NOW)

    crossing_reader.cross.assert_not_called()
