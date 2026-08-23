#!/usr/bin/env python3
"""Read and patronally qualify persisted BOAMP observations."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_ROOT = _REPO_ROOT / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.modules.opportunity.application.boamp_qualification import (  # noqa: E402
    BoampQualificationCommand,
    PatronBoampObservationService,
    QualificationDecision,
    QualificationReason,
)
from app.modules.opportunity.infrastructure.boamp_qualification_repository import (  # noqa: E402
    BoampQualificationPersistenceConflict,
    BoampQualificationRepository,
)
from app.platform.events.dispatcher import CommandContext  # noqa: E402
from app.platform.security.context import ActorKind  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read or qualify persisted BOAMP observations as a patron."
    )
    parser.add_argument("--database-url", default=os.environ.get("SMART_AO_DATABASE_URL"))
    parser.add_argument("--tenant-id", type=UUID, required=True)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--min-score", type=int, default=0)
    parser.add_argument("--observation-id", type=UUID)
    parser.add_argument("--actor-id", type=UUID, required=True)
    parser.add_argument("--decision", choices=[item.value for item in QualificationDecision])
    parser.add_argument("--reason-code", choices=[item.value for item in QualificationReason])
    parser.add_argument("--command-id", type=UUID)
    parser.add_argument("--idempotency-key", type=UUID)
    parser.add_argument("--correlation-id", type=UUID)
    parser.add_argument("--now", help="UTC ISO-8601 instant used for a deterministic audit time.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        database_url = args.database_url
        if not database_url or database_url.startswith("REPLACE_WITH_"):
            raise ValueError("--database-url or SMART_AO_DATABASE_URL is required")
        now = _parse_now(args.now)
        engine = sa.create_engine(database_url, pool_pre_ping=True)
        try:
            sessions = sessionmaker(bind=engine, expire_on_commit=False)
            service = PatronBoampObservationService(
                repository=BoampQualificationRepository()
            )
            if args.decision is None:
                if any(
                    value is not None
                    for value in (
                        args.observation_id,
                        args.reason_code,
                        args.command_id,
                        args.idempotency_key,
                    )
                ):
                    raise ValueError("qualification arguments require --decision")
                with sessions() as session:
                    observations = service.read(
                        session=session,
                        tenant_id=args.tenant_id,
                        actor_id=args.actor_id,
                        actor_kind=ActorKind.PATRON_ADMIN.value,
                        limit=args.limit,
                        min_score=args.min_score,
                    )
                _print_read_projection(observations)
                return 0
            _require_qualification_args(args)
            command = BoampQualificationCommand(
                observation_id=args.observation_id,
                decision=QualificationDecision(args.decision),
                reason_code=QualificationReason(args.reason_code),
                command_id=args.command_id,
                idempotency_key=args.idempotency_key,
                correlation_id=args.correlation_id,
            )
            context = CommandContext(
                tenant_id=args.tenant_id,
                actor_id=args.actor_id,
                actor_kind=ActorKind.PATRON_ADMIN.value,
                received_at=now,
            )
            with sessions.begin() as session:
                result = service.qualify(
                    session=session,
                    context=context,
                    command=command,
                    now=now,
                )
        finally:
            engine.dispose()
    except (
        OSError,
        TypeError,
        ValueError,
        PermissionError,
        BoampQualificationPersistenceConflict,
        sa.exc.SQLAlchemyError,
    ) as error:
        print(f"BOAMP patron operation refused: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "event": "BOAMP_OPPORTUNITY_QUALIFICATION_RECORDED",
                "event_id": str(result.event_id),
                "qualification_id": str(result.qualification_id),
                "replayed": result.replayed,
            },
            sort_keys=True,
        )
    )
    return 0


def _require_qualification_args(args: argparse.Namespace) -> None:
    if any(
        value is None
        for value in (
            args.observation_id,
            args.actor_id,
            args.reason_code,
            args.command_id,
            args.idempotency_key,
        )
    ):
        raise ValueError(
            "--observation-id, --actor-id, --reason-code, --command-id and "
            "--idempotency-key are required with --decision"
        )


def _parse_now(value: str | None) -> datetime:
    if value is None:
        return datetime.now(tz=UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("--now must include a timezone")
    return parsed.astimezone(UTC)


def _print_read_projection(observations: Sequence[object]) -> None:
    print(
        json.dumps(
            {
                "event": "BOAMP_OPPORTUNITIES_READ",
                "observations": [
                    {
                        "department_codes": list(item.department_codes),
                        "fingerprint_sha256": item.fingerprint_sha256,
                        "market_types": list(item.market_types),
                        "observation_id": str(item.observation_id),
                        "publication_date": item.publication_date,
                        "response_deadline": item.response_deadline,
                        "score": item.score,
                        "score_explanation": item.score_explanation,
                        "score_version": item.score_version,
                        "source_notice_id": item.source_notice_id,
                        "source_status": item.source_status,
                        "title": item.title,
                    }
                    for item in observations
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
