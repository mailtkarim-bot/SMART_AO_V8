from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from app.platform.security.capabilities import Capability, capabilities_for
from app.platform.security.context import ActorKind
from pydantic import ValidationError

REPOSITORY_ROOT = Path(__file__).parents[3]
SENSITIVE_FIELD_NAMES = (
    "quantity_decimal",
    "unit_price_minor",
    "total_minor",
    "sales_total_minor",
    "direct_cost_total_minor",
    "overhead_total_minor",
    "subcontracting_total_minor",
    "contingency_total_minor",
    "gross_margin_minor",
)


@pytest.mark.architecture
@pytest.mark.security
def test_decision_read_contract_and_submission_gate_have_no_financial_field_names() -> None:
    source_paths = (
        REPOSITORY_ROOT / "backend/app/modules/decision/public/risk_requirement_read_contracts.py",
        REPOSITORY_ROOT / "backend/app/interfaces/http/routes/patron_decisions.py",
        REPOSITORY_ROOT / "backend/app/modules/decision/domain/submission_gate.py",
        REPOSITORY_ROOT / "backend/app/modules/decision/infrastructure/risk_requirement_reader.py",
        REPOSITORY_ROOT / "backend/app/modules/decision/application/risk_requirement.py",
        REPOSITORY_ROOT / "backend/app/modules/decision/application/finalize.py",
        REPOSITORY_ROOT / "backend/app/modules/patron_action/application/service.py",
        REPOSITORY_ROOT / "backend/app/modules/submission/application/service.py",
    )

    for source_path in source_paths:
        source = source_path.read_text(encoding="utf-8")
        assert not any(field_name in source for field_name in SENSITIVE_FIELD_NAMES), source_path


@pytest.mark.security
def test_decision_risk_read_is_not_a_collaborator_capability() -> None:
    collaborator_capabilities = capabilities_for(ActorKind.COLLABORATEUR)

    assert Capability.DECISION_RISK_READ not in collaborator_capabilities
    assert Capability.DECISION_RISK_READ.value not in collaborator_capabilities


def test_decision_pricing_contract_rejects_financial_keys() -> None:
    from app.modules.decision.public.risk_requirement_read_contracts import (
        DecisionPricingReconciliationItem,
    )

    payload = {
        "link_id": uuid4(),
        "batch_id": uuid4(),
        "document_kind": "DPGF",
        "batch_state": "COMMITTED",
        "row_number": 1,
        "code": "BET-001",
        "designation": "Béton",
        "unit": "m3",
        "match_basis": "CODE_OR_DESIGNATION",
        "verification_status": "COMMITTED_NORMALIZED_IMPORT",
        "total_minor": 999_999,
    }

    with pytest.raises(ValidationError):
        DecisionPricingReconciliationItem.model_validate(payload)


def test_decision_link_contract_rejects_financial_keys() -> None:
    from app.modules.decision.public.risk_requirement_read_contracts import (
        DecisionRiskRequirementLinkItem,
    )

    payload = {
        "link_id": uuid4(),
        "case_id": uuid4(),
        "risk_id": uuid4(),
        "requirement_id": uuid4(),
        "dce_version_id": uuid4(),
        "relationship": "DEADLINE",
        "rationale": "Exigence confirmée",
        "source_refs": ("dce-requirement:1",),
        "created_at": datetime.now(UTC),
        "action_id": None,
        "action_state": None,
        "action_severity": None,
        "action_revision": None,
        "unit_price_minor": 100,
    }

    with pytest.raises(ValidationError):
        DecisionRiskRequirementLinkItem.model_validate(payload)
