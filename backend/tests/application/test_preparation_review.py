from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import sqlalchemy as sa
from app.modules.preparation.application.commands import GenerateTechnicalDocumentCommand
from app.modules.preparation.application.review import (
    PreparationReviewHandler,
    PreparationReviewService,
    preparation_review_handlers,
)
from app.modules.preparation.application.review_commands import (
    AddPreparationCorrectionCommand,
    CreateTechnicalResponseDraftCommand,
    DecidePreparationReviewCommand,
    RequestPreparationReviewCommand,
)
from app.modules.preparation.application.service import PreparationService, preparation_handlers
from app.modules.preparation.infrastructure.dce_preparation_reader import (
    SqlAlchemyPreparationDceReader,
)
from app.modules.preparation.infrastructure.document_storage import LocalGeneratedDocumentStorage
from app.platform.events.dispatcher import (
    CommandContext,
    CommandDispatcher,
    CommandExecutionError,
)
from app.platform.persistence.models import DomainEventRecord, OutboxMessageRecord
from app.platform.security.authorization import AuthorizationPolicy
from app.platform.security.capabilities import Capability, capabilities_for
from app.platform.security.context import ActorKind
from app.platform.security.models import (
    CaseAssignmentRecord,
    PreparationReviewCorrectionRecord,
    PreparationReviewRecord,
    TechnicalResponseDraftRecord,
)
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session, sessionmaker

from tests.application.test_collab_work_task import _seed
from tests.application.test_preparation_completeness import (
    NOW,
    _confirm_requirement,
    _dce_version_id,
    _enable_preparation_scope,
    _readiness_command,
)

pytest_plugins = ("tests.application.test_collab_work_task",)


@pytest.fixture
def services(session_factory: sessionmaker[Session], tmp_path: Path):
    storage = LocalGeneratedDocumentStorage(root=tmp_path / "dce-private")
    dispatcher = CommandDispatcher(
        session_factory=session_factory,
        handlers={
            **preparation_handlers(
                storage=storage,
                dce_reader=SqlAlchemyPreparationDceReader(),
            ),
            **preparation_review_handlers(storage=storage),
        },
    )
    policy = AuthorizationPolicy()
    preparation = PreparationService(
        session_factory=session_factory,
        dispatcher=dispatcher,
        policy=policy,
        storage=storage,
    )
    review = PreparationReviewService(
        session_factory=session_factory,
        dispatcher=dispatcher,
        policy=policy,
        storage=storage,
    )
    return preparation, review


def _review_scope(session_factory: sessionmaker[Session], actor, assignment_id):
    with session_factory.begin() as session:
        assignment = session.get(CaseAssignmentRecord, assignment_id)
        assignment.scope_actions_json = [
            *assignment.scope_actions_json,
            Capability.PREPARATION_REVIEW_REQUEST.value,
        ]
    scope = actor.assignment_scopes[0]
    return replace(
        actor,
        assignment_scopes=(
            replace(
                scope,
                allowed_actions=frozenset(
                    {*scope.allowed_actions, Capability.PREPARATION_REVIEW_REQUEST.value}
                ),
            ),
        ),
    )


def _patron(actor):
    return replace(
        actor,
        actor_kind=ActorKind.PATRON_ADMIN,
        capabilities=capabilities_for(ActorKind.PATRON_ADMIN),
    )


def _prepare_document(services, session_factory: sessionmaker[Session]):
    preparation, _ = services
    actor, assignment_id, case_id, requirement_id = _seed(session_factory)
    actor = _enable_preparation_scope(session_factory, actor, assignment_id)
    actor = _review_scope(session_factory, actor, assignment_id)
    dce_version_id = _dce_version_id(session_factory, actor.tenant_id)
    package_id = uuid4()
    preparation.execute(
        actor=actor,
        command=_readiness_command(
            actor=actor,
            assignment_id=assignment_id,
            case_id=case_id,
            dce_version_id=dce_version_id,
            package_id=package_id,
            expected_revision=0,
        ),
        now=NOW,
    )
    _confirm_requirement(session_factory, actor=actor, requirement_id=requirement_id)
    preparation.execute(
        actor=actor,
        command=_readiness_command(
            actor=actor,
            assignment_id=assignment_id,
            case_id=case_id,
            dce_version_id=dce_version_id,
            package_id=package_id,
            expected_revision=1,
        ),
        now=NOW,
    )
    document_id = uuid4()
    preparation.execute(
        actor=actor,
        command=GenerateTechnicalDocumentCommand(
            command_id=uuid4(),
            idempotency_key=uuid4(),
            correlation_id=uuid4(),
            package_id=package_id,
            document_id=document_id,
            expected_revision=2,
            readiness_revision=2,
            document_kind="TECHNICAL_RESPONSE",
        ),
        now=NOW,
    )
    return actor, assignment_id, case_id, requirement_id, package_id, document_id


