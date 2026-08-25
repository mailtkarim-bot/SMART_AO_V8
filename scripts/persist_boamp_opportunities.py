#!/usr/bin/env python3
"""Persist a validated BOAMP staging report in one tenant-scoped transaction."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_ROOT = _REPO_ROOT / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.modules.opportunity.application.boamp_ingestion import (  # noqa: E402
    OpportunityCandidate,
)
from app.modules.opportunity.application.boamp_scoring import (  # noqa: E402
    BoampOpportunityScoringService,
)
from app.modules.opportunity.domain.watch_profile import WatchProfileCriteria  # noqa: E402
from app.modules.opportunity.infrastructure.boamp_observation_repository import (  # noqa: E402
    BoampObservationPersistenceConflict,
    BoampObservationRepository,
    ingestion_request_hash,
)

_ALLOWED_CANDIDATE_FIELDS = {
    "department_codes",
    "fingerprint_sha256",
    "market_types",
    "publication_date",
    "response_deadline",
    "source",
    "source_notice_id",
    "source_status",
    "title",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Persist a bounded BOAMP staging report for one trusted tenant."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--tenant-id", type=UUID, required=True)
    parser.add_argument("--profile-id", type=UUID, required=True)
    parser.add_argument("--profile-version", type=int, required=True)
    parser.add_argument("--actor-id", type=UUID, required=True)
    parser.add_argument("--command-id", type=UUID, required=True)
    parser.add_argument("--idempotency-key", type=UUID, required=True)
    parser.add_argument("--correlation-id", type=UUID)
    parser.add_argument("--keyword", action="append", required=True)
    parser.add_argument("--included-department", action="append", default=[])
    parser.add_argument("--excluded-department", action="append", default=[])
    parser.add_argument("--database-url", default=os.environ.get("SMART_AO_DATABASE_URL"))
    parser.add_argument("--now", help="UTC ISO-8601 instant used for reproducible scoring.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if not args.database_url or args.database_url.startswith("REPLACE_WITH_"):
            raise ValueError("--database-url or SMART_AO_DATABASE_URL is required")
        now = _parse_now(args.now)
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        candidates = _read_candidates(payload)
        criteria = WatchProfileCriteria(
            keywords=tuple(args.keyword),
            included_departments=tuple(args.included_department),
            excluded_departments=tuple(args.excluded_department),
        )
        score_service = BoampOpportunityScoringService()
        scored = tuple(
            (candidate, score_service.score(candidate=candidate, criteria=criteria, now=now))
            for candidate in candidates
        )
        request_hash = ingestion_request_hash(
            profile_id=args.profile_id,
            profile_version=args.profile_version,
            pages_read=_read_int(payload, "pages_read"),
            truncated=_read_bool(payload, "truncated"),
            scored_candidates=scored,
        )
        engine = sa.create_engine(args.database_url, pool_pre_ping=True)
        try:
            sessions = sessionmaker(bind=engine, expire_on_commit=False)
            with sessions.begin() as session:
                result = BoampObservationRepository().persist(
                    session=session,
                    tenant_id=args.tenant_id,
                    actor_id=args.actor_id,
                    profile_id=args.profile_id,
                    profile_version=args.profile_version,
                    command_id=args.command_id,
                    idempotency_key=args.idempotency_key,
                    correlation_id=args.correlation_id,
                    request_hash=request_hash,
                    started_at=now,
                    completed_at=now,
                    pages_read=_read_int(payload, "pages_read"),
                    truncated=_read_bool(payload, "truncated"),
                    scored_candidates=scored,
                )
        finally:
            engine.dispose()
    except (
        OSError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
        BoampObservationPersistenceConflict,
        sa.exc.SQLAlchemyError,
    ) as error:
        print(f"BOAMP persistence refused: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "event": "BOAMP_INGESTION_PERSISTED",
                "event_id": str(result.event_id),
                "ingestion_run_id": str(result.run_id),
                "observation_ids": [str(item) for item in result.observation_ids],
                "replayed": result.replayed,
                "request_hash": request_hash,
            },
            sort_keys=True,
        )
    )
    return 0


def _parse_now(value: str | None) -> datetime:
    if value is None:
        return datetime.now(tz=UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("--now must include a timezone")
    return parsed.astimezone(UTC)


def _read_candidates(payload: object) -> tuple[OpportunityCandidate, ...]:
    if not isinstance(payload, dict) or payload.get("schema") != (
        "SMART_AO_OPPORTUNITY_INGESTION_REPORT_V1"
    ):
        raise ValueError("unsupported BOAMP staging report schema")
    raw_candidates = payload.get("candidates")
    if not isinstance(raw_candidates, list):
        raise TypeError("candidates must be a list")
    candidates: list[OpportunityCandidate] = []
    for raw in raw_candidates:
        if not isinstance(raw, dict):
            raise TypeError("candidate must be an object")
        if set(raw) != _ALLOWED_CANDIDATE_FIELDS:
            raise ValueError("candidate contains a field outside the persistence allowlist")
        candidate = OpportunityCandidate(
            source=_read_string(raw, "source"),
            source_notice_id=_read_string(raw, "source_notice_id"),
            title=_read_optional_string(raw, "title"),
            publication_date=_read_optional_date(raw, "publication_date"),
            response_deadline=_read_optional_datetime(raw, "response_deadline"),
            department_codes=_read_string_tuple(raw, "department_codes"),
            market_types=_read_string_tuple(raw, "market_types"),
            source_status=_read_optional_string(raw, "source_status"),
        )
        if candidate.source != "BOAMP" or raw["fingerprint_sha256"] != candidate.fingerprint():
            raise ValueError("candidate fingerprint or source is invalid")
        candidates.append(candidate)
    return tuple(candidates)


def _read_int(payload: object, field: str) -> int:
    if not isinstance(payload, dict) or not isinstance(payload.get(field), int):
        raise TypeError(f"{field} must be an integer")
    return payload[field]


def _read_bool(payload: object, field: str) -> bool:
    if not isinstance(payload, dict) or not isinstance(payload.get(field), bool):
        raise TypeError(f"{field} must be a boolean")
    return payload[field]


def _read_string(raw: dict[str, object], field: str) -> str:
    value = raw[field]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _read_optional_string(raw: dict[str, object], field: str) -> str | None:
    value = raw[field]
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string or null")
    return value


def _read_string_tuple(raw: dict[str, object], field: str) -> tuple[str, ...]:
    value = raw[field]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError(f"{field} must be a list of strings")
    return tuple(value)


def _read_optional_date(raw: dict[str, object], field: str) -> date | None:
    value = raw[field]
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field} must be an ISO date or null")
    return date.fromisoformat(value)


def _read_optional_datetime(raw: dict[str, object], field: str) -> datetime | None:
    value = raw[field]
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field} must be an ISO datetime or null")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed.astimezone(UTC)


if __name__ == "__main__":
    raise SystemExit(main())
