import base64
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.modules.decision.application.queries import (
    DecisionPricingReconciliationProjection,
    DecisionRiskRequirementPage,
)
from app.modules.decision.application.risk_requirement_read import (
    PatronDecisionRiskRequirementReadService,
)
from app.platform.security.context import ActorKind

TENANT_ID = uuid4()
CASE_ID = uuid4()
LINK_ID = uuid4()
NOW = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)


def _actor(*, actor_kind=ActorKind.PATRON_ADMIN):
    return SimpleNamespace(
        actor_kind=actor_kind,
        membership_id=uuid4(),
        tenant_id=TENANT_ID,
    )


def _service(*, page=None, reconciliation=()):
    reader = MagicMock()
    reader.list_for_case.return_value = page or DecisionRiskRequirementPage(
        items=(), next_cursor=None
    )
    pricing_reader = MagicMock()
    pricing_reader.reconcile.return_value = reconciliation
    policy = MagicMock()
    policy.authorize.return_value = SimpleNamespace(allowed=True, code="ALLOWED")
    return (
        PatronDecisionRiskRequirementReadService(
            reader=reader,
            pricing_reader=pricing_reader,
            policy=policy,
        ),
        reader,
        pricing_reader,
    )


def _cursor() -> str:
    payload = f"{NOW.isoformat()}|{LINK_ID}"
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


@pytest.mark.application
def test_list_links_decodes_stable_cursor_and_keeps_page_bounded() -> None:
    page = DecisionRiskRequirementPage(items=(), next_cursor="next")
    service, reader, _ = _service(page=page)

    result = service.list_links(
        actor=_actor(),
        case_id=CASE_ID,
        limit=25,
        cursor=_cursor(),
        now=NOW,
    )

    assert result is page
    kwargs = reader.list_for_case.call_args.kwargs
    assert kwargs["tenant_id"] == TENANT_ID
    assert kwargs["case_id"] == CASE_ID
    assert kwargs["limit"] == 25
    assert kwargs["after_created_at"] == NOW
    assert kwargs["after_id"] == LINK_ID


@pytest.mark.application
def test_list_links_rejects_invalid_cursor_before_reader() -> None:
    service, reader, _ = _service()

    with pytest.raises(ValueError, match="invalid decision risk link cursor"):
        service.list_links(
            actor=_actor(), case_id=CASE_ID, limit=25, cursor="invalid", now=NOW
        )

    reader.list_for_case.assert_not_called()


@pytest.mark.application
def test_collaborator_cannot_read_risk_links_or_pricing_candidates() -> None:
    service, reader, pricing_reader = _service()

    with pytest.raises(PermissionError, match="PATRON_REQUIRED"):
        service.list_links(
            actor=_actor(actor_kind=ActorKind.COLLABORATEUR),
            case_id=CASE_ID,
            limit=25,
            cursor=None,
            now=NOW,
        )

    with pytest.raises(PermissionError, match="PATRON_REQUIRED"):
        service.reconcile_pricing(
            actor=_actor(actor_kind=ActorKind.COLLABORATEUR),
            case_id=CASE_ID,
            link_id=LINK_ID,
            search="béton",
            limit=25,
            now=NOW,
        )

    reader.list_for_case.assert_not_called()
    pricing_reader.reconcile.assert_not_called()


@pytest.mark.application
def test_reconciliation_returns_only_non_financial_candidate_metadata() -> None:
    item = DecisionPricingReconciliationProjection(
        link_id=LINK_ID,
        batch_id=uuid4(),
        document_kind="DPGF",
        batch_state="COMMITTED",
        row_number=7,
        code="BET-001",
        designation="Béton de structure",
        unit="m3",
        match_basis="CODE_OR_DESIGNATION",
        verification_status="COMMITTED_NORMALIZED_IMPORT",
    )
    service, _, pricing_reader = _service(reconciliation=(item,))

    result = service.reconcile_pricing(
        actor=_actor(),
        case_id=CASE_ID,
        link_id=LINK_ID,
        search=" Béton ",
        limit=10,
        now=NOW,
    )

    assert result == (item,)
    kwargs = pricing_reader.reconcile.call_args.kwargs
    assert kwargs["search"] == "Béton"
    assert "unit_price_minor" not in item.__dataclass_fields__
    assert "total_minor" not in item.__dataclass_fields__
