import pytest
from app.modules.decision.domain.submission_gate import (
    DecisionSubmissionGateSnapshot,
    SubmissionGateStatus,
    evaluate_submission_gate,
)


def _snapshot(**overrides):
    values = {
        "lifecycle": "FINALIZED",
        "outcome": "GO",
        "context_status": "FROZEN",
        "condition_status": "NOT_APPLICABLE",
        "open_condition_count": 0,
        "unresolved_risk_action_count": 0,
        "all_dce_requirements_confirmed": True,
    }
    values.update(overrides)
    return DecisionSubmissionGateSnapshot(**values)


@pytest.mark.domain
def test_go_with_verified_context_and_resolved_risk_actions_is_ready() -> None:
    result = evaluate_submission_gate(_snapshot())

    assert result.status is SubmissionGateStatus.READY
    assert result.can_submit is True
    assert result.reasons == ()


@pytest.mark.domain
@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"outcome": "NO_GO"}, "NO_GO_DECISION"),
        ({"lifecycle": "PENDING_PATRON"}, "DECISION_NOT_FINALIZED"),
        ({"all_dce_requirements_confirmed": False}, "DCE_REQUIREMENTS_NOT_CONFIRMED"),
        ({"unresolved_risk_action_count": 1}, "UNRESOLVED_RISK_ACTIONS"),
    ],
)
def test_submission_gate_blocks_non_submitable_states(overrides, reason) -> None:
    result = evaluate_submission_gate(_snapshot(**overrides))

    assert result.status is SubmissionGateStatus.BLOCKED
    assert reason in result.reasons
    assert result.can_submit is False


@pytest.mark.domain
def test_conditional_go_requires_all_conditions_satisfied() -> None:
    result = evaluate_submission_gate(
        _snapshot(
            outcome="CONDITIONAL_GO",
            condition_status="OPEN",
            open_condition_count=1,
        )
    )

    assert result.status is SubmissionGateStatus.BLOCKED
    assert result.reasons == ("CONDITIONAL_GO_OPEN_CONDITIONS",)


@pytest.mark.domain
def test_conditional_go_becomes_ready_only_when_conditions_are_satisfied() -> None:
    result = evaluate_submission_gate(
        _snapshot(
            outcome="CONDITIONAL_GO",
            condition_status="SATISFIED",
            open_condition_count=0,
        )
    )

    assert result.status is SubmissionGateStatus.READY
