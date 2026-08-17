from uuid import uuid4

import pytest
from app.modules.dce.application.commands import AddFinancialReportLineCommand
from app.platform.security.capabilities import Capability, capabilities_for
from app.platform.security.context import ActorKind
from pydantic import ValidationError


def _payload() -> dict[str, object]:
    return {
        "command_id": uuid4(),
        "idempotency_key": uuid4(),
        "correlation_id": uuid4(),
        "case_id": uuid4(),
        "report_id": uuid4(),
        "expected_revision": 0,
        "category": "SALES",
        "label": "Chiffre d'affaires prévisionnel",
        "quantity_decimal": "1",
        "unit": "forfait",
        "amount_minor": 125_000,
    }


def test_financial_line_command_is_closed_and_server_scoped() -> None:
    command = AddFinancialReportLineCommand(**_payload())

    assert command.command_type == "AddFinancialReportLine"
    assert command.category == "SALES"
    assert command.amount_minor == 125_000

    with pytest.raises(ValidationError):
        AddFinancialReportLineCommand(**_payload(), tenant_id=uuid4())


def test_financial_line_command_rejects_invalid_closed_values() -> None:
    payload = _payload()

    with pytest.raises(ValidationError):
        AddFinancialReportLineCommand(**{**payload, "category": "PRICE_SECRET"})

    with pytest.raises(ValidationError):
        AddFinancialReportLineCommand(**{**payload, "label": "   "})

    with pytest.raises(ValidationError):
        AddFinancialReportLineCommand(**{**payload, "expected_revision": -1})


def test_financial_line_write_capability_is_patron_only() -> None:
    patron_capabilities = capabilities_for(ActorKind.PATRON_ADMIN)
    collaborator_capabilities = capabilities_for(ActorKind.COLLABORATEUR)
    delegate_capabilities = capabilities_for(ActorKind.PATRON_DELEGATE)

    assert Capability.FINANCIAL_REPORT_LINE_WRITE in patron_capabilities
    assert Capability.FINANCIAL_REPORT_LINE_WRITE not in collaborator_capabilities
    assert Capability.FINANCIAL_REPORT_LINE_WRITE not in delegate_capabilities
