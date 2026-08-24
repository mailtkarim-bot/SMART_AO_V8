from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.modules.case.application.commands import CreateCaseCommand
from app.modules.case.application.handlers import CreateCaseHandler
from app.platform.events.dispatcher import CommandContext

TENANT_ID = uuid4()
ACTOR_ID = uuid4()
NOW = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)


def _command(**overrides: object) -> CreateCaseCommand:
    values: dict[str, object] = {
        "command_id": uuid4(),
        "idempotency_key": uuid4(),
        "case_id": uuid4(),
        "title": "Réhabilitation d’un groupe scolaire",
        "object_description": "Travaux de rénovation énergétique et accessibilité.",
        "scope_kind": "SINGLE_LOT",
        "lot_numbers": ("01",),
        "origin_kind": "MANUAL",
        "origin_rationale": "Opportunité saisie par le patron.",
    }
    values.update(overrides)
    return CreateCaseCommand(**values)


def _context() -> CommandContext:
    return CommandContext(
        tenant_id=TENANT_ID,
        actor_id=ACTOR_ID,
        actor_kind="PATRON_ADMIN",
        received_at=NOW,
    )


@pytest.mark.application
def test_create_case_persists_tenant_bound_root_and_sparse_event() -> None:
    session = MagicMock()
    repository = MagicMock()
    repository.has_active_functional_identity.return_value = False

    command = _command()
    outcome = CreateCaseHandler(lambda _session: repository).execute(
        session=session,
        command=command,
        context=_context(),
    )

    repository.create.assert_called_once()
    record = repository.create.call_args.kwargs
    assert record["tenant_id"] == TENANT_ID
    assert record["aggregate_id"] == command.case_id
    assert record["aggregate_revision"] == 0
    assert record["scope_kind"] == "SINGLE_LOT"
    assert record["scope_json"]["lot_numbers"] == ["01"]
    assert len(record["scope_fingerprint"]) == 64
    assert len(record["functional_identity_hash"]) == 64
    assert outcome.result_code == "CASE_CREATED"
    assert outcome.aggregate_refs[0]["aggregate_type"] == "AFF"
    assert outcome.events[0].event_type == "CASE_CREATED"
    assert outcome.events[0].payload == {
        "case_id": str(record["aggregate_id"]),
        "tenant_id": str(TENANT_ID),
    }


@pytest.mark.application
def test_create_case_rejects_duplicate_active_functional_identity() -> None:
    session = MagicMock()
    repository = MagicMock()
    repository.has_active_functional_identity.return_value = True

    with pytest.raises(ValueError, match="DUPLICATE_FUNCTIONAL_IDENTITY"):
        CreateCaseHandler(lambda _session: repository).execute(
            session=session,
            command=_command(),
            context=_context(),
        )


@pytest.mark.application
def test_create_case_requires_consultation_for_non_manual_origin() -> None:
    with pytest.raises(ValueError, match="consultation reference"):
        CreateCaseHandler(lambda _session: MagicMock()).execute(
            session=MagicMock(),
            command=_command(origin_kind="OPPORTUNITY", origin_reference_id=uuid4()),
            context=_context(),
        )


def test_create_case_rejects_missing_or_stale_consultation_reference() -> None:
    consultation_id = uuid4()
    command = _command(
        origin_kind="OPPORTUNITY",
        origin_reference_id=uuid4(),
        consultation_id=consultation_id,
        consultation_revision=4,
    )
    repository = MagicMock()
    reader = MagicMock()
    reader.get_revision.return_value = None

    with pytest.raises(ValueError, match="CONSULTATION_REQUIRED_OR_STALE"):
        CreateCaseHandler(
            lambda _session: repository,
            lambda _session: reader,
        ).execute(session=MagicMock(), command=command, context=_context())

    reader.get_revision.return_value = 3
    with pytest.raises(ValueError, match="CONSULTATION_REQUIRED_OR_STALE"):
        CreateCaseHandler(
            lambda _session: repository,
            lambda _session: reader,
        ).execute(session=MagicMock(), command=command, context=_context())


def test_create_case_links_existing_consultation_revision() -> None:
    consultation_id = uuid4()
    command = _command(
        origin_kind="OPPORTUNITY",
        origin_reference_id=uuid4(),
        consultation_id=consultation_id,
        consultation_revision=4,
    )
    repository = MagicMock()
    repository.has_active_functional_identity.return_value = False
    reader = MagicMock()
    reader.get_revision.return_value = 4

    CreateCaseHandler(
        lambda _session: repository,
        lambda _session: reader,
    ).execute(session=MagicMock(), command=command, context=_context())

    reader.get_revision.assert_called_once_with(
        tenant_id=TENANT_ID,
        consultation_id=consultation_id,
    )
    record = repository.create.call_args.kwargs
    assert record["consultation_id"] == consultation_id
    assert record["consultation_scope_snapshot_json"]["kind"] == "SINGLE_LOT"
    assert record["consultation_rationale"] is None


def test_create_case_validates_origin_reference_consistency() -> None:
    with pytest.raises(ValueError, match="MANUAL_ORIGIN_MUST_NOT_HAVE_REFERENCE"):
        CreateCaseHandler(lambda _session: MagicMock()).execute(
            session=MagicMock(),
            command=_command(origin_reference_id=uuid4()),
            context=_context(),
        )

    with pytest.raises(ValueError, match="NON_MANUAL_ORIGIN_REQUIRES_REFERENCE"):
        CreateCaseHandler(lambda _session: MagicMock()).execute(
            session=MagicMock(),
            command=_command(origin_kind="IMPORT"),
            context=_context(),
        )
