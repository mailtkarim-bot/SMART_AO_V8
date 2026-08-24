from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SubmissionGateStatus(StrEnum):
    READY = "READY"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class DecisionSubmissionGateSnapshot:
    lifecycle: str
    outcome: str
    context_status: str
    condition_status: str
    open_condition_count: int
    unresolved_risk_action_count: int
    all_dce_requirements_confirmed: bool


@dataclass(frozen=True, slots=True)
class DecisionSubmissionGateResult:
    status: SubmissionGateStatus
    reasons: tuple[str, ...]

    @property
    def can_submit(self) -> bool:
        return self.status is SubmissionGateStatus.READY


def evaluate_submission_gate(
    snapshot: DecisionSubmissionGateSnapshot,
) -> DecisionSubmissionGateResult:
    """Return a non-financial, explainable gate for future submission authorization."""
    reasons: list[str] = []
    if snapshot.lifecycle != "FINALIZED":
        reasons.append("DECISION_NOT_FINALIZED")
    if snapshot.outcome == "NO_GO":
        reasons.append("NO_GO_DECISION")
    elif snapshot.outcome not in {"GO", "CONDITIONAL_GO"}:
        reasons.append("DECISION_OUTCOME_NOT_SUBMITTABLE")
    if snapshot.context_status != "FROZEN":
        reasons.append("DECISION_CONTEXT_NOT_FROZEN")
    if not snapshot.all_dce_requirements_confirmed:
        reasons.append("DCE_REQUIREMENTS_NOT_CONFIRMED")
    if snapshot.outcome == "CONDITIONAL_GO":
        if snapshot.condition_status != "SATISFIED" or snapshot.open_condition_count:
            reasons.append("CONDITIONAL_GO_OPEN_CONDITIONS")
    elif snapshot.open_condition_count:
        reasons.append("UNEXPECTED_OPEN_CONDITIONS")
    if snapshot.unresolved_risk_action_count:
        reasons.append("UNRESOLVED_RISK_ACTIONS")
    return DecisionSubmissionGateResult(
        status=SubmissionGateStatus.BLOCKED if reasons else SubmissionGateStatus.READY,
        reasons=tuple(reasons),
    )