@pytest.mark.db
@pytest.mark.security
def test_review_is_versioned_idempotent_and_corrections_are_append_only(
    services, session_factory: sessionmaker[Session]
) -> None:
    _, review = services
    actor, _, _, _, package_id, document_id = _prepare_document(services, session_factory)
    review_id = uuid4()
    request = RequestPreparationReviewCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        review_id=review_id,
        package_id=package_id,
        target_document_id=document_id,
        target_version=1,
        expected_package_revision=3,
    )
    requested = review.execute(actor=actor, command=request, now=NOW)
    replay = review.execute(actor=actor, command=request, now=NOW)
    assert requested.result_code == "PREPARATION_REVIEW_REQUESTED"
    assert replay.replayed is True
    duplicate = request.model_copy(
        update={
            "command_id": uuid4(),
            "idempotency_key": uuid4(),
            "expected_package_revision": 4,
        }
    )
    with pytest.raises(CommandExecutionError, match="REVIEW_ALREADY_EXISTS"):
        review.execute(actor=actor, command=duplicate, now=NOW)

    with pytest.raises(PermissionError, match="PATRON_REQUIRED"):
        review.execute(
            actor=actor,
            command=DecidePreparationReviewCommand(
                command_id=uuid4(),
                idempotency_key=uuid4(),
                correlation_id=uuid4(),
                review_id=review_id,
                package_id=package_id,
                target_document_id=document_id,
                expected_review_revision=1,
                decision_code="ACCEPTED",
            ),
            now=NOW,
        )

    patron = _patron(actor)
    returned = review.execute(
        actor=patron,
        command=DecidePreparationReviewCommand(
            command_id=uuid4(),
            idempotency_key=uuid4(),
            correlation_id=uuid4(),
            review_id=review_id,
            package_id=package_id,
            target_document_id=document_id,
            expected_review_revision=1,
            decision_code="CORRECTIONS_REQUIRED",
            decision_note="La section méthode doit être sourcée.",
        ),
        now=NOW,
    )
    assert returned.result_code == "PREPARATION_REVIEW_DECIDED"
    with pytest.raises(CommandExecutionError, match="VERSION_CONFLICT"):
        review.execute(
            actor=patron,
            command=DecidePreparationReviewCommand(
                command_id=uuid4(),
                idempotency_key=uuid4(),
                correlation_id=uuid4(),
                review_id=review_id,
                package_id=package_id,
                target_document_id=document_id,
                expected_review_revision=1,
                decision_code="ACCEPTED",
            ),
            now=NOW,
        )

    correction = review.execute(
        actor=patron,
        command=AddPreparationCorrectionCommand(
            command_id=uuid4(),
            idempotency_key=uuid4(),
            correlation_id=uuid4(),
            review_id=review_id,
            package_id=package_id,
            target_document_id=document_id,
            correction_code="SOURCE_MISSING",
            instruction="Ajouter la référence de la méthode utilisée.",
            source_locator="DCE p. 12",
        ),
        now=NOW,
    )
    assert correction.result_code == "PREPARATION_CORRECTION_ADDED"

    accepted = review.execute(
        actor=patron,
        command=DecidePreparationReviewCommand(
            command_id=uuid4(),
            idempotency_key=uuid4(),
            correlation_id=uuid4(),
            review_id=review_id,
            package_id=package_id,
            target_document_id=document_id,
            expected_review_revision=2,
            decision_code="ACCEPTED",
        ),
        now=NOW,
    )
    assert accepted.result_code == "PREPARATION_REVIEW_DECIDED"

    with session_factory() as session:
        reviews = list(
            session.scalars(
                sa.select(PreparationReviewRecord)
                .where(PreparationReviewRecord.tenant_id == actor.tenant_id)
                .order_by(PreparationReviewRecord.revision)
            )
        )
        corrections = list(session.scalars(sa.select(PreparationReviewCorrectionRecord)))
        assert [row.state for row in reviews] == [
            "REQUESTED",
            "RETURNED_WITH_CORRECTIONS",
            "ACCEPTED",
        ]
        assert [row.revision for row in corrections] == [1]
        assert session.scalar(sa.select(sa.func.count()).select_from(DomainEventRecord)) == 7
        assert session.scalar(sa.select(sa.func.count()).select_from(OutboxMessageRecord)) >= 7
    with pytest.raises(ProgrammingError), session_factory.begin() as session:
        session.execute(sa.delete(PreparationReviewCorrectionRecord))

    projected = review.read_reviews(actor=patron, package_id=package_id, now=NOW)
    assert len(projected) == 1
    latest_review, projected_corrections = projected[0]
    assert latest_review.state == "ACCEPTED"
    assert latest_review.revision == 3
    assert len(projected_corrections) == 1
    assert projected_corrections[0].review_revision == 2


