from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import sqlalchemy as sa
from app.platform.persistence.models import TenantRecord
from app.platform.security.audit import (
    AuditEventType,
    AuditOutcome,
    AuditSeverity,
    InvalidSecurityAuditEventError,
    SecurityAuditEntry,
    SecurityAuditWriter,
)
from app.platform.security.models import SecurityAuditEventRecord
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)






@pytest.fixture(autouse=True)
def isolate_audit_records(database_engine: sa.Engine) -> None:
    with database_engine.begin() as connection:
        connection.execute(sa.text("TRUNCATE TABLE tenants, identities CASCADE"))


def _entry(*, tenant_id=None, metadata: dict[str, object] | None = None) -> SecurityAuditEntry:
    return SecurityAuditEntry(
        occurred_at=NOW,
        tenant_id=tenant_id,
        actor_id=None,
        identity_id=None,
        session_id=None,
        actor_kind=None,
        auth_strength=None,
        event_type=AuditEventType.AUTH_LOGIN_DENIED,
        outcome=AuditOutcome.DENIED,
        severity=AuditSeverity.WARNING,
        action="auth.login",
        resource_type="AUTHENTICATION",
        resource_id=None,
        case_id=None,
        correlation_id=uuid4(),
        command_id=None,
        request_id=uuid4(),
        source_ip_hash="a" * 64,
        user_agent_family="browser",
        reason_code="INVALID_CREDENTIALS",
        metadata=metadata or {"channel": "web"},
    )


@pytest.mark.db
@pytest.mark.security
def test_writer_persists_allowlisted_authentication_event_with_pseudonymous_references(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    tenant_id = uuid4()
    with Session(database_engine) as session:
        session.add(TenantRecord(id=tenant_id, slug="tenant-audit", lifecycle="ACTIVE"))
        session.commit()

    writer = SecurityAuditWriter()
    with session_factory.begin() as session:
        event_id = writer.record(session=session, entry=_entry(tenant_id=tenant_id))

    with Session(database_engine) as session:
        stored = session.get(SecurityAuditEventRecord, event_id)

    assert stored is not None
    assert stored.tenant_id == tenant_id
    assert stored.event_type == "AUTH_LOGIN_DENIED"
    assert stored.outcome == "DENIED"
    assert stored.metadata_json == {"channel": "web"}
    assert stored.source_ip_hash == "a" * 64


@pytest.mark.db
@pytest.mark.security
def test_security_audit_event_rejects_unknown_vocabulary_at_database_boundary(
    database_engine: sa.Engine,
) -> None:
    with Session(database_engine) as session:
        session.add(
            SecurityAuditEventRecord(
                id=uuid4(),
                occurred_at=NOW,
                schema_version=1,
                tenant_id=None,
                actor_id=None,
                identity_id=None,
                session_id=None,
                actor_kind=None,
                auth_strength=None,
                event_type="UNAPPROVED_EVENT",
                outcome="DENIED",
                severity="WARNING",
                action="auth.login",
                resource_type="AUTHENTICATION",
                resource_id=None,
                case_id=None,
                correlation_id=None,
                command_id=None,
                request_id=None,
                source_ip_hash=None,
                user_agent_family=None,
                reason_code="INVALID_CREDENTIALS",
                metadata_json={"channel": "web"},
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


@pytest.mark.db
@pytest.mark.security
def test_security_audit_event_is_append_only_against_update_and_delete(
    database_engine: sa.Engine,
    session_factory: sessionmaker[Session],
) -> None:
    writer = SecurityAuditWriter()
    with session_factory.begin() as session:
        event_id = writer.record(session=session, entry=_entry())

    with database_engine.connect() as connection:
        with pytest.raises(sa.exc.DBAPIError, match="SECURITY_AUDIT_APPEND_ONLY"):
            connection.execute(
                sa.text(
                    "UPDATE security_audit_events SET reason_code = 'CHANGED' WHERE id = :event_id"
                ),
                {"event_id": event_id},
            )
        connection.rollback()
    with database_engine.connect() as connection:
        with pytest.raises(sa.exc.DBAPIError, match="SECURITY_AUDIT_APPEND_ONLY"):
            connection.execute(
                sa.text("DELETE FROM security_audit_events WHERE id = :event_id"),
                {"event_id": event_id},
            )
        connection.rollback()


@pytest.mark.security
def test_writer_refuses_secret_and_financial_metadata_before_persistence() -> None:
    writer = SecurityAuditWriter()

    with pytest.raises(InvalidSecurityAuditEventError):
        writer.validate(_entry(metadata={"password": "not-allowed"}))
    with pytest.raises(InvalidSecurityAuditEventError):
        writer.validate(_entry(metadata={"amount": 4200}))
    with pytest.raises(InvalidSecurityAuditEventError):
        writer.validate(_entry(metadata={"channel": "web", "token": "not-allowed"}))
