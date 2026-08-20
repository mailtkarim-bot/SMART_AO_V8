# ruff: noqa: F401, F811
from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from app.modules.dce.application.commands import RecordDceRequirementConfirmationCommand
from app.modules.dce.application.handlers import (
    RecordDceRequirementConfirmationHandler,
    RecordDceRequirementMaterializationRunHandler,
)
from app.modules.dce.application.requirements import DceRequirementsService
from app.modules.dce.infrastructure.models.dce_requirement_confirmations import (
    DceRequirementConfirmationCurrentRecord,
    DceRequirementConfirmationRecord,
)
from app.modules.dce.infrastructure.models.dce_requirements import DceRequirementRecord
from app.platform.events.dispatcher import CommandContext, CommandDispatcher, CommandExecutionError

sys.path.append(str(Path(__file__).parent))

from test_dce_rc_analysis import (  # noqa: E402
    NOW,
    _extract_then_analyze,
    _seed_admitted_document,
    isolate_rc_analysis_records,
)


@pytest.mark.db
@pytest.mark.integration
def test_requirement_confirmation_is_historical_and_system_is_refused(
    session_factory, tmp_path: Path
) -> None:
    from app.modules.dce.infrastructure.quarantine import LocalQuarantineStorageAdapter

    storage = LocalQuarantineStorageAdapter(root=tmp_path)
    tenant_id, document_id, dce_version_id = _seed_admitted_document(
        session_factory, storage=storage, source_bytes=b"Le DC1 est obligatoire."
    )
    analysis = _extract_then_analyze(
        session_factory=session_factory,
        storage=storage,
        tenant_id=tenant_id,
        document_id=document_id,
        dce_version_id=dce_version_id,
    )
    materializer = DceRequirementsService(
        session_factory=session_factory,
        dispatcher=CommandDispatcher(
            session_factory=session_factory,
            handlers={
                "RecordDceRequirementMaterializationRun": (
                    RecordDceRequirementMaterializationRunHandler()
                )
            },
        ),
    )
    materializer.materialize(
        tenant_id=tenant_id,
        dce_version_id=dce_version_id,
        dce_rc_analysis_id=UUID(analysis.aggregate_refs[0]["aggregate_id"]),
        now=NOW,
    )
    with session_factory() as session:
        requirement = session.scalar(sa.select(DceRequirementRecord))
    assert requirement is not None
    dispatcher = CommandDispatcher(
        session_factory=session_factory,
        handlers={"RecordDceRequirementConfirmation": RecordDceRequirementConfirmationHandler()},
    )
    command = RecordDceRequirementConfirmationCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=dce_version_id,
        confirmation_id=uuid4(),
        requirement_id=requirement.id,
        expected_confirmation_revision=0,
        outcome="CONFIRMED",
        reason_code="SOURCE_REVIEWED",
    )
    with pytest.raises(CommandExecutionError) as missing_failure:
        dispatcher.dispatch(
            command=command.model_copy(
                update={
                    "command_id": uuid4(),
                    "idempotency_key": uuid4(),
                    "confirmation_id": uuid4(),
                    "requirement_id": uuid4(),
                }
            ),
            context=CommandContext(
                tenant_id=tenant_id, actor_id=uuid4(), actor_kind="PATRON_ADMIN", received_at=NOW
            ),
        )
    assert str(missing_failure.value.__cause__) == "NOT_FOUND_OR_FORBIDDEN"

    result = dispatcher.dispatch(
        command=command,
        context=CommandContext(
            tenant_id=tenant_id, actor_id=uuid4(), actor_kind="PATRON_ADMIN", received_at=NOW
        ),
    )
    assert result.result_code == "DCE_REQUIREMENT_CONFIRMED"
    with session_factory() as session:
        current = session.get(DceRequirementConfirmationCurrentRecord, requirement.id)
        confirmation = session.get(DceRequirementConfirmationRecord, command.confirmation_id)
    assert current is not None and current.revision == 1
    assert confirmation is not None and confirmation.outcome == "CONFIRMED"

    with pytest.raises(CommandExecutionError) as stale_failure:
        dispatcher.dispatch(
            command=command.model_copy(
                update={
                    "command_id": uuid4(),
                    "idempotency_key": uuid4(),
                    "confirmation_id": uuid4(),
                }
            ),
            context=CommandContext(
                tenant_id=tenant_id,
                actor_id=uuid4(),
                actor_kind="PATRON_ADMIN",
                received_at=NOW,
            ),
        )
    assert str(stale_failure.value.__cause__) == "DCE_REQUIREMENT_CONFIRMATION_STALE"

    collaborator_command = command.model_copy(
        update={
            "command_id": uuid4(),
            "idempotency_key": uuid4(),
            "confirmation_id": uuid4(),
            "expected_confirmation_revision": 1,
            "outcome": "NOT_APPLICABLE",
        }
    )
    with pytest.raises(CommandExecutionError) as patron_failure:
        dispatcher.dispatch(
            command=collaborator_command,
            context=CommandContext(
                tenant_id=tenant_id, actor_id=uuid4(), actor_kind="COLLABORATEUR", received_at=NOW
            ),
        )
    assert str(patron_failure.value.__cause__) == "DCE_REQUIREMENT_PATRON_REQUIRED"

    second = dispatcher.dispatch(
        command=collaborator_command,
        context=CommandContext(
            tenant_id=tenant_id, actor_id=uuid4(), actor_kind="PATRON_ADMIN", received_at=NOW
        ),
    )
    assert second.result_code == "DCE_REQUIREMENT_CONFIRMED"
    with pytest.raises(sa.exc.DBAPIError), session_factory.begin() as session:
        confirmation = session.get(DceRequirementConfirmationRecord, command.confirmation_id)
        assert confirmation is not None
        confirmation.outcome = "REVIEW_REQUIRED"
    system_command = command.model_copy(
        update={"command_id": uuid4(), "idempotency_key": uuid4(), "confirmation_id": uuid4()}
    )
    with pytest.raises(CommandExecutionError):
        dispatcher.dispatch(
            command=system_command,
            context=CommandContext(
                tenant_id=tenant_id, actor_id=uuid4(), actor_kind="SYSTEM", received_at=NOW
            ),
        )