@pytest.mark.db
@pytest.mark.security
def test_response_draft_is_versioned_replayed_and_financial_payload_is_rejected(
    services, session_factory: sessionmaker[Session]
) -> None:
    _, review = services
    actor, _, _, requirement_id, package_id, document_id = _prepare_document(
        services, session_factory
    )
    draft_id = uuid4()
    command = CreateTechnicalResponseDraftCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        draft_id=draft_id,
        package_id=package_id,
        source_document_id=document_id,
        expected_package_revision=3,
        section_codes=["METHOD", "SOURCES"],
        source_refs=[requirement_id],
    )
    created = review.execute(actor=actor, command=command, now=NOW)
    replay = review.execute(actor=actor, command=command, now=NOW)
    assert created.result_code == "TECHNICAL_RESPONSE_DRAFT_CREATED"
    assert replay.replayed is True
    with session_factory() as session:
        draft = session.scalar(sa.select(TechnicalResponseDraftRecord))
        assert draft.version == 1
        assert draft.state == "DRAFT"
        assert draft.section_codes_json == ["METHOD", "SOURCES"]
        assert "storage_key" not in {"section_codes_json", "source_refs_json"}
        assert draft.content_sha256

    with pytest.raises(ValueError, match="FINANCIAL_DATA_FORBIDDEN"):
        AddPreparationCorrectionCommand(
            command_id=uuid4(),
            idempotency_key=uuid4(),
            review_id=uuid4(),
            package_id=package_id,
            target_document_id=document_id,
            correction_code="WORDING_UNCLEAR",
            instruction="Ajouter le prix et la marge dans le texte.",
        )


@pytest.mark.db
@pytest.mark.security
def test_review_rejects_missing_target_version_and_invalid_decision_state(
    services, session_factory: sessionmaker[Session]
) -> None:
    _, review = services
    actor, _, _, _, package_id, document_id = _prepare_document(services, session_factory)
    patron = _patron(actor)
    review_id = uuid4()
    request = RequestPreparationReviewCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        review_id=review_id,
        package_id=package_id,
        target_document_id=document_id,
        target_version=1,
        expected_package_revision=3,
    )
    with pytest.raises(CommandExecutionError, match="TARGET_VERSION_NOT_FOUND"):
        review.execute(
            actor=actor,
            command=request.model_copy(update={"target_version": 99}),
            now=NOW,
        )
    review.execute(actor=actor, command=request, now=NOW)
    with pytest.raises(CommandExecutionError, match="REVIEW_NOT_FOUND"):
        review.execute(
            actor=patron,
            command=DecidePreparationReviewCommand(
                command_id=uuid4(),
                idempotency_key=uuid4(),
                correlation_id=uuid4(),
                review_id=review_id,
                package_id=package_id,
                target_document_id=uuid4(),
                expected_review_revision=1,
                decision_code="ACCEPTED",
            ),
            now=NOW,
        )
    review.execute(
        actor=patron,
        command=DecidePreparationReviewCommand(
            command_id=uuid4(),
            idempotency_key=uuid4(),
            correlation_id=uuid4(),
            review_id=review_id,
            package_id=package_id,
            target_document_id=document_id,
            expected_review_revision=1,
            decision_code="ACCEPTED",
        ),
        now=NOW,
    )
    with pytest.raises(CommandExecutionError, match="REVIEW_STATE_INVALID"):
        review.execute(
            actor=patron,
            command=DecidePreparationReviewCommand(
                command_id=uuid4(),
                idempotency_key=uuid4(),
                correlation_id=uuid4(),
                review_id=review_id,
                package_id=package_id,
                target_document_id=document_id,
                expected_review_revision=2,
                decision_code="REJECTED",
            ),
            now=NOW,
        )


