from unittest.mock import MagicMock
from uuid import uuid4

from app.modules.decision.application.ports import DecisionRiskRequirementLinkDraft
from app.modules.decision.domain.risk_requirement import (
    RiskRequirementLink,
    RiskRequirementRelation,
)
from app.modules.decision.infrastructure.risk_requirement_repository import (
    SqlAlchemyDecisionRiskRequirementLinkRepository,
)


def test_requirement_is_confirmed_uses_current_confirmation_projection() -> None:
    repository = SqlAlchemyDecisionRiskRequirementLinkRepository()
    session = MagicMock()
    session.scalar.return_value = uuid4()

    assert repository.requirement_is_confirmed(
        session=session,
        tenant_id=uuid4(),
        requirement_id=uuid4(),
        dce_version_id=uuid4(),
    ) is True
    session.scalar.assert_called_once()


def test_requirement_is_not_confirmed_when_current_projection_is_absent() -> None:
    repository = SqlAlchemyDecisionRiskRequirementLinkRepository()
    session = MagicMock()
    session.scalar.return_value = None

    assert repository.requirement_is_confirmed(
        session=session,
        tenant_id=uuid4(),
        requirement_id=uuid4(),
        dce_version_id=uuid4(),
    ) is False


def test_create_persists_only_safe_reference_identifiers() -> None:
    repository = SqlAlchemyDecisionRiskRequirementLinkRepository()
    session = MagicMock()
    risk_id = uuid4()
    requirement_id = uuid4()
    link = RiskRequirementLink(
        risk_id=risk_id,
        requirement_id=requirement_id,
        relationship=RiskRequirementRelation.MITIGATES,
        rationale="Le traitement patronal couvre l’exigence confirmée.",
    )
    draft = DecisionRiskRequirementLinkDraft(
        id=uuid4(),
        tenant_id=uuid4(),
        case_id=uuid4(),
        risk_id=risk_id,
        requirement_id=requirement_id,
        dce_version_id=uuid4(),
        functional_key="case:version:risk:requirement:MITIGATES",
        link=link,
        actor_id=uuid4(),
        membership_id=uuid4(),
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=None,
    )

    repository.create(session=session, draft=draft)

    record = session.add.call_args.args[0]
    assert record.relationship == "MITIGATES"
    assert record.source_refs_json == [
        f"decision-risk:{risk_id}",
        f"dce-requirement:{requirement_id}",
    ]
    assert record.rationale == draft.link.rationale
    assert "excerpt" not in str(record.source_refs_json)
