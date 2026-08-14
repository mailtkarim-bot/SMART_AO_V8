"""Security-audit vocabulary and append-only writing port for SEC-01."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy.orm import Session, sessionmaker

from app.platform.security.authorization import (
    AuthorizationDecision,
    AuthorizationPolicyPort,
    AuthorizationRequest,
)
from app.platform.security.context import ActorContext
from app.platform.security.models import SecurityAuditEventRecord


class AuditEventType(StrEnum):
    """Closed event types emitted by the authentication and authorization perimeter."""

    AUTH_LOGIN_SUCCEEDED = "AUTH_LOGIN_SUCCEEDED"
    AUTH_LOGIN_DENIED = "AUTH_LOGIN_DENIED"
    AUTH_REFRESH_SUCCEEDED = "AUTH_REFRESH_SUCCEEDED"
    AUTH_REFRESH_DENIED = "AUTH_REFRESH_DENIED"
    AUTH_LOGOUT_SUCCEEDED = "AUTH_LOGOUT_SUCCEEDED"
    AUTH_SESSION_REJECTED = "AUTH_SESSION_REJECTED"
    AUTHZ_SUCCEEDED = "AUTHZ_SUCCEEDED"
    AUTHZ_DENIED = "AUTHZ_DENIED"
    AUTHZ_STEP_UP_REQUIRED = "AUTHZ_STEP_UP_REQUIRED"


class AuditOutcome(StrEnum):
    """Allowed security audit outcomes."""

    SUCCEEDED = "SUCCEEDED"
    DENIED = "DENIED"
    FAILED = "FAILED"
    SUSPICIOUS = "SUSPICIOUS"


class AuditSeverity(StrEnum):
    """Bounded severity vocabulary suitable for security supervision."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class InvalidSecurityAuditEventError(ValueError):
    """Rejects an event that is not minimized enough for durable security audit."""


@dataclass(frozen=True, slots=True)
class SecurityAuditEntry:
    """Minimal, pseudonymous data allowed to reach the durable audit table."""

    occurred_at: datetime
    tenant_id: UUID | None
    actor_id: UUID | None
    identity_id: UUID | None
    session_id: UUID | None
    actor_kind: str | None
    auth_strength: str | None
    event_type: AuditEventType
    outcome: AuditOutcome
    severity: AuditSeverity
    action: str
    resource_type: str | None
    resource_id: UUID | None
    case_id: UUID | None
    correlation_id: UUID | None
    command_id: UUID | None
    request_id: UUID | None
    source_ip_hash: str | None
    user_agent_family: str | None
    reason_code: str | None
    metadata: dict[str, object]


class SecurityAuditWriter:
    """Validates and appends events inside a transaction owned by the caller."""

    _allowed_metadata_keys = frozenset({"channel", "http_method", "reason_class"})
    _action_pattern = re.compile(r"^[a-z][a-z0-9_.-]{2,119}$")
    _reason_pattern = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")

    def validate(self, entry: SecurityAuditEntry) -> None:
        """Reject details that could disclose credentials, business content or prices."""
        if entry.occurred_at.tzinfo is None:
            raise InvalidSecurityAuditEventError("occurred_at must be timezone-aware")
        if self._action_pattern.fullmatch(entry.action) is None:
            raise InvalidSecurityAuditEventError("action must use the closed audit vocabulary")
        if (
            entry.reason_code is not None
            and self._reason_pattern.fullmatch(entry.reason_code) is None
        ):
            raise InvalidSecurityAuditEventError("reason_code must be an allow-listed code")
        if (
            entry.source_ip_hash is not None
            and re.fullmatch(r"[a-f0-9]{64}", entry.source_ip_hash) is None
        ):
            raise InvalidSecurityAuditEventError(
                "source_ip_hash must be a SHA-256 hexadecimal digest"
            )
        if entry.user_agent_family is not None and len(entry.user_agent_family) > 120:
            raise InvalidSecurityAuditEventError("user_agent_family is too long")
        self._validate_metadata(entry.metadata)

    def record(self, *, session: Session, entry: SecurityAuditEntry) -> UUID:
        """Append one validated record without committing the caller transaction."""
        self.validate(entry)
        event_id = uuid4()
        session.add(
            SecurityAuditEventRecord(
                id=event_id,
                occurred_at=entry.occurred_at,
                schema_version=1,
                tenant_id=entry.tenant_id,
                actor_id=entry.actor_id,
                identity_id=entry.identity_id,
                session_id=entry.session_id,
                actor_kind=entry.actor_kind,
                auth_strength=entry.auth_strength,
                event_type=entry.event_type.value,
                outcome=entry.outcome.value,
                severity=entry.severity.value,
                action=entry.action,
                resource_type=entry.resource_type,
                resource_id=entry.resource_id,
                case_id=entry.case_id,
                correlation_id=entry.correlation_id,
                command_id=entry.command_id,
                request_id=entry.request_id,
                source_ip_hash=entry.source_ip_hash,
                user_agent_family=entry.user_agent_family,
                reason_code=entry.reason_code,
                metadata_json=dict(entry.metadata),
            )
        )
        return event_id

    def _validate_metadata(self, metadata: dict[str, object]) -> None:
        if set(metadata) - self._allowed_metadata_keys:
            raise InvalidSecurityAuditEventError("metadata contains a forbidden key")
        for key, value in metadata.items():
            if not isinstance(value, (str, bool, int)) or isinstance(value, float):
                raise InvalidSecurityAuditEventError(f"metadata {key} has a forbidden value type")
            if isinstance(value, str) and (not value or len(value) > 64):
                raise InvalidSecurityAuditEventError(f"metadata {key} is outside bounds")


@dataclass(frozen=True, slots=True)
class AuditedAuthorizationPolicy:
    """Decorates a policy port to append denial and step-up security audit events."""

    policy: AuthorizationPolicyPort
    session_factory: sessionmaker[Session]
    writer: SecurityAuditWriter

    def authorize(
        self,
        *,
        context: ActorContext,
        request: AuthorizationRequest,
    ) -> AuthorizationDecision:
        decision = self.policy.authorize(context=context, request=request)
        if decision.allowed:
            return decision
        event_type = (
            AuditEventType.AUTHZ_STEP_UP_REQUIRED
            if decision.code == "STEP_UP_REQUIRED"
            else AuditEventType.AUTHZ_DENIED
        )
        severity = (
            AuditSeverity.INFO
            if decision.code == "STEP_UP_REQUIRED"
            else AuditSeverity.WARNING
        )
        with self.session_factory.begin() as session:
            self.writer.record(
                session=session,
                entry=SecurityAuditEntry(
                    occurred_at=request.evaluated_at or context.authenticated_at,
                    tenant_id=context.tenant_id,
                    actor_id=context.actor_id,
                    identity_id=context.identity_id,
                    session_id=context.session_id,
                    actor_kind=context.actor_kind.value,
                    auth_strength=None,
                    event_type=event_type,
                    outcome=AuditOutcome.DENIED,
                    severity=severity,
                    action=request.action,
                    resource_type=request.resource.resource_type,
                    resource_id=request.resource.resource_id,
                    case_id=request.resource.case_id,
                    correlation_id=context.correlation_id,
                    command_id=None,
                    request_id=None,
                    source_ip_hash=None,
                    user_agent_family=None,
                    reason_code=decision.code,
                    metadata={"channel": "policy"},
                ),
            )
        return decision
