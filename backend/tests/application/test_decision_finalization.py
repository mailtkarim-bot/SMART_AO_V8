from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.modules.decision.application.finalize import FinalizeGoNoGoDecisionHandler
from app.modules.decision.application.finalize_commands import FinalizeGoNoGoDecisionCommand
from app.platform.events.dispatcher import CommandContext, CommandExecutionError
from app.platform.persistence.repository import OptimisticRevisionConflictError

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
TENANT_ID = uuid4()
ACTOR_ID = uuid4()
MEMBERSHIP_ID = uuid4()
CASE_ID = uuid4()
DECISION_ID = uuid4()
CONTEXT_ID = uuid4()
FINGERPRINT = "a" * 64


def _command(**overrides):
    values = {
        "command_id": uuid4(),
        "idempotency_key": uuid4(),
        "correlation_id": uuid4(),
        "decision_id": DECISION_ID,
        "case_id": CASE_ID,
        "expected_revision": 3,
        "displayed_fingerprint": FINGERPRINT,
        "outcome": "GO",
        "justification": "Le patron confirme la décision après revue des sources vérifiées.",
    }
    values.update(overrides)
    return FinalizeGoNoGoDecisionCommand(**values)


def _verified_reader(*, confirmed: bool = True) -> MagicMock:
    reader = MagicMock()
    reader.has_confirmed_dce_requirements.return_value = confirmed
    return reader


def _context() -> CommandContext:
    return CommandContext(
        tenant_id=TENANT_ID,
        actor_id=ACTOR_ID,
        actor_kind="PATRON_ADMIN",
        received_at=NOW,
        membership_id=MEMBERSHIP_ID,
        case_id=CASE_ID,
    )


def _snapshot(*, fingerprint: str = FINGERPRINT, references: tuple = ("verified-ref",)):
    return SimpleNamespace(
        root=SimpleNamespace(
            case_id=CASE_ID,
            decision_type="GO_NO_GO",
            lifecycle="PENDING_PATRON",
            outcome="UNDECIDED",
            validity="CURRENT",
            context_status="FROZEN",
        ),
        contexts=(
            SimpleNamespace(
                id=CONTEXT_ID,
                context_state="FROZEN",
                context_fingerprint=fingerprint,
            ),
        ),
        context_references=tuple(SimpleNamespace(id=ref) for ref in references),
    )


def test_finalize_go_updates_only_after_frozen_context_and_revision_check() -> None:
    repository = MagicMock()
    repository.get.return_value = _snapshot()
    repository.update_root.return_value = 4

    outcome = FinalizeGoNoGoDecisionHandler(
        repository_factory=lambda _session: repository,
        verified_context_reader=_verified_reader(),
    ).execute(session=MagicMock(), command=_command(), context=_context())

    changes = repository.update_root.call_args.kwargs["changes"]
    assert changes["lifecycle"] == "FINALIZED"
    assert changes["outcome"] == "GO"
    assert changes["selected_final_context_id"] == CONTEXT_ID
    assert changes["finalized_by_actor_id"] == ACTOR_ID
    assert outcome.aggregate_refs[0]["aggregate_revision"] == 4
    assert outcome.events[0].event_type == "DecisionFinalized"
    assert "justification" not in outcome.events[0].payload


def test_finalize_rejects_unconfirmed_dce_requirement_references() -> None:
    repository = MagicMock()
    repository.get.return_value = _snapshot()

    with pytest.raises(CommandExecutionError, match="DCE_REQUIREMENTS_NOT_CONFIRMED"):
        FinalizeGoNoGoDecisionHandler(
            repository_factory=lambda _session: repository,
            verified_context_reader=_verified_reader(confirmed=False),
        ).execute(session=MagicMock(), command=_command(), context=_context())

    repository.update_root.assert_not_called()


def test_finalize_no_go_is_human_choice_and_does_not_compute_from_documents() -> None:
    repository = MagicMock()
    repository.get.return_value = _snapshot()
    repository.update_root.return_value = 4

    outcome = FinalizeGoNoGoDecisionHandler(
        repository_factory=lambda _session: repository,
        verified_context_reader=_verified_reader(),
    ).execute(
        session=MagicMock(),
        command=_command(outcome="NO_GO"),
        context=_context(),
    )

    assert outcome.events[0].payload["outcome"] == "NO_GO"
    assert repository.update_root.call_args.kwargs["changes"]["outcome"] == "NO_GO"


@pytest.mark.parametrize(
    ("snapshot", "command", "error"),
    [
        (_snapshot(fingerprint="b" * 64), _command(), "STALE_DECISION_CONTEXT"),
        (_snapshot(references=()), _command(), "DECISION_CONTEXT_REFERENCES_REQUIRED"),
        (_snapshot(), _command(expected_revision=2), "STALE_DECISION_REVISION"),
    ],
)
def test_finalize_rejects_stale_or_unreferenced_context(snapshot, command, error) -> None:
    repository = MagicMock()
    repository.get.return_value = snapshot
    if error == "STALE_DECISION_REVISION":
        repository.update_root.side_effect = OptimisticRevisionConflictError("stale")

    with pytest.raises(CommandExecutionError, match=error):
        FinalizeGoNoGoDecisionHandler(
            repository_factory=lambda _session: repository,
            verified_context_reader=_verified_reader(),
        ).execute(session=MagicMock(), command=command, context=_context())

    if error != "STALE_DECISION_REVISION":
        repository.update_root.assert_not_called()
