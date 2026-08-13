"""Trusted server-side actor facts used by authorization policies.

This module intentionally has no HTTP, ORM, session-storage, or business-module
imports. S02-B will supply identity/session persistence; S02-A only freezes the
contract that downstream code must consume.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID


class ActorKind(StrEnum):
    """The stable actor categories defined by SEC-01."""

    PATRON_ADMIN = "PATRON_ADMIN"
    PATRON_DELEGATE = "PATRON_DELEGATE"
    COLLABORATEUR = "COLLABORATEUR"
    PARTENAIRE_EXTERNAL = "PARTENAIRE_EXTERNAL"
    SUPPORT_BREAK_GLASS = "SUPPORT_BREAK_GLASS"
    SYSTEM = "SYSTEM"


class MembershipState(StrEnum):
    """States that control whether a tenant membership can authorize access."""

    INVITED = "INVITED"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class DataClassification(StrEnum):
    """Server-owned classifications used before a representation is serialized."""

    PUBLIC_TENDER = "PUBLIC_TENDER"
    INTERNAL_OPERATIONAL = "INTERNAL_OPERATIONAL"
    PERSONAL_OR_ADMINISTRATIVE = "PERSONAL_OR_ADMINISTRATIVE"
    FINANCIAL_PRIVATE = "FINANCIAL_PRIVATE"
    SECURITY_RESTRICTED = "SECURITY_RESTRICTED"
    SUPPORT_RESTRICTED = "SUPPORT_RESTRICTED"


@dataclass(frozen=True, slots=True)
class ActorContext:
    """Trusted and immutable authorization facts resolved by the server."""

    actor_id: UUID
    identity_id: UUID
    tenant_id: UUID
    membership_id: UUID
    actor_kind: ActorKind
    membership_state: MembershipState
    capabilities: frozenset[str]
    assigned_case_ids: frozenset[UUID]
    session_id: UUID | None
    authenticated_at: datetime
    mfa_verified_at: datetime | None
    correlation_id: UUID

    @property
    def membership_is_active(self) -> bool:
        """Whether this context can authorize tenant-scoped user operations."""

        return self.membership_state is MembershipState.ACTIVE

    def has_recent_mfa(
        self,
        *,
        evaluated_at: datetime,
        maximum_age: timedelta = timedelta(minutes=15),
    ) -> bool:
        """Return whether MFA was verified in the bounded step-up window."""

        if self.mfa_verified_at is None:
            return False
        if self.mfa_verified_at > evaluated_at:
            return False
        return evaluated_at - self.mfa_verified_at <= maximum_age
