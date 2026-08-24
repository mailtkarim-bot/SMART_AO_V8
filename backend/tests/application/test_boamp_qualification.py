from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.modules.opportunity.application.boamp_qualification import (
    BoampQualificationCommand,
    PatronBoampObservationService,
    QualificationDecision,
    QualificationReason,
)
from app.modules.opportunity.infrastructure.boamp_qualification_repository import (
    QualificationPersistenceResult,
)
from app.platform.events.dispatcher import CommandContext
from app.platform.security.context import ActorKind

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)


class FakeRepository:
    def __init__(self, record: object) -> None:
        self.record = record
        self.calls: list[dict[str, object]] = []

    def list_observations(self, *, session, tenant_id, limit, min_score):
        self.calls.append(
            {"tenant_id": tenant_id, "limit": limit, "min_score": min_score}
        )
        return (self.record,)

    def persist_qualification(self, **kwargs):
        self.calls.append(kwargs)
        return QualificationPersistenceResult(
            qualification_id=uuid4(), event_id=uuid4(), replayed=False
        )


class FakeSession:
    def __init__(self, *values: object) -> None:
        self.values = list(values)

    def scalar(self, _statement):
        return self.values.pop(0)


def _record():
    return SimpleNamespace(
        id=uuid4(),
        source_notice_id="A-1",
        title="Réhabilitation école",
        publication_date=NOW.date(),
        response_deadline=NOW,
        department_codes=["59"],
        market_types=["TRAVAUX"],
        source_status="EN_COURS",
        score_version="BOAMP_PUBLIC_V1",
        score=100,
        score_explanation_json={"score": 100},
        fingerprint_sha256="a" * 64,
    )


def test_patron_read_returns_closed_projection_and_tenant_scope() -> None:
    tenant_id = uuid4()
    repository = FakeRepository(_record())
    service = PatronBoampObservationService(repository=repository)

    result = service.read(
        session=FakeSession(uuid4()),
        tenant_id=tenant_id,
        actor_id=uuid4(),
        actor_kind=ActorKind.PATRON_ADMIN.value,
        limit=10,
        min_score=80,
    )

    assert result[0].observation_id == repository.record.id
    assert result[0].score == 100
    assert not hasattr(result[0], "tenant_id")
    assert repository.calls == [{"tenant_id": tenant_id, "limit": 10, "min_score": 80}]


def test_qualification_requires_patron_and_compatible_closed_reason() -> None:
    with pytest.raises(ValueError, match="incompatible"):
        BoampQualificationCommand(
            observation_id=uuid4(),
            decision=QualificationDecision.QUALIFIED,
            reason_code=QualificationReason.NOT_RELEVANT,
            command_id=uuid4(),
            idempotency_key=uuid4(),
        ).validate()

    repository = FakeRepository(_record())
    service = PatronBoampObservationService(repository=repository)
    context = CommandContext(
        tenant_id=uuid4(),
        actor_id=uuid4(),
        actor_kind=ActorKind.PATRON_ADMIN.value,
        received_at=NOW,
    )
    command = BoampQualificationCommand(
        observation_id=repository.record.id,
        decision=QualificationDecision.QUALIFIED,
        reason_code=QualificationReason.RELEVANT_PUBLIC_SIGNAL,
        command_id=uuid4(),
        idempotency_key=uuid4(),
    )

    result = service.qualify(
        session=FakeSession(uuid4(), repository.record),
        context=context,
        command=command,
        now=NOW,
    )

    assert result.replayed is False
    assert repository.calls[-1]["tenant_id"] == context.tenant_id


def test_qualification_rejects_collaborator_before_database_access() -> None:
    repository = FakeRepository(_record())
    service = PatronBoampObservationService(repository=repository)
    context = CommandContext(
        tenant_id=uuid4(),
        actor_id=uuid4(),
        actor_kind=ActorKind.COLLABORATEUR.value,
        received_at=NOW,
    )

    with pytest.raises(PermissionError, match="PATRON_REQUIRED"):
        service.qualify(
            session=FakeSession(),
            context=context,
            command=BoampQualificationCommand(
                observation_id=repository.record.id,
                decision=QualificationDecision.QUALIFIED,
                reason_code=QualificationReason.RELEVANT_PUBLIC_SIGNAL,
                command_id=uuid4(),
                idempotency_key=uuid4(),
            ),
            now=NOW,
        )
