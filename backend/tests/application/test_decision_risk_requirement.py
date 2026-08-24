from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.modules.decision.application.link_commands import LinkRiskToRequirementCommand
from app.modules.decision.application.risk_requirement import LinkRiskToRequirementHandler
from app.modules.decision.domain.risk_requirement import (
    RiskRequirementLink,
    RiskRequirementLinkValidationError,
    RiskRequirementRelation,
)
from app.platform.events.dispatcher import CommandContext, CommandExecutionError
from app.platform.security.capabilities import Capability, capabilities_for
from app.platform.security.context import ActorKind

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
TENANT_ID = uuid4()
ACTOR_ID = uuid4()
MEMBERSHIP_ID = uuid4()
CASE_ID = uuid4()
RISK_ID = uuid4()
REQUIREMENT_ID = uuid4()
DCE_VERSION_ID = uuid4()


def _command(**overrides):
    values = {
        "command_id": uuid4(),
        "idempotency_key": uuid4(),
        "correlation_id": uuid4(),
        "link_id": uuid4(),
        "case_id": CASE_ID,
        "risk_id": RISK_ID,
        "requirement_id": REQUIREMENT_ID,
        "dce_version_id": DCE_VERSION_ID,
        "relationship": "IMPACTS",
        "rationale": "Le risque modifie la lecture opérationnelle de cette exigence confirmée.",
    }
    values.update(overrides)
    return LinkRiskToRequirementCommand(**values)


def _context() -> CommandContext:
    return CommandContext(
        tenant_id=TENANT_ID,
        actor_id=ACTOR_ID,
        actor_kind="PATRON_ADMIN",
        received_at=NOW,
        membership_id=MEMBERSHIP_ID,
        case_id=CASE_ID,
    )


def _repository(*, confirmed: bool = True, duplicate: bool = False) -> MagicMock:
    repository = MagicMock()
    repository.case_exists.return_value = True
    repository.case_uses_dce_version.return_value = True
    repository.risk_matches_case_and_version.return_value = True
    repository.requirement_is_confirmed.return_value = confirmed
    repository.functional_exists.return_value = duplicate
    return repository


@pytest.mark.application
def test_link_risk_to_confirmed_requirement_emits_sparse_event() -> None:
    repository = _repository()
    command = _command()

    outcome = LinkRiskToRequirementHandler(
        repository_factory=lambda _session: repository
    ).execute(session=SimpleNamespace(), command=command, context=_context())

    draft = repository.create.call_args.kwargs["draft"]
    assert draft.tenant_id == TENANT_ID
    assert draft.link.risk_id == RISK_ID
    assert draft.link.requirement_id == REQUIREMENT_ID
    assert draft.link.relationship.value == "IMPACTS"
    assert outcome.result_code == "DECISION_RISK_REQUIREMENT_LINKED"
    assert outcome.events[0].event_type == "DecisionRiskRequirementLinked"
    assert outcome.events[0].payload == {
        "link_id": str(command.link_id),
        "case_id": str(CASE_ID),
        "risk_id": str(RISK_ID),
        "requirement_id": str(REQUIREMENT_ID),
        "relationship": "IMPACTS",
    }
    assert "rationale" not in outcome.events[0].payload


@pytest.mark.application
def test_link_creates_sourced_patron_action_when_writer_is_configured() -> None:
    repository = _repository()
    action_writer = MagicMock()
    action_writer.create_from_risk_requirement_link.return_value = SimpleNamespace(
        id=uuid4(), aggregate_revision=1
    )

    outcome = LinkRiskToRequirementHandler(
        repository_factory=lambda _session: repository,
        action_writer=action_writer,
    ).execute(session=SimpleNamespace(), command=_command(), context=_context())

    action_writer.create_from_risk_requirement_link.assert_called_once()
    assert len(outcome.aggregate_refs) == 2
    assert outcome.aggregate_refs[1]["aggregate_type"] == "PatronAction"
    assert outcome.events[1].event_type == "PatronActionCreated"
    assert outcome.events[1].payload["action_type"] == "DECIDE_GO_NO_GO"
    assert outcome.events[1].payload["severity"] == "BLOCKING"


@pytest.mark.application
def test_link_rejects_requirement_without_human_confirmation() -> None:
    repository = _repository(confirmed=False)

    with pytest.raises(CommandExecutionError, match="DCE_REQUIREMENT_NOT_CONFIRMED"):
        LinkRiskToRequirementHandler(
            repository_factory=lambda _session: repository
        ).execute(session=MagicMock(), command=_command(), context=_context())

    repository.create.assert_not_called()


@pytest.mark.application
def test_link_rejects_stale_dce_context() -> None:
    repository = _repository()
    repository.case_uses_dce_version.return_value = False

    with pytest.raises(CommandExecutionError, match="STALE_DCE_CONTEXT"):
        LinkRiskToRequirementHandler(
            repository_factory=lambda _session: repository
        ).execute(session=MagicMock(), command=_command(), context=_context())

    repository.create.assert_not_called()


@pytest.mark.application
def test_link_rejects_functional_duplicate() -> None:
    repository = _repository(duplicate=True)

    with pytest.raises(CommandExecutionError, match="RISK_REQUIREMENT_LINK_ALREADY_EXISTS"):
        LinkRiskToRequirementHandler(
            repository_factory=lambda _session: repository
        ).execute(session=MagicMock(), command=_command(), context=_context())

    repository.create.assert_not_called()


@pytest.mark.application
def test_risk_requirement_link_capability_is_patron_only() -> None:
    assert Capability.DECISION_RISK_LINK_WRITE in capabilities_for(ActorKind.PATRON_ADMIN)
    assert Capability.DECISION_RISK_LINK_WRITE not in capabilities_for(ActorKind.COLLABORATEUR)


@pytest.mark.domain
def test_link_domain_rejects_blank_rationale() -> None:
    link = RiskRequirementLink(
        risk_id=RISK_ID,
        requirement_id=REQUIREMENT_ID,
        relationship=RiskRequirementRelation.IMPACTS,
        rationale="   ",
    )

    with pytest.raises(RiskRequirementLinkValidationError, match="rationale"):
        link.validate()
