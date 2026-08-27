from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.modules.decision.application.risk import RegisterStructuredRiskHandler
from app.modules.decision.application.risk_commands import RegisterStructuredRiskCommand
from app.modules.decision.domain.risk import (
    RiskCategory,
    RiskLikelihood,
    RiskSeverity,
    RiskTreatment,
    RiskValidationError,
    StructuredRisk,
)
from app.platform.events.dispatcher import CommandContext, CommandExecutionError

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
TENANT_ID = uuid4()
ACTOR_ID = uuid4()
MEMBERSHIP_ID = uuid4()
CASE_ID = uuid4()
DCE_VERSION_ID = uuid4()
FRAGMENT_ID = uuid4()


def _command(**overrides):
    values = {
        "command_id": uuid4(),
        "idempotency_key": uuid4(),
        "correlation_id": uuid4(),
        "risk_id": uuid4(),
        "case_id": CASE_ID,
        "dce_version_id": DCE_VERSION_ID,
        "source_fragment_id": FRAGMENT_ID,
        "category": "CCAP",
        "risk_code": "CCAP-DELAI-001",
        "title": "Délai contractuel critique",
        "statement": "Le délai contractuel impose une mobilisation anticipée.",
        "severity": "HIGH",
        "likelihood": "LIKELY",
        "source_excerpt": "Le titulaire respecte le délai contractuel.",
        "source_locator": {"page": 12, "section": "CCAP 4.2"},
        "start_byte_offset": 100,
        "end_byte_offset": 150,
        "due_at": None,
    }
    values.update(overrides)
    return RegisterStructuredRiskCommand(**values)


def _context() -> CommandContext:
    return CommandContext(
        tenant_id=TENANT_ID,
        actor_id=ACTOR_ID,
        actor_kind="PATRON_ADMIN",
        received_at=NOW,
        membership_id=MEMBERSHIP_ID,
        case_id=CASE_ID,
    )


@pytest.mark.application
def test_register_risk_validates_source_and_emits_sparse_event() -> None:
    repository = MagicMock()
    repository.case_exists.return_value = True
    repository.case_uses_dce_version.return_value = True
    repository.source_exists.return_value = True
    repository.source_supports.return_value = True
    repository.functional_exists.return_value = False
    command = _command()

    outcome = RegisterStructuredRiskHandler(repository_factory=lambda _session: repository).execute(
        session=SimpleNamespace(), command=command, context=_context()
    )

    draft = repository.create.call_args.kwargs["draft"]
    assert draft.tenant_id == TENANT_ID
    assert draft.case_id == CASE_ID
    assert draft.risk.category.value == "CCAP"
    assert draft.risk.severity.value == "HIGH"
    assert draft.risk.treatment.value == "OPEN"
    assert draft.functional_key.endswith(":CCAP-DELAI-001")
    repository.source_exists.assert_called_once_with(
        session=repository.create.call_args.kwargs["session"],
        tenant_id=TENANT_ID,
        dce_version_id=DCE_VERSION_ID,
        source_fragment_id=FRAGMENT_ID,
    )
    assert outcome.result_code == "DECISION_RISK_REGISTERED"
    assert outcome.events[0].event_type == "DecisionRiskRegistered"
    assert outcome.events[0].payload == {
        "risk_id": str(command.risk_id),
        "case_id": str(CASE_ID),
        "category": "CCAP",
        "severity": "HIGH",
    }
    assert "source_excerpt" not in outcome.events[0].payload
    assert "statement" not in outcome.events[0].payload


@pytest.mark.application
def test_register_risk_fails_closed_when_source_is_not_in_tenant_version() -> None:
    repository = MagicMock()
    repository.case_exists.return_value = True
    repository.case_uses_dce_version.return_value = True
    repository.source_exists.return_value = False
    repository.source_supports.return_value = False

    with pytest.raises(CommandExecutionError, match="SOURCE_FRAGMENT_NOT_FOUND_OR_FORBIDDEN"):
        RegisterStructuredRiskHandler(repository_factory=lambda _session: repository).execute(
            session=MagicMock(), command=_command(), context=_context()
        )

    repository.create.assert_not_called()


@pytest.mark.application
def test_register_risk_rejects_stale_dce_context() -> None:
    repository = MagicMock()
    repository.case_exists.return_value = True
    repository.case_uses_dce_version.return_value = False

    with pytest.raises(CommandExecutionError, match="STALE_DCE_CONTEXT"):
        RegisterStructuredRiskHandler(repository_factory=lambda _session: repository).execute(
            session=MagicMock(), command=_command(), context=_context()
        )

    repository.create.assert_not_called()


@pytest.mark.application
def test_register_risk_rejects_functional_duplicate() -> None:
    repository = MagicMock()
    repository.case_exists.return_value = True
    repository.case_uses_dce_version.return_value = True
    repository.source_exists.return_value = True
    repository.source_supports.return_value = True
    repository.functional_exists.return_value = True

    with pytest.raises(CommandExecutionError, match="RISK_ALREADY_REGISTERED"):
        RegisterStructuredRiskHandler(repository_factory=lambda _session: repository).execute(
            session=MagicMock(), command=_command(), context=_context()
        )

    repository.create.assert_not_called()


@pytest.mark.domain
def test_structured_risk_rejects_unordered_source_offsets() -> None:
    risk = StructuredRisk(
        category=RiskCategory.CCAP,
        risk_code="RISK-1",
        title="Risque",
        statement="Énoncé",
        severity=RiskSeverity.LOW,
        likelihood=RiskLikelihood.RARE,
        treatment=RiskTreatment.OPEN,
        source_excerpt="Extrait",
        start_byte_offset=10,
        end_byte_offset=10,
        source_locator={"page": 1},
    )

    with pytest.raises(RiskValidationError, match="offsets"):
        risk.validate()
