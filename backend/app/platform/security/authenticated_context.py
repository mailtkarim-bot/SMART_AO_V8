"""Server-side authentication context resolution from short-lived access tokens."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.platform.security.capabilities import Capability, capabilities_for
from app.platform.security.context import (
    ActorContext,
    ActorKind,
    AssignmentScope,
    DataClassification,
    MembershipState,
)
from app.platform.security.models import (
    AuthSessionRecord,
    CaseAssignmentRecord,
    IdentityRecord,
    TenantMembershipRecord,
)
from app.platform.security.tokens import AccessTokenRejectedError, JwtAccessTokenCodec

_SESSION_IDLE_TIMEOUT = timedelta(hours=8)


class Clock(Protocol):
    """Returns the current timezone-aware instant."""

    def now(self) -> datetime: ...


class UnauthenticatedError(Exception):
    """Neutral refusal for missing, malformed, stale or revoked authentication."""

    def __init__(self) -> None:
        super().__init__("UNAUTHENTICATED")


@dataclass(frozen=True, slots=True)
class AuthenticationContextResolver:
    """Resolves trusted actor facts from JWT claims and current server state."""

    session_factory: sessionmaker[Session]
    access_tokens: JwtAccessTokenCodec
    clock: Clock

    def resolve(self, *, access_token: str) -> ActorContext:
        """Verify JWT and authoritative session state before creating ActorContext."""
        try:
            claims = self.access_tokens.decode(access_token)
        except AccessTokenRejectedError as error:
            raise UnauthenticatedError() from error

        now = self._now()
        rejected = False
        resolved_context: ActorContext | None = None
        with self.session_factory.begin() as session:
            row = session.execute(
                sa.select(AuthSessionRecord, TenantMembershipRecord, IdentityRecord)
                .join(
                    TenantMembershipRecord,
                    sa.and_(
                        TenantMembershipRecord.id == AuthSessionRecord.membership_id,
                        TenantMembershipRecord.tenant_id == AuthSessionRecord.tenant_id,
                        TenantMembershipRecord.identity_id == AuthSessionRecord.identity_id,
                    ),
                )
                .join(IdentityRecord, IdentityRecord.id == AuthSessionRecord.identity_id)
                .where(
                    AuthSessionRecord.id == claims.session_id,
                    AuthSessionRecord.identity_id == claims.subject,
                    AuthSessionRecord.token_version == claims.token_version,
                )
                .with_for_update()
            ).one_or_none()
            if row is None:
                rejected = True
            else:
                auth_session, membership, identity = row
                is_active = (
                    auth_session.state == "ACTIVE"
                    and membership.state == "ACTIVE"
                    and identity.lifecycle == "ACTIVE"
                    and now < auth_session.expires_at
                    and now < auth_session.absolute_expires_at
                )
                if not is_active:
                    if auth_session.state == "ACTIVE" and now >= auth_session.expires_at:
                        auth_session.state = "EXPIRED"
                    rejected = True
                else:
                    auth_session.last_seen_at = now
                    auth_session.expires_at = min(
                        now + _SESSION_IDLE_TIMEOUT,
                        auth_session.absolute_expires_at,
                    )
                    try:
                        actor_kind = ActorKind(membership.role)
                    except ValueError:
                        rejected = True
                    else:
                        assignment_scopes = self._active_assignment_scopes(
                            session=session,
                            tenant_id=membership.tenant_id,
                            membership_id=membership.id,
                            actor_kind=actor_kind,
                            now=now,
                        )
                        resolved_context = ActorContext(
                            actor_id=identity.id,
                            identity_id=identity.id,
                            tenant_id=membership.tenant_id,
                            membership_id=membership.id,
                            actor_kind=actor_kind,
                            membership_state=MembershipState.ACTIVE,
                            capabilities=capabilities_for(actor_kind),
                            assigned_case_ids=frozenset(
                                scope.case_id for scope in assignment_scopes
                            ),
                            session_id=auth_session.id,
                            authenticated_at=auth_session.issued_at,
                            mfa_verified_at=auth_session.mfa_verified_at,
                            correlation_id=uuid4(),
                            assignment_scopes=assignment_scopes,
                        )

        if rejected or resolved_context is None:
            raise UnauthenticatedError()
        return resolved_context

    @staticmethod
    def _active_assignment_scopes(
        *,
        session: Session,
        tenant_id,
        membership_id,
        actor_kind: ActorKind,
        now: datetime,
    ) -> tuple[AssignmentScope, ...]:
        if actor_kind is not ActorKind.COLLABORATEUR:
            return ()
        records = session.scalars(
            sa.select(CaseAssignmentRecord).where(
                CaseAssignmentRecord.tenant_id == tenant_id,
                CaseAssignmentRecord.membership_id == membership_id,
                CaseAssignmentRecord.state == "ACTIVE",
                CaseAssignmentRecord.starts_at <= now,
                sa.or_(
                    CaseAssignmentRecord.ends_at.is_(None),
                    CaseAssignmentRecord.ends_at > now,
                ),
            )
        )
        scopes: list[AssignmentScope] = []
        for record in records:
            actions = frozenset(
                action
                for action in record.scope_actions_json
                if action in Capability._value2member_map_
            )
            classifications = frozenset(
                DataClassification(value)
                for value in record.scope_classifications_json
                if value in DataClassification._value2member_map_
            )
            if actions and classifications:
                scopes.append(
                    AssignmentScope(
                        case_id=record.case_id,
                        allowed_actions=actions,
                        allowed_classifications=classifications,
                    )
                )
        return tuple(scopes)

    def _now(self) -> datetime:
        current = self.clock.now()
        if current.tzinfo is None:
            raise ValueError("authentication context clock must return a timezone-aware timestamp")
        return current.astimezone(UTC)
