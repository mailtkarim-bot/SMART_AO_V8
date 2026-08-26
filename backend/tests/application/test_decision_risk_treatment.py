from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.modules.decision.application.ports import DecisionRiskSnapshot
from app.modules.decision.application.risk import TransitionStructuredRiskTreatmentHandler
from app.modules.decision.application.risk_commands import TransitionStructuredRiskTreatmentCommand
from app.platform.events.dispatcher import CommandContext, CommandExecutionError

NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)
TENANT_ID = uuid4()
ACTOR_ID = uuid4()
MEMBERSHIP_ID = uuid4()
CASE_ID = uuid4()
RISK_ID = uuid4()
DCE_VERSION_ID = uuid4()
FRAGMENT_ID = uuid4()


def _context() -> CommandContext:
    return CommandContext(
        tenant_id=TENANT_ID,
        actor_id=ACTOR_ID,
        actor_kind="PATRON_ADMIN",
        received_at=NOW,
        membership_id=MEMBERSHIP_ID,
        case_id=CASE_ID,
    )


def _command(**overrides) -> TransitionStructuredRiskTreatmentCommand:
    values = {
        "command_id": uuid4(),
        "idempotency_key": uuid4(),
        "correlation_id": uuid4(),
        "risk_id": RISK_ID,
        "case_id": CASE_ID,
        "expected_revision": 1,
        "to_treatment": "ACCEPTED",
        "evidence_excerpt": "Le titulaire confirme le plan d'action.",
        "evidence_locator": {"page": 4, "section": "plan"},
        "evidence_start_byte_offset": 10,
        "evidence_end_byte_offset": 48,
        "rationale": "Le plan est accepté par le patron.",
    }
    values.update(overrides)
    return TransitionStructuredRiskTreatmentCommand(**values)


def _snapshot(*, treatment: str = "OPEN", revision: int = 1) -> DecisionRiskSnapshot:
    return DecisionRiskSnapshot(
        id=RISK_ID,
        tenant_id=TENANT_ID,
        case_id=CASE_ID,
        dce_version_id=DCE_VERSION_ID,
        source_fragment_id=FRAGMENT_ID,
        risk_code="CCAP-RISK-001",
        category="CCAP",
        title="Risque de délai",
        severity="HIGH",
        likelihood="LIKELY",
        treatment=treatment,
        revision=revision,
        due_at=None,
        latest_treatment_evidence=None,
    )


def test_transition_accepts_open_risk_and_emits_sparse_event() -> None:
    repository = MagicMock()
    repository.get_current.return_value = _snapshot()
    repository.source_supports.return_value = True
    command = _command()

    outcome = TransitionStructuredRiskTreatmentHandler(
        repository_factory=lambda _session: repository
    ).execute(session=SimpleNamespace(), command=command, context=_context())

    draft = repository.transition.call_args.kwargs["draft"]
    assert draft.from_treatment == "OPEN"
    assert draft.to_treatment == "ACCEPTED"
    assert draft.aggregate_revision == 2
    assert outcome.result_code == "DECISION_RISK_TREATMENT_TRANSITIONED"
    assert outcome.events[0].event_type == "DecisionRiskTreatmentTransitioned"
    assert outcome.events[0].payload == {
        "risk_id": str(RISK_ID),
        "case_id": str(CASE_ID),
        "from_treatment": "OPEN",
        "to_treatment": "ACCEPTED",
        "revision": 2,
    }
    assert "evidence_excerpt" not in outcome.events[0].payload


def test_transition_rejects_stale_revision_before_evidence_lookup() -> None:
    repository = MagicMock()
    repository.get_current.return_value = _snapshot(revision=2)

    with pytest.raises(CommandExecutionError, match="RISK_REVISION_CONFLICT"):
        TransitionStructuredRiskTreatmentHandler(
            repository_factory=lambda _session: repository
        ).execute(
            session=MagicMock(),
            command=_command(expected_revision=1),
            context=_context(),
        )

    repository.source_supports.assert_not_called()
    repository.transition.assert_not_called()


def test_transition_rejects_unproven_evidence() -> None:
    repository = MagicMock()
    repository.get_current.return_value = _snapshot()
    repository.source_supports.return_value = False

    with pytest.raises(CommandExecutionError, match="SOURCE_PROVENANCE_MISMATCH"):
        TransitionStructuredRiskTreatmentHandler(
            repository_factory=lambda _session: repository
        ).execute(session=MagicMock(), command=_command(), context=_context())

    repository.transition.assert_not_called()


@pytest.mark.parametrize(
    ("treatment", "to_treatment"),
    [("MITIGATED", "ACCEPTED"), ("MITIGATED", "MITIGATED")],
)
def test_transition_rejects_non_forward_treatment(treatment: str, to_treatment: str) -> None:
    repository = MagicMock()
    repository.get_current.return_value = _snapshot(treatment=treatment, revision=2)
    repository.source_supports.return_value = True

    with pytest.raises(CommandExecutionError, match="INVALID_RISK_TREATMENT_TRANSITION"):
        TransitionStructuredRiskTreatmentHandler(
            repository_factory=lambda _session: repository
        ).execute(
            session=MagicMock(),
            command=_command(expected_revision=2, to_treatment=to_treatment),
            context=_context(),
        )

    repository.transition.assert_not_called()
