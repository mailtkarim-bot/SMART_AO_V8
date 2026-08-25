"""Transactional repository for auditable BOAMP observations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4, uuid5

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.opportunity.application.boamp_ingestion import OpportunityCandidate
from app.modules.opportunity.application.boamp_scoring import ExplainableOpportunityScore
from app.modules.opportunity.infrastructure.observation_models import (
    BoampIngestionObservationLinkRecord,
    BoampIngestionRunRecord,
    BoampOpportunityObservationRecord,
)
from app.platform.persistence.models import DomainEventRecord, OutboxMessageRecord


class BoampObservationPersistenceConflict(RuntimeError):
    """An idempotency key or command identifies incompatible ingestion data."""


@dataclass(frozen=True, slots=True)
class BoampPersistenceResult:
    run_id: UUID
    observation_ids: tuple[UUID, ...]
    event_id: UUID
    replayed: bool


class BoampObservationRepository:
    """Persist one complete ingestion atomically and isolate every lookup by tenant."""

    def persist(
        self,
        *,
        session: Session,
        tenant_id: UUID,
        actor_id: UUID,
        profile_id: UUID,
        profile_version: int,
        command_id: UUID,
        idempotency_key: UUID,
        correlation_id: UUID | None,
        request_hash: str,
        started_at: datetime,
        completed_at: datetime,
        pages_read: int,
        truncated: bool,
        scored_candidates: tuple[tuple[OpportunityCandidate, ExplainableOpportunityScore], ...],
    ) -> BoampPersistenceResult:
        run_id = uuid5(
            UUID("00000000-0000-0000-0000-000000000001"),
            f"boamp-ingestion:{tenant_id}:{idempotency_key}",
        )
        candidates = session.scalars(
            sa.select(BoampIngestionRunRecord).where(
                BoampIngestionRunRecord.tenant_id == tenant_id,
                sa.or_(
                    BoampIngestionRunRecord.id == run_id,
                    BoampIngestionRunRecord.command_id == command_id,
                    BoampIngestionRunRecord.idempotency_key == idempotency_key,
                ),
            )
        ).all()
        distinct_run_ids = {record.id for record in candidates}
        if len(distinct_run_ids) > 1:
            raise BoampObservationPersistenceConflict("ambiguous ingestion identity collision")
        if candidates:
            record = candidates[0]
            if (
                record.id != run_id
                or record.command_id != command_id
                or record.idempotency_key != idempotency_key
                or record.request_hash != request_hash
            ):
                raise BoampObservationPersistenceConflict("ingestion idempotency conflict")
            links = tuple(
                session.scalars(
                    sa.select(BoampIngestionObservationLinkRecord)
                    .where(
                        BoampIngestionObservationLinkRecord.tenant_id == tenant_id,
                        BoampIngestionObservationLinkRecord.ingestion_run_id == record.id,
                    )
                    .order_by(BoampIngestionObservationLinkRecord.observation_id)
                )
            )
            event = session.scalar(
                sa.select(DomainEventRecord).where(
                    DomainEventRecord.tenant_id == tenant_id,
                    DomainEventRecord.aggregate_id == record.id,
                    DomainEventRecord.event_type == "BoampIngestionRecorded",
                )
            )
            if event is None:
                raise BoampObservationPersistenceConflict("ingestion replay has no audit event")
            return BoampPersistenceResult(
                run_id=record.id,
                observation_ids=tuple(link.observation_id for link in links),
                event_id=event.id,
                replayed=True,
            )

        record = BoampIngestionRunRecord(
            id=run_id,
            tenant_id=tenant_id,
            profile_id=profile_id,
            profile_version=profile_version,
            actor_id=actor_id,
            command_id=command_id,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            request_hash=request_hash,
            status="RECORDED",
            pages_read=pages_read,
            candidate_count=len(scored_candidates),
            truncated=truncated,
            started_at=started_at,
            completed_at=completed_at,
        )
        session.add(record)
        session.flush()
        observation_ids: list[UUID] = []
        for candidate, score in scored_candidates:
            observation_id = uuid5(
                UUID("00000000-0000-0000-0000-000000000002"),
                f"boamp-observation:{tenant_id}:{candidate.source_notice_id}:{candidate.fingerprint()}",
            )
            statement = insert(BoampOpportunityObservationRecord).values(
                id=observation_id,
                tenant_id=tenant_id,
                source=candidate.source,
                source_notice_id=candidate.source_notice_id,
                fingerprint_sha256=candidate.fingerprint(),
                title=candidate.title,
                publication_date=candidate.publication_date,
                response_deadline=candidate.response_deadline,
                department_codes=list(candidate.department_codes),
                market_types=list(candidate.market_types),
                source_status=candidate.source_status,
                score_version=score.version,
                score=score.score,
                score_explanation_json=score.snapshot(),
                score_explanation_sha256=score.explanation_sha256,
                observed_at=completed_at,
            ).on_conflict_do_nothing(constraint="uq_boamp_observations_source_fingerprint")
            session.execute(statement)
            persisted = session.scalar(
                sa.select(BoampOpportunityObservationRecord.id).where(
                    BoampOpportunityObservationRecord.tenant_id == tenant_id,
                    BoampOpportunityObservationRecord.source == candidate.source,
                    BoampOpportunityObservationRecord.source_notice_id
                    == candidate.source_notice_id,
                    BoampOpportunityObservationRecord.fingerprint_sha256 == candidate.fingerprint(),
                )
            )
            if persisted is None:
                raise BoampObservationPersistenceConflict("observation insert was not readable")
            observation_ids.append(persisted)
            link_id = uuid5(
                UUID("00000000-0000-0000-0000-000000000003"),
                f"boamp-link:{tenant_id}:{run_id}:{persisted}",
            )
            session.execute(
                insert(BoampIngestionObservationLinkRecord)
                .values(
                    id=link_id,
                    tenant_id=tenant_id,
                    ingestion_run_id=run_id,
                    observation_id=persisted,
                )
                .on_conflict_do_nothing(constraint="uq_boamp_links_run_observation")
            )

        event_id = uuid4()
        session.add(
            DomainEventRecord(
                id=event_id,
                tenant_id=tenant_id,
                aggregate_type="BoampIngestionRun",
                aggregate_id=run_id,
                aggregate_revision=0,
                event_type="BoampIngestionRecorded",
                payload_version=1,
                payload_json={
                    "profile_id": str(profile_id),
                    "profile_version": profile_version,
                    "ingestion_run_id": str(run_id),
                    "observation_count": len(observation_ids),
                    "request_hash": request_hash,
                },
                actor_id=actor_id,
                command_id=command_id,
                correlation_id=correlation_id,
                causation_id=None,
                occurred_at=completed_at,
            )
        )
        session.flush()
        session.add(
            OutboxMessageRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                event_id=event_id,
                topic="opportunity.boamp.ingestion.recorded",
                payload_version=1,
                payload_json={
                    "ingestion_run_id": str(run_id),
                    "observation_count": len(observation_ids),
                    "request_hash": request_hash,
                },
                status="PENDING",
                attempt_count=0,
                next_attempt_at=None,
                published_at=None,
                last_error_code=None,
                dedupe_key=f"boamp-ingestion:{tenant_id}:{run_id}",
            )
        )
        return BoampPersistenceResult(
            run_id=run_id,
            observation_ids=tuple(observation_ids),
            event_id=event_id,
            replayed=False,
        )


def ingestion_request_hash(
    *,
    profile_id: UUID,
    profile_version: int,
    pages_read: int,
    truncated: bool,
    scored_candidates: tuple[tuple[OpportunityCandidate, ExplainableOpportunityScore], ...],
) -> str:
    payload = {
        "pages_read": pages_read,
        "profile_id": str(profile_id),
        "profile_version": profile_version,
        "truncated": truncated,
        "candidates": [
            {"candidate": candidate.snapshot(), "score": score.snapshot()}
            for candidate, score in scored_candidates
        ],
    }
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
