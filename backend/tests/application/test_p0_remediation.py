from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.modules.decision.application.lifecycle import (
    CreateDecisionHandler,
    FreezeDecisionContextHandler,
    ResolveDecisionConditionHandler,
)
from app.modules.decision.application.lifecycle_commands import (
    CreateDecisionCommand,
    DecisionContextReferenceInput,
    FreezeDecisionContextCommand,
    ResolveDecisionConditionCommand,
)
from app.modules.decision.application.ports import DecisionConditionTransitionDraft
from app.modules.pricing.application.import_preview import PricingImportPreviewService
from app.platform.events.dispatcher import CommandContext, CommandExecutionError
from app.platform.security.authorization import AuthorizationDecision
from app.platform.security.context import ActorContext, ActorKind, MembershipState
from openpyxl import Workbook

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)


class FakeLifecycleRepository:
    def __init__(self, snapshot=None, *, applicable_dce: bool = False) -> None:
        self.snapshot = snapshot
        self.applicable_dce = applicable_dce
        self.created_root = None
        self.created_context = None
        self.updated = None

    def case_exists(self, *, session, tenant_id, case_id):
        return True

    def case_scope_fingerprint(self, *, session, tenant_id, case_id):
        return "a" * 64

    def active_decision_exists(self, *, session, tenant_id, decision_key_hash):
        return False

    def case_has_applicable_dce(self, *, session, tenant_id, case_id):
        return self.applicable_dce

    def context_reference_is_valid(
        self,
        *,
        session,
        tenant_id,
        case_id,
        aggregate_type,
        aggregate_id,
        aggregate_revision,
        content_hash,
    ):
        return aggregate_type == "CASE" and aggregate_id == case_id

    def next_cycle_number(self, *, session, tenant_id, decision_key_hash):
        return 1

    def create_root(self, *, session, draft):
        self.created_root = draft

    def create_context(self, *, session, context, references):
        self.created_context = (context, references)


class FakeDecisionRepository:
    def __init__(self, snapshot) -> None:
        self.snapshot = snapshot
        self.updated = None

    def get(self, *, tenant_id, aggregate_id):
        return self.snapshot

    def update_root(self, *, tenant_id, aggregate_id, expected_revision, changes):
        self.updated = (expected_revision, changes)
        self.snapshot.root.aggregate_revision = expected_revision + 1
        return expected_revision + 1


class FakeConditionRepository:
    def __init__(self) -> None:
        self.transition_draft: DecisionConditionTransitionDraft | None = None

    def transition(self, *, session, draft):
        self.transition_draft = draft


def command_context(*, actor_kind: str = "PATRON_ADMIN") -> CommandContext:
    return CommandContext(
        tenant_id=uuid4(),
        actor_id=uuid4(),
        actor_kind=actor_kind,
        received_at=NOW,
        membership_id=uuid4(),
    )


def decision_snapshot(*, condition_status: str = "OPEN"):
    decision_id = uuid4()
    condition_id = uuid4()
    root = SimpleNamespace(
        id=decision_id,
        case_id=uuid4(),
        aggregate_revision=3,
        decision_type="GO_NO_GO",
        lifecycle="FINALIZED",
        outcome="CONDITIONAL_GO",
        validity="CURRENT",
        context_status="FROZEN",
        condition_status=condition_status,
    )
    condition = SimpleNamespace(
        id=condition_id,
        status="OPEN",
        label="Obtenir l’attestation d’assurance",
        failure_consequence="NO_GO",
    )
    return SimpleNamespace(
        root=root, contexts=(), context_references=(), conditions=(condition,)
    ), condition_id


def test_create_and_freeze_decision_are_available_to_application_handlers():
    lifecycle_repository = FakeLifecycleRepository()
    context = command_context()
    decision_id = uuid4()
    case_id = uuid4()
    created = CreateDecisionHandler(repository=lifecycle_repository).execute(
        session=object(),
        command=CreateDecisionCommand(
            command_id=uuid4(),
            idempotency_key=uuid4(),
            decision_id=decision_id,
            case_id=case_id,
            scope_fingerprint="a" * 64,
        ),
        context=context,
    )
    assert created.result_code == "DECISION_DRAFT_CREATED"
    assert lifecycle_repository.created_root.id == decision_id

    freeze_repository = FakeDecisionRepository(
        SimpleNamespace(
            root=SimpleNamespace(
                case_id=case_id,
                aggregate_revision=0,
                decision_type="GO_NO_GO",
                lifecycle="DRAFT",
                context_status="INCOMPLETE",
            ),
            contexts=(),
        )
    )
    context_id = uuid4()
    frozen = FreezeDecisionContextHandler(
        lifecycle_repository=lifecycle_repository,
        repository_factory=lambda _session: freeze_repository,
    ).execute(
        session=object(),
        command=FreezeDecisionContextCommand(
            command_id=uuid4(),
            idempotency_key=uuid4(),
            decision_id=decision_id,
            case_id=case_id,
            context_id=context_id,
            expected_revision=0,
            rationale="Périmètre vérifié par le patron.",
            references=(
                DecisionContextReferenceInput(
                    aggregate_type="CASE",
                    aggregate_id=case_id,
                    aggregate_revision=1,
                    reference_role="SUBJECT",
                ),
            ),
        ),
        context=context,
    )
    assert frozen.result_code == "DECISION_CONTEXT_FROZEN"
    assert frozen.aggregate_refs[1]["fingerprint"]
    assert freeze_repository.updated[1]["context_status"] == "FROZEN"


