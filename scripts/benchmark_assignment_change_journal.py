"""Measure append-only Assignment journal writes and recent-history reads on PostgreSQL."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

import sqlalchemy as sa
from app.modules.case.infrastructure.models.case import CaseRecord
from app.platform.persistence.models import TenantRecord
from app.platform.security.models import (
    CaseAssignmentChangeEventRecord,
    CaseAssignmentRecord,
    IdentityRecord,
    TenantMembershipRecord,
)

DATABASE_URL = os.getenv("SMART_AO_TEST_DATABASE_URL") or (
    "postgresql+psycopg://"
    + "smart_ao"
    + ":"
    + "smart_ao"
    + "@127.0.0.1:5432/smart_ao"
)
EVENT_COUNT = 1_000
READ_LIMIT = 100
NOW = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)


def measure(
    engine: sa.Engine,
    *,
    event_type: str = "ASSIGNMENT_SCOPE_AMENDED",
) -> dict[str, float | int | str]:
    if event_type not in {
        "ASSIGNMENT_SCOPE_AMENDED",
        "ASSIGNMENT_SUSPENDED",
        "ASSIGNMENT_REACTIVATED",
    }:
        raise ValueError("unsupported assignment journal benchmark event")
    is_suspension = event_type == "ASSIGNMENT_SUSPENDED"
    is_reactivation = event_type == "ASSIGNMENT_REACTIVATED"
    tenant_id = uuid4()
    patron_identity_id = uuid4()
    patron_membership_id = uuid4()
    collaborator_identity_id = uuid4()
    collaborator_membership_id = uuid4()
    case_id = uuid4()
    assignment_id = uuid4()
    with engine.begin() as connection:
            connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))
            connection.execute(
                sa.insert(TenantRecord).values(
                    id=tenant_id,
                    slug=f"benchmark-{tenant_id.hex[:12]}",
                    lifecycle="ACTIVE",
                )
            )
            connection.execute(
                sa.insert(IdentityRecord),
                [
                    {
                        "id": patron_identity_id,
                        "email_normalized": f"patron-{patron_identity_id.hex[:12]}@example.test",
                        "lifecycle": "ACTIVE",
                        "email_verified_at": NOW,
                    },
                    {
                        "id": collaborator_identity_id,
                        "email_normalized": (
                            f"collab-{collaborator_identity_id.hex[:12]}@example.test"
                        ),
                        "lifecycle": "ACTIVE",
                        "email_verified_at": NOW,
                    },
                ],
            )
            connection.execute(
                sa.insert(TenantMembershipRecord),
                [
                    {
                        "id": patron_membership_id,
                        "tenant_id": tenant_id,
                        "identity_id": patron_identity_id,
                        "role": "PATRON_ADMIN",
                        "state": "ACTIVE",
                        "activated_at": NOW,
                        "revoked_at": None,
                    },
                    {
                        "id": collaborator_membership_id,
                        "tenant_id": tenant_id,
                        "identity_id": collaborator_identity_id,
                        "role": "COLLABORATEUR",
                        "state": "ACTIVE",
                        "activated_at": NOW,
                        "revoked_at": None,
                    },
                ],
            )
            connection.execute(
                sa.insert(CaseRecord).values(
                    id=case_id,
                    tenant_id=tenant_id,
                    aggregate_revision=1,
                    functional_identity_hash="a" * 64,
                    title="Affaire benchmark journal patron",
                    object_description=None,
                    business_origin="MANUAL",
                    origin_reference_id=None,
                    origin_rationale="Mesure locale du journal append-only",
                    consultation_id=None,
                    scope_kind="CUSTOM",
                    scope_json={},
                    scope_fingerprint="b" * 64,
                    applicable_dce_version_id=None,
                    lifecycle="ACTIVE",
                    commercial_stage="ANALYSIS",
                    decision_readiness="NOT_ASSESSED",
                    dce_freshness="NO_DCE",
                    responsibility_status="ASSIGNED",
                    stopped_reason=None,
                    stopped_at=None,
                    archived_reason=None,
                    archived_at=None,
                    created_by_actor_id=None,
                    updated_by_actor_id=None,
                )
            )
            connection.execute(
                sa.insert(CaseAssignmentRecord).values(
                    id=assignment_id,
                    tenant_id=tenant_id,
                    membership_id=collaborator_membership_id,
                    case_id=case_id,
                    aggregate_revision=EVENT_COUNT,
                    state="ACTIVE",
                    scope_actions_json=["case.dce.read"],
                    scope_classifications_json=["INTERNAL_OPERATIONAL"],
                    granted_by_membership_id=patron_membership_id,
                    granted_at=NOW,
                    starts_at=NOW,
                    ends_at=None,
                    ended_at=None,
                )
            )
            rows = [
                {
                    "id": uuid4(),
                    "tenant_id": tenant_id,
                    "assignment_id": assignment_id,
                    "case_id": case_id,
                    "target_membership_id": collaborator_membership_id,
                    "author_membership_id": patron_membership_id,
                    "event_type": event_type,
                    "previous_revision": revision - 1,
                    "resulting_revision": revision,
                    "previous_state": "SUSPENDED" if is_reactivation else "ACTIVE",
                    "resulting_state": "SUSPENDED" if is_suspension else "ACTIVE",
                    "reason_code": (
                        "CASE_PAUSED"
                        if is_suspension
                        else "CASE_RESUMED"
                        if is_reactivation
                        else None
                    ),
                    "previous_scope_actions_json": ["case.dce.read"],
                    "previous_scope_classifications_json": ["INTERNAL_OPERATIONAL"],
                    "resulting_scope_actions_json": (
                        ["case.dce.read"]
                        if is_suspension or is_reactivation
                        else ["preparation.transmit"]
                    ),
                    "resulting_scope_classifications_json": ["INTERNAL_OPERATIONAL"],
                    "command_id": uuid4(),
                    "correlation_id": uuid4(),
                }
                for revision in range(1, EVENT_COUNT + 1)
            ]
            insert_started = perf_counter()
            connection.execute(sa.insert(CaseAssignmentChangeEventRecord), rows)
            insert_elapsed_ms = (perf_counter() - insert_started) * 1_000

    with engine.connect() as connection:
        read_started = perf_counter()
        recent_rows = connection.execute(
            sa.select(CaseAssignmentChangeEventRecord.id)
            .where(
                CaseAssignmentChangeEventRecord.tenant_id == tenant_id,
                CaseAssignmentChangeEventRecord.assignment_id == assignment_id,
            )
            .order_by(CaseAssignmentChangeEventRecord.created_at.desc())
            .limit(READ_LIMIT)
        ).all()
        read_elapsed_ms = (perf_counter() - read_started) * 1_000

    return {
        "event_type": event_type,
        "event_count": EVENT_COUNT,
        "recent_read_limit": READ_LIMIT,
        "insert_elapsed_ms": round(insert_elapsed_ms, 3),
        "insert_rate_events_per_second": round(EVENT_COUNT / (insert_elapsed_ms / 1_000), 1),
        "recent_read_elapsed_ms": round(read_elapsed_ms, 3),
        "recent_read_rows": len(recent_rows),
    }


def main() -> None:
    engine = sa.create_engine(DATABASE_URL)
    try:
        print(json.dumps(measure(engine), sort_keys=True))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
