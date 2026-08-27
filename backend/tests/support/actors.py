from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.platform.security.context import ActorContext, ActorKind, MembershipState


def make_actor_context(
    *,
    actor_kind: ActorKind = ActorKind.PATRON_ADMIN,
    tenant_id: UUID | None = None,
    membership_id: UUID | None = None,
    session_id: UUID | None = None,
) -> ActorContext:
    """Build a trusted actor fixture without widening test doubles to object."""
    return ActorContext(
        actor_id=uuid4(),
        identity_id=uuid4(),
        tenant_id=tenant_id or uuid4(),
        membership_id=membership_id or uuid4(),
        actor_kind=actor_kind,
        membership_state=MembershipState.ACTIVE,
        capabilities=frozenset(),
        assigned_case_ids=frozenset(),
        session_id=session_id,
        authenticated_at=datetime.now(tz=UTC),
        mfa_verified_at=None,
        correlation_id=uuid4(),
    )
