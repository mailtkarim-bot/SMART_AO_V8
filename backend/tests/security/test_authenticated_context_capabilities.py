from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import sqlalchemy as sa
from app.modules.case.infrastructure.models.case import CaseRecord
from app.platform.persistence.models import TenantRecord
from app.platform.security.authenticated_context import (
    AuthenticationContextResolver,
    UnauthenticatedError,
)
from app.platform.security.capabilities import Capability
from app.platform.security.models import (
    AuthSessionRecord,
    CaseAssignmentRecord,
    IdentityRecord,
    TenantMembershipRecord,
)
from app.platform.security.tokens import JwtAccessTokenCodec
from sqlalchemy.orm import Session, sessionmaker

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW






@pytest.fixture(autouse=True)
def isolate_context_records(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


def _resolver(
    session_factory: sessionmaker[Session],
) -> tuple[AuthenticationContextResolver, JwtAccessTokenCodec]:
    access_tokens = JwtAccessTokenCodec(
        signing_key="test-only-signing-key-at-least-32-bytes",
        issuer="smart-ao-test",
        audience="smart-ao-web",
        clock=FixedClock(),
    )
    return (
        AuthenticationContextResolver(
            session_factory=session_factory,
            access_tokens=access_tokens,
            clock=FixedClock(),
        ),
        access_tokens,
    )


def _seed_collaborator_assignment(database_engine: sa.Engine) -> tuple:
    tenant_id = uuid4()
    identity_id = uuid4()
    membership_id = uuid4()
    case_id = uuid4()
    session_id = uuid4()
    with Session(database_engine) as session:
        session.add(
            TenantRecord(
                id=tenant_id,
                slug=f"tenant-{tenant_id.hex[:12]}",
                lifecycle="ACTIVE",
            )
        )
        session.add(
            IdentityRecord(
                id=identity_id,
                email_normalized=f"collaborateur-{identity_id}@example.test",
                lifecycle="ACTIVE",
                email_verified_at=NOW,
            )
        )
        session.flush()
        session.add(
            TenantMembershipRecord(
                id=membership_id,
                tenant_id=tenant_id,
                identity_id=identity_id,
                role="COLLABORATEUR",
                state="ACTIVE",
                activated_at=NOW,
                revoked_at=None,
            )
        )
        session.flush()
        session.add(
            CaseRecord(
                id=case_id,
                tenant_id=tenant_id,
                aggregate_revision=1,
                functional_identity_hash="a" * 64,
                title="Affaire collaborateur",
                object_description=None,
                business_origin="MANUAL",
                origin_reference_id=None,
                origin_rationale="Test de sécurité",
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
        session.flush()
        session.add(
            CaseAssignmentRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                membership_id=membership_id,
                case_id=case_id,
                state="ACTIVE",
                scope_actions_json=["dce.prepare", "consultation.read", "forged.action"],
                scope_classifications_json=["PUBLIC_TENDER", "INTERNAL_OPERATIONAL", "INVALID"],
                granted_by_membership_id=membership_id,
                granted_at=NOW,
                starts_at=NOW - timedelta(minutes=1),
                ends_at=None,
                ended_at=None,
            )
        )
        session.add(
            AuthSessionRecord(
                id=session_id,
                tenant_id=tenant_id,
                membership_id=membership_id,
                identity_id=identity_id,
                state="ACTIVE",
                auth_strength="PASSWORD",
                token_version=1,
                issued_at=NOW,
                last_seen_at=NOW,
                expires_at=NOW + timedelta(hours=8),
                absolute_expires_at=NOW + timedelta(hours=24),
                mfa_verified_at=None,
                revoked_at=None,
                revoke_reason=None,
            )
        )
        session.commit()
    return tenant_id, identity_id, membership_id, case_id, session_id


@pytest.mark.db
@pytest.mark.security
def test_context_resolver_derives_collaborator_capabilities_and_case_scope_from_database(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    _, identity_id, membership_id, case_id, session_id = _seed_collaborator_assignment(
        database_engine
    )
    resolver, access_tokens = _resolver(session_factory)

    context = resolver.resolve(
        access_token=access_tokens.issue(
            identity_id=identity_id,
            session_id=session_id,
            token_version=1,
        )
    )

    assert context.membership_id == membership_id
    assert Capability.DCE_PREPARE in context.capabilities
    assert Capability.PRICING_READ not in context.capabilities
    assert context.assigned_case_ids == frozenset({case_id})
    assert len(context.assignment_scopes) == 1
    scope = context.assignment_scopes[0]
    assert scope.case_id == case_id
    assert scope.allowed_actions == frozenset(
        {Capability.DCE_PREPARE, Capability.CONSULTATION_READ}
    )
    assert len(scope.allowed_classifications) == 2


@pytest.mark.db
@pytest.mark.security
def test_context_resolver_excludes_assignment_when_its_end_date_has_elapsed(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    _, identity_id, membership_id, case_id, session_id = _seed_collaborator_assignment(
        database_engine
    )
    with Session(database_engine) as session:
        assignment = session.scalar(
            sa.select(CaseAssignmentRecord).where(
                CaseAssignmentRecord.membership_id == membership_id,
                CaseAssignmentRecord.case_id == case_id,
            )
        )
        assert assignment is not None
        assignment.ends_at = NOW
        session.commit()
    resolver, access_tokens = _resolver(session_factory)

    context = resolver.resolve(
        access_token=access_tokens.issue(
            identity_id=identity_id,
            session_id=session_id,
            token_version=1,
        )
    )

    assert context.assignment_scopes == ()
    assert context.assigned_case_ids == frozenset()


@pytest.mark.db
@pytest.mark.security
def test_context_resolver_rejects_missing_and_expired_sessions(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    _, identity_id, _, _, session_id = _seed_collaborator_assignment(database_engine)
    resolver, access_tokens = _resolver(session_factory)
    token = access_tokens.issue(
        identity_id=identity_id,
        session_id=session_id,
        token_version=1,
    )

    with Session(database_engine) as session:
        auth_session = session.get(AuthSessionRecord, session_id)
        assert auth_session is not None
        auth_session.issued_at = NOW - timedelta(hours=1)
        auth_session.last_seen_at = NOW - timedelta(hours=1)
        auth_session.expires_at = NOW - timedelta(seconds=1)
        session.commit()
    with pytest.raises(UnauthenticatedError, match="UNAUTHENTICATED"):
        resolver.resolve(access_token=token)

    with pytest.raises(UnauthenticatedError, match="UNAUTHENTICATED"):
        resolver.resolve(
            access_token=access_tokens.issue(
                identity_id=identity_id,
                session_id=uuid4(),
                token_version=1,
            )
        )


@pytest.mark.db
@pytest.mark.security
def test_context_resolver_rejects_inactive_membership(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    _, identity_id, membership_id, _, session_id = _seed_collaborator_assignment(
        database_engine
    )
    with Session(database_engine) as session:
        membership = session.get(TenantMembershipRecord, membership_id)
        assert membership is not None
        membership.state = "SUSPENDED"
        session.commit()
    resolver, access_tokens = _resolver(session_factory)

    with pytest.raises(UnauthenticatedError, match="UNAUTHENTICATED"):
        resolver.resolve(
            access_token=access_tokens.issue(
                identity_id=identity_id,
                session_id=session_id,
                token_version=1,
            )
        )


@pytest.mark.db
@pytest.mark.security
def test_non_collaborator_context_has_no_assignment_scopes(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    _, identity_id, membership_id, _, session_id = _seed_collaborator_assignment(
        database_engine
    )
    with Session(database_engine) as session:
        membership = session.get(TenantMembershipRecord, membership_id)
        assert membership is not None
        membership.role = "PATRON_ADMIN"
        session.commit()
    resolver, access_tokens = _resolver(session_factory)

    context = resolver.resolve(
        access_token=access_tokens.issue(
            identity_id=identity_id,
            session_id=session_id,
            token_version=1,
        )
    )

    assert context.assignment_scopes == ()
    assert context.assigned_case_ids == frozenset()


class NaiveClock:
    def now(self) -> datetime:
        return NOW.replace(tzinfo=None)


@pytest.mark.db
@pytest.mark.security
def test_context_resolver_rejects_naive_clock(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    _, identity_id, _, _, session_id = _seed_collaborator_assignment(database_engine)
    _, access_tokens = _resolver(session_factory)
    resolver = AuthenticationContextResolver(
        session_factory=session_factory,
        access_tokens=access_tokens,
        clock=NaiveClock(),
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        resolver.resolve(
            access_token=access_tokens.issue(
                identity_id=identity_id,
                session_id=session_id,
                token_version=1,
            )
        )
