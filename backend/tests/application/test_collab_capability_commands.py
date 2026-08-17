from __future__ import annotations

from uuid import uuid4

import pytest
from app.modules.membership.application.collab_capability_commands import (
    ProposeCapabilityForCaseCommand,
    ReportCapabilityGapCommand,
)
from pydantic import ValidationError


def _proposal_payload() -> dict[str, object]:
    return {
        "command_id": uuid4(),
        "idempotency_key": uuid4(),
        "proposal_id": uuid4(),
        "case_id": uuid4(),
        "assignment_id": uuid4(),
        "capability_id": uuid4(),
        "capability_version_id": uuid4(),
        "requirement_id": uuid4(),
        "justification": "La qualification répond au périmètre de l’exigence.",
    }


def test_propose_capability_requires_case_source_and_rejects_finance() -> None:
    valid = ProposeCapabilityForCaseCommand(**_proposal_payload())
    assert valid.requirement_id is not None
    with pytest.raises(ValidationError, match="CAPABILITY_SOURCE_REQUIRED"):
        ProposeCapabilityForCaseCommand(
            **{key: value for key, value in _proposal_payload().items() if key != "requirement_id"}
        )
    with pytest.raises(ValidationError, match="FINANCIAL_DATA_FORBIDDEN"):
        ProposeCapabilityForCaseCommand(
            **{**_proposal_payload(), "justification": "Inclure le prix et la marge."}
        )


def test_report_gap_requires_source_and_forbids_closed_fields() -> None:
    gap = ReportCapabilityGapCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        gap_id=uuid4(),
        case_id=uuid4(),
        assignment_id=uuid4(),
        requirement_id=uuid4(),
        gap_kind="MISSING",
        severity="BLOCKING",
        reason="La preuve requise n’est pas disponible.",
        recommended_action="Demander la pièce au patron.",
    )
    assert gap.gap_kind == "MISSING"
    with pytest.raises(ValidationError, match="CAPABILITY_SOURCE_REQUIRED"):
        ReportCapabilityGapCommand(
            command_id=uuid4(),
            idempotency_key=uuid4(),
            gap_id=uuid4(),
            case_id=uuid4(),
            assignment_id=uuid4(),
            gap_kind="MISSING",
            severity="BLOCKING",
            reason="Source absente",
            recommended_action="Demander la pièce.",
        )
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ReportCapabilityGapCommand(
            **{
                "command_id": uuid4(),
                "idempotency_key": uuid4(),
                "gap_id": uuid4(),
                "case_id": uuid4(),
                "assignment_id": uuid4(),
                "requirement_id": uuid4(),
                "gap_kind": "MISSING",
                "severity": "BLOCKING",
                "reason": "Source absente",
                "recommended_action": "Demander la pièce.",
                "tenant_id": uuid4(),
            }
        )
