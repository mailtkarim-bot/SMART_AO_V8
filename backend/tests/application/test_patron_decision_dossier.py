from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.modules.decision.application.patron_dossier import PatronDecisionDossierService
from app.modules.decision.infrastructure.dossier_reader import SqlAlchemyDecisionDossierReader
from app.platform.security.authorization import AuthorizationDecision, AuthorizationPolicy
from app.platform.security.capabilities import capabilities_for
from app.platform.security.context import ActorKind

from tests.application.test_financial_report_draft_lines import _seed_draft


class _SessionContext:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, *args):
        return False


class _DenyPolicy:
    def authorize(self, *, context, request):
        return AuthorizationDecision.denied(reason="test")


def _service(session):
    return PatronDecisionDossierService(
        reader=SqlAlchemyDecisionDossierReader(lambda: _SessionContext(session)),
        policy=AuthorizationPolicy(),
    )


def test_patron_decision_dossier_projects_selected_context_and_conditions(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    decision_id = uuid4()
    context_id = uuid4()
    record = SimpleNamespace(
        id=decision_id,
        aggregate_revision=1,
        case_id=case_id,
        decision_type="GO_CONDITIONNEL",
        lifecycle="FINALIZED",
        outcome="GO_CONDITIONAL",
        validity="CURRENT",
        context_status="FROZEN",
        final_justification="Validation patronale",
    )
    context = SimpleNamespace(
        id=context_id,
        canonical_context_json={"known": ["RC"], "risks": ["DEADLINE"]},
        unknowns_json=["VISIT_DATE"],
        context_fingerprint="a" * 64,
    )
    reference = SimpleNamespace(
        aggregate_type="DceVersion",
        aggregate_id=uuid4(),
        aggregate_revision=2,
        reference_role="SOURCE",
    )
    condition = SimpleNamespace(
        id=uuid4(),
        label="Visite obligatoire",
        status="OPEN",
        due_at=None,
        failure_consequence="NO_GO",
    )
    session = MagicMock()
    session.scalar.side_effect = [record, context]
    session.scalars.side_effect = [
        MagicMock(all=lambda: [reference]),
        MagicMock(all=lambda: [condition]),
    ]
    result = _service(session).read(
        actor=actor,
        case_id=case_id,
        now=datetime.now(tz=UTC),
    )
    assert result.decision_id == decision_id
    assert result.known == ("RC",)
    assert result.unknowns == ("VISIT_DATE",)
    assert result.risks == ("DEADLINE",)
    assert result.sources[0]["role"] == "SOURCE"
    assert result.conditions[0]["status"] == "OPEN"
    assert result.context_fingerprint == "a" * 64


def test_patron_decision_dossier_falls_back_to_latest_context(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    record = SimpleNamespace(
        id=uuid4(),
        aggregate_revision=1,
        case_id=case_id,
        decision_type="GO",
        lifecycle="FINALIZED",
        outcome="GO",
        validity="CURRENT",
        context_status="FROZEN",
        final_justification=None,
    )
    context = SimpleNamespace(
        id=uuid4(),
        canonical_context_json={"references": [], "risks": []},
        unknowns_json=[],
        context_fingerprint="b" * 64,
    )
    session = MagicMock()
    session.scalar.side_effect = [record, None, context]
    session.scalars.side_effect = [MagicMock(all=lambda: []), MagicMock(all=lambda: [])]
    result = _service(session).read(
        actor=actor,
        case_id=case_id,
        now=datetime.now(tz=UTC),
    )
    assert result.decision_id == record.id
    assert result.sources == ()
    assert result.context_fingerprint == "b" * 64


def test_patron_decision_dossier_refuses_missing_record_and_context(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    missing_record = MagicMock()
    missing_record.scalar.return_value = None
    with pytest.raises(PermissionError, match="NOT_FOUND_OR_FORBIDDEN"):
        _service(missing_record).read(actor=actor, case_id=case_id, now=datetime.now(tz=UTC))

    record = SimpleNamespace(
        id=uuid4(),
        aggregate_revision=1,
        case_id=case_id,
        decision_type="GO_NO_GO",
        lifecycle="DRAFT",
        outcome="UNDECIDED",
        validity="CURRENT",
        context_status="INCOMPLETE",
        final_justification=None,
    )
    missing_context = MagicMock()
    missing_context.scalar.side_effect = [record, None, None]
    result = _service(missing_context).read(actor=actor, case_id=case_id, now=datetime.now(tz=UTC))
    assert result.context_status == "INCOMPLETE"
    assert result.sources == ()


def test_patron_decision_dossier_refuses_non_patron_and_denied_policy(session_factory):
    actor, case_id, _, _ = _seed_draft(session_factory)
    collaborator = replace(
        actor,
        actor_id=uuid4(),
        identity_id=uuid4(),
        membership_id=uuid4(),
        actor_kind=ActorKind.COLLABORATEUR,
        capabilities=capabilities_for(ActorKind.COLLABORATEUR),
    )
    with pytest.raises(PermissionError, match="PATRON_REQUIRED"):
        _service(MagicMock()).read(actor=collaborator, case_id=case_id, now=datetime.now(tz=UTC))
    denied = PatronDecisionDossierService(
        reader=SqlAlchemyDecisionDossierReader(lambda: _SessionContext(MagicMock())),
        policy=_DenyPolicy(),
    )
    with pytest.raises(PermissionError, match="AUTHORIZATION_DENIED"):
        denied.read(actor=actor, case_id=case_id, now=datetime.now(tz=UTC))
