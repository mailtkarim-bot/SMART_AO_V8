from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.modules.decision.application.queries import DecisionDocumentContradictionProjection
from app.modules.decision.application.risk_requirement_read import (
    PatronDecisionRiskRequirementReadService,
)
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


def _service(*, contradiction_reader=None):
    contradiction_reader = contradiction_reader or MagicMock()
    policy = MagicMock()
    policy.authorize.return_value = SimpleNamespace(allowed=True, code="ALLOWED")
    service = PatronDecisionRiskRequirementReadService(
        reader=MagicMock(),
        pricing_reader=MagicMock(),
        contradiction_reader=contradiction_reader,
        policy=policy,
    )
    return service, contradiction_reader


@pytest.mark.application
def test_contradictions_forward_tenant_case_and_limit() -> None:
    contradiction_reader = MagicMock()
    item = DecisionDocumentContradictionProjection(
        contradiction_id=uuid4(),
        dce_version_id=uuid4(),
        contradiction_type="PRICING_UNIT_MISMATCH",
        source_fragment_id=uuid4(),
        source_locator_label="CCTP · page 8",
        source_start_byte_offset=0,
        source_end_byte_offset=84,
        related_batch_id=uuid4(),
        related_document_kind="BPU",
        related_row_number=9,
        related_code="02.04",
        related_designation="Pose de garde-corps",
        related_unit="ml",
        comparison_basis="CCTP_EXPLICIT_UNIT_V1",
        verification_status="REVIEW_REQUIRED",
    )
    contradiction_reader.detect.return_value = (item,)
    service, _ = _service(contradiction_reader=contradiction_reader)

    result = service.detect_document_contradictions(
        actor=_actor(), case_id=CASE_ID, limit=25, now=NOW
    )

    assert result == (item,)
    assert contradiction_reader.detect.call_args.kwargs == {
        "tenant_id": TENANT_ID,
        "case_id": CASE_ID,
        "limit": 25,
    }


@pytest.mark.application
def test_contradictions_reject_collaborator_before_reader() -> None:
    service, contradiction_reader = _service()

    with pytest.raises(PermissionError, match="PATRON_REQUIRED"):
        service.detect_document_contradictions(
            actor=_actor(actor_kind=ActorKind.COLLABORATEUR),
            case_id=CASE_ID,
            limit=25,
            now=NOW,
        )

    contradiction_reader.detect.assert_not_called()


@pytest.mark.application
def test_contradictions_reject_invalid_limit_before_reader() -> None:
    service, contradiction_reader = _service()

    with pytest.raises(ValueError, match="between 1 and 100"):
        service.detect_document_contradictions(actor=_actor(), case_id=CASE_ID, limit=0, now=NOW)

    contradiction_reader.detect.assert_not_called()