@pytest.mark.db
@pytest.mark.security
def test_correction_requires_returned_review_and_draft_rejects_invalid_inputs(
    services, session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, review = services
    actor, _, _, requirement_id, package_id, document_id = _prepare_document(
        services, session_factory
    )
    patron = _patron(actor)
    review_id = uuid4()
    request = RequestPreparationReviewCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=uuid4(),
        review_id=review_id,
        package_id=package_id,
        target_document_id=document_id,
        target_version=1,
        expected_package_revision=3,
    )
    review.execute(actor=actor, command=request, now=NOW)
    review.execute(
        actor=patron,
        command=DecidePreparationReviewCommand(
            command_id=uuid4(),
            idempotency_key=uuid4(),
            correlation_id=uuid4(),
            review_id=review_id,
            package_id=package_id,
            target_document_id=document_id,
            expected_review_revision=1,
            decision_code="ACCEPTED",
        ),
        now=NOW,
    )
    with pytest.raises(CommandExecutionError, match="CORRECTIONS_NOT_REQUESTED"):
        review.execute(
            actor=patron,
            command=AddPreparationCorrectionCommand(
                command_id=uuid4(),
                idempotency_key=uuid4(),
                correlation_id=uuid4(),
                review_id=review_id,
                package_id=package_id,
                target_document_id=document_id,
                correction_code="SOURCE_MISSING",
                instruction="Ajouter une source publique.",
            ),
            now=NOW,
        )
    with pytest.raises(CommandExecutionError, match="SECTION_CODE_INVALID"):
        review.execute(
            actor=actor,
            command=CreateTechnicalResponseDraftCommand(
                command_id=uuid4(),
                idempotency_key=uuid4(),
                correlation_id=uuid4(),
                draft_id=uuid4(),
                package_id=package_id,
                source_document_id=document_id,
                expected_package_revision=5,
                section_codes=["UNKNOWN"],
                source_refs=[requirement_id],
            ),
            now=NOW,
        )
    with pytest.raises(CommandExecutionError, match="SOURCE_DOCUMENT_NOT_FOUND"):
        review.execute(
            actor=actor,
            command=CreateTechnicalResponseDraftCommand(
                command_id=uuid4(),
                idempotency_key=uuid4(),
                correlation_id=uuid4(),
                draft_id=uuid4(),
                package_id=package_id,
                source_document_id=uuid4(),
                expected_package_revision=5,
                section_codes=["METHOD"],
                source_refs=[requirement_id],
            ),
            now=NOW,
        )
    monkeypatch.setattr(
        "app.modules.preparation.application.review.contains_forbidden_text",
        lambda content: True,
    )
    with pytest.raises(CommandExecutionError, match="FINANCIAL_DATA_FORBIDDEN"):
        review.execute(
            actor=actor,
            command=CreateTechnicalResponseDraftCommand(
                command_id=uuid4(),
                idempotency_key=uuid4(),
                correlation_id=uuid4(),
                draft_id=uuid4(),
                package_id=package_id,
                source_document_id=document_id,
                expected_package_revision=5,
                section_codes=["METHOD"],
                source_refs=[requirement_id],
            ),
            now=NOW,
        )


def test_review_handler_rejects_unknown_command_type() -> None:
    handler = PreparationReviewHandler(storage=SimpleNamespace())

    with pytest.raises(CommandExecutionError, match="unsupported preparation review command"):
        handler.execute(
            session=SimpleNamespace(),
            command=SimpleNamespace(command_type="UnknownReviewCommand"),
            context=CommandContext(
                tenant_id=uuid4(),
                actor_id=uuid4(),
                actor_kind=ActorKind.COLLABORATEUR.value,
                received_at=NOW,
            ),
        )
