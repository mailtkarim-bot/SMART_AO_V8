from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import sqlalchemy as sa
from app.platform.persistence.models import TenantRecord
from app.platform.security.audit import (
    AuditedAuthorizationPolicy,
    AuditEventType,
    SecurityAuditWriter,
)
from app.platform.security.authentication import (
    AuditedAuthenticationService,
    AuthenticationService,
)
from app.platform.security.authorization import (
    AuthorizationPolicy,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.context import (
    ActorContext,
    ActorKind,
    DataClassification,
    MembershipState,
)
from app.platform.security.models import (
    IdentityRecord,
    PasswordCredentialRecord,
    SecurityAuditEventRecord,
    TenantMembershipRecord,
)
from sqlalchemy.orm import Session, sessionmaker

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


class StubPasswordVerifier:
    def verify(self, *, password_hash: str, password: str) -> bool:
        return password_hash == "$argon2id$fixture" and password == "Correct#Pass123"


class SequenceTokenGenerator:
    def __init__(self, *values: str) -> None:
        self._values = deque(values)

    def generate(self) -> str:
        return self._values.popleft()






@pytest.fixture(autouse=True)
def isolate_audit_integration_records(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


def _seed_active_membership(engine: sa.Engine) -> tuple:
    tenant_id = uuid4()
    identity_id = uuid4()
    membership_id = uuid4()
    email = f"patron-{identity_id}@example.test"
    with Session(engine) as session:
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
                email_normalized=email,
                lifecycle="ACTIVE",
                email_verified_at=NOW,
            )
        )
        session.flush()
        session.add(
            PasswordCredentialRecord(
                id=uuid4(),
                identity_id=identity_id,
                password_hash="$argon2id$fixture",
                algorithm="ARGON2ID",
                parameters_version=1,
                changed_at=NOW,
                must_change=False,
            )
        )
        session.add(
            TenantMembershipRecord(
                id=membership_id,
                tenant_id=tenant_id,
                identity_id=identity_id,
                role="PATRON_ADMIN",
                state="ACTIVE",
                activated_at=NOW,
                revoked_at=None,
            )
        )
        session.commit()
    return tenant_id, identity_id, membership_id, email


def _service(session_factory: sessionmaker[Session]) -> AuditedAuthenticationService:
    core = AuthenticationService(
        session_factory=session_factory,
        password_verifier=StubPasswordVerifier(),
        token_generator=SequenceTokenGenerator("refresh-1", "refresh-2"),
        clock=FixedClock(),
    )
    return AuditedAuthenticationService(
        core=core,
        session_factory=session_factory,
        writer=SecurityAuditWriter(),
        clock=FixedClock(),
    )


@pytest.mark.db
@pytest.mark.security
def test_login_success_and_logout_append_minimized_security_events(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, _, email = _seed_active_membership(database_engine)
    service = _service(session_factory)

    login = service.login(email=email, password="Correct#Pass123", tenant_id=tenant_id)
    assert service.logout(session_id=login.session_id) is True

    with Session(database_engine) as session:
        events = list(
            session.scalars(
                sa.select(SecurityAuditEventRecord)
                .order_by(SecurityAuditEventRecord.occurred_at, SecurityAuditEventRecord.id)
            )
        )

    assert {event.event_type for event in events} == {
        AuditEventType.AUTH_LOGIN_SUCCEEDED,
        AuditEventType.AUTH_LOGOUT_SUCCEEDED,
    }
    login_event = next(
        event for event in events if event.event_type == AuditEventType.AUTH_LOGIN_SUCCEEDED
    )
    logout_event = next(
        event for event in events if event.event_type == AuditEventType.AUTH_LOGOUT_SUCCEEDED
    )
    assert login_event.tenant_id == tenant_id
    assert login_event.identity_id == identity_id
    assert login_event.session_id == login.session_id
    assert login_event.metadata_json == {"channel": "service"}
    assert logout_event.reason_code == "LOGOUT"


@pytest.mark.db
@pytest.mark.security
def test_login_failure_is_audited_without_persisting_the_attempted_email_or_password(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, _, _, _ = _seed_active_membership(database_engine)
    service = _service(session_factory)

    with pytest.raises(Exception, match="INVALID_CREDENTIALS"):
        service.login(
            email="unknown@example.test",
            password="Do-not-log-this-password",
            tenant_id=tenant_id,
        )

    with Session(database_engine) as session:
        event = session.scalar(sa.select(SecurityAuditEventRecord))

    assert event is not None
    assert event.event_type == AuditEventType.AUTH_LOGIN_DENIED
    assert event.tenant_id is None
    assert event.identity_id is None
    assert event.reason_code == "INVALID_CREDENTIALS"
    rendered = str(event.metadata_json)
    assert "unknown@example.test" not in rendered
    assert "Do-not-log-this-password" not in rendered


@pytest.mark.db
@pytest.mark.security
def test_audited_policy_records_authorization_denial_with_pseudonymous_resource_references(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id, identity_id, membership_id, _ = _seed_active_membership(database_engine)
    context = ActorContext(
        actor_id=identity_id,
        identity_id=identity_id,
        tenant_id=tenant_id,
        membership_id=membership_id,
        actor_kind=ActorKind.PATRON_ADMIN,
        membership_state=MembershipState.ACTIVE,
        capabilities=frozenset(),
        assigned_case_ids=frozenset(),
        session_id=uuid4(),
        authenticated_at=NOW,
        mfa_verified_at=None,
        correlation_id=uuid4(),
    )
    request = AuthorizationRequest(
        action="pricing.read",
        resource=AuthorizationResource(
            resource_type="PRICE",
            resource_id=uuid4(),
            tenant_id=tenant_id,
            classification=DataClassification.FINANCIAL_PRIVATE,
            case_id=uuid4(),
        ),
    )
    policy = AuditedAuthorizationPolicy(
        policy=AuthorizationPolicy(),
        session_factory=session_factory,
        writer=SecurityAuditWriter(),
    )

    decision = policy.authorize(context=context, request=request)

    assert decision.allowed is False
    with Session(database_engine) as session:
        event = session.scalar(sa.select(SecurityAuditEventRecord))
    assert event is not None
    assert event.event_type == AuditEventType.AUTHZ_DENIED
    assert event.tenant_id == tenant_id
    assert event.actor_id == identity_id
    assert event.resource_id == request.resource.resource_id
    assert event.case_id == request.resource.case_id
    assert event.reason_code == "AUTHORIZATION_DENIED"