def test_conditional_go_condition_resolution_updates_projection_and_is_append_only():
    snapshot, condition_id = decision_snapshot()
    decision_repository = FakeDecisionRepository(snapshot)
    transition_repository = FakeConditionRepository()
    command = ResolveDecisionConditionCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        transition_id=uuid4(),
        decision_id=snapshot.root.id,
        case_id=snapshot.root.case_id,
        condition_id=condition_id,
        expected_revision=3,
        target_status="SATISFIED",
        evidence_reference="enterprise-proof:2026-08-25",
    )
    outcome = ResolveDecisionConditionHandler(
        repository_factory=lambda _session: decision_repository,
        condition_repository=transition_repository,
    ).execute(session=object(), command=command, context=command_context())
    assert outcome.result_code == "DECISION_CONDITION_RESOLVED"
    assert transition_repository.transition_draft is not None
    assert transition_repository.transition_draft.to_status == "SATISFIED"
    assert decision_repository.updated[1]["condition_status"] == "SATISFIED"


def test_conditional_go_condition_requires_evidence_or_failure_reason():
    snapshot, condition_id = decision_snapshot()
    with pytest.raises(CommandExecutionError, match="CONDITION_EVIDENCE_REQUIRED"):
        ResolveDecisionConditionHandler(
            repository_factory=lambda _session: FakeDecisionRepository(snapshot),
            condition_repository=FakeConditionRepository(),
        ).execute(
            session=object(),
            command=ResolveDecisionConditionCommand(
                command_id=uuid4(),
                idempotency_key=uuid4(),
                transition_id=uuid4(),
                decision_id=snapshot.root.id,
                case_id=snapshot.root.case_id,
                condition_id=condition_id,
                expected_revision=3,
                target_status="SATISFIED",
            ),
            context=command_context(),
        )


class AllowPolicy:
    def authorize(self, *, context, request):
        return AuthorizationDecision(allowed=True, code="ALLOWED", http_status_code=200)


def pricing_actor() -> ActorContext:
    actor_id = uuid4()
    return ActorContext(
        actor_id=actor_id,
        identity_id=uuid4(),
        tenant_id=uuid4(),
        membership_id=uuid4(),
        actor_kind=ActorKind.PATRON_ADMIN,
        membership_state=MembershipState.ACTIVE,
        capabilities=frozenset(),
        assigned_case_ids=frozenset(),
        session_id=None,
        authenticated_at=NOW,
        mfa_verified_at=None,
        correlation_id=uuid4(),
    )


def xlsx_with_rows(count: int) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Code", "Designation", "Unit", "Quantity", "Unit Price"])
    for index in range(1, count + 1):
        sheet.append([f"L-{index}", f"Ligne {index}", "u", 1, 10])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_pricing_preview_returns_all_rows_up_to_the_declared_safety_budget():
    preview = PricingImportPreviewService(policy=AllowPolicy()).preview(
        actor=pricing_actor(),
        case_id=uuid4(),
        document_kind="DPGF",
        filename="dpgf.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        payload=xlsx_with_rows(150),
    )
    assert preview.row_count == 150
    assert len(preview.rows) == 150
    assert preview.rows[-1].row_number == 151


def test_freeze_requires_dce_requirement_reference_when_case_has_dce():
    lifecycle_repository = FakeLifecycleRepository(applicable_dce=True)
    case_id = uuid4()
    decision_id = uuid4()
    decision_repository = FakeDecisionRepository(
        SimpleNamespace(
            root=SimpleNamespace(
                case_id=case_id,
                aggregate_revision=0,
                decision_type="GO_NO_GO",
                lifecycle="DRAFT",
                context_status="INCOMPLETE",
            ),
            contexts=(),
        )
    )
    with pytest.raises(CommandExecutionError, match="DCE_REQUIREMENT_REFERENCE_REQUIRED"):
        FreezeDecisionContextHandler(
            lifecycle_repository=lifecycle_repository,
            repository_factory=lambda _session: decision_repository,
        ).execute(
            session=object(),
            command=FreezeDecisionContextCommand(
                command_id=uuid4(),
                idempotency_key=uuid4(),
                decision_id=decision_id,
                case_id=case_id,
                context_id=uuid4(),
                expected_revision=0,
                rationale="Périmètre contrôlé.",
                references=(
                    DecisionContextReferenceInput(
                        aggregate_type="CASE",
                        aggregate_id=case_id,
                        aggregate_revision=1,
                        reference_role="SUBJECT",
                    ),
                ),
            ),
            context=command_context(),
        )
