from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import sqlalchemy as sa
from app.modules.case.infrastructure.models.case import CaseRecord
from app.platform.persistence.models import TenantRecord
from app.platform.security.models import (
    CaseAssignmentRecord,
    IdentityRecord,
    TenantMembershipRecord,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)




@pytest.fixture(autouse=True)
def isolate_assignment_records(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


def _records() -> tuple[TenantRecord, IdentityRecord, TenantMembershipRecord, CaseRecord]:
    tenant_id = uuid4()
    identity_id = uuid4()
    membership_id = uuid4()
    case_id = uuid4()
    return (
        TenantRecord(id=tenant_id, slug=f"tenant-{tenant_id.hex[:12]}", lifecycle="ACTIVE"),
        IdentityRecord(
            id=identity_id,
            email_normalized=f"collaborateur-{identity_id}@example.test",
            lifecycle="ACTIVE",
            email_verified_at=NOW,
        ),
        TenantMembershipRecord(
            id=membership_id,
            tenant_id=tenant_id,
            identity_id=identity_id,
            role="COLLABORATEUR",
            state="ACTIVE",
            activated_at=NOW,
            revoked_at=None,
        ),
        CaseRecord(
            id=case_id,
            tenant_id=tenant_id,
            aggregate_revision=1,
            functional_identity_hash="a" * 64,
            title="Affaire test",
            object_description=None,
            business_origin="MANUAL",
            origin_reference_id=None,
            origin_rationale="Création de test",
            consultation_id=None,
            scope_kind="CUSTOM",
            scope_json={},
            scope_fingerprint="b" * 64,
            applicable_dce_version_id=None,
            lifecycle="ACTIVE",
            commercial_stage="ANALYSIS",
            decision_readiness="NOT_ASSESSED",
            dce_freshness="NO_DCE",
            responsibility_status="UNASSIGNED",
            stopped_reason=None,
            stopped_at=None,
            archived_reason=None,
            archived_at=None,
            created_by_actor_id=None,
            updated_by_actor_id=None,
        ),
    )


def _assignment(
    *,
    tenant_id,
    membership_id,
    case_id,
    state: str = "ACTIVE",
) -> CaseAssignmentRecord:
    return CaseAssignmentRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        membership_id=membership_id,
        case_id=case_id,
        state=state,
        scope_actions_json=["consultation.read", "dce.prepare"],
        scope_classifications_json=["PUBLIC_TENDER", "INTERNAL_OPERATIONAL"],
        granted_by_membership_id=membership_id,
        granted_at=NOW,
        starts_at=NOW,
        ends_at=None,
        ended_at=None,
    )


@pytest.mark.db
@pytest.mark.security
def test_case_assignment_persists_scoped_collaborator_access_with_composite_tenant_fks(
    database_engine: sa.Engine,
) -> None:
    tenant, identity, membership, case = _records()
    assignment = _assignment(
        tenant_id=tenant.id,
        membership_id=membership.id,
        case_id=case.id,
    )

    with Session(database_engine) as session:
        session.add_all([tenant, identity, membership])
        session.flush()
        session.add(case)
        session.flush()
        session.add(assignment)
        session.commit()
        stored = session.get(CaseAssignmentRecord, assignment.id)

    assert stored is not None
    assert stored.state == "ACTIVE"
    assert stored.scope_actions_json == ["consultation.read", "dce.prepare"]
    assert stored.scope_classifications_json == ["PUBLIC_TENDER", "INTERNAL_OPERATIONAL"]


@pytest.mark.db
@pytest.mark.security
def test_only_one_active_assignment_is_allowed_for_same_collaborator_and_case(
    database_engine: sa.Engine,
) -> None:
    tenant, identity, membership, case = _records()
    first = _assignment(tenant_id=tenant.id, membership_id=membership.id, case_id=case.id)
    second = _assignment(tenant_id=tenant.id, membership_id=membership.id, case_id=case.id)

    with Session(database_engine) as session:
        session.add_all([tenant, identity, membership])
        session.flush()
        session.add(case)
        session.flush()
        session.add(first)
        session.commit()
        session.add(second)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


@pytest.mark.db
@pytest.mark.security
def test_assignment_rejects_member_or_case_from_another_tenant(
    database_engine: sa.Engine,
) -> None:
    tenant_a, identity_a, membership_a, case_a = _records()
    tenant_b, identity_b, membership_b, case_b = _records()
    del membership_b, case_a
    invalid_assignment = _assignment(
        tenant_id=tenant_a.id,
        membership_id=membership_a.id,
        case_id=case_b.id,
    )

    with Session(database_engine) as session:
        session.add_all([tenant_a, identity_a, membership_a, tenant_b, identity_b])
        session.flush()
        session.add(case_b)
        session.flush()
        session.commit()
        session.add(invalid_assignment)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
