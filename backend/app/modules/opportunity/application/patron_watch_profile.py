"""Patron-authorized service and dispatcher handlers for watch profiles."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.opportunity.application.watch_profile_commands import (
    AddOpportunityWatchProfileVersionCommand,
    CreateOpportunityWatchProfileCommand,
)
from app.modules.opportunity.domain.watch_profile import WatchProfileState, normalize_profile_name
from app.modules.opportunity.infrastructure.models import (
    OpportunityWatchProfileRecord,
    OpportunityWatchProfileVersionRecord,
)
from app.platform.events.dispatcher import (
    CommandContext,
    CommandDispatcher,
    CommandExecutionError,
    CommandHandler,
    DispatchResult,
    HandlerOutcome,
    PendingDomainEvent,
)
from app.platform.security.authorization import (
    AuthorizationPolicyPort,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext, ActorKind, DataClassification


@dataclass(frozen=True, slots=True)
class WatchProfileVersionProjection:
    version_id: UUID
    version_number: int
    name: str
    criteria: dict[str, object]
    criteria_sha256: str


@dataclass(frozen=True, slots=True)
class WatchProfileProjection:
    profile_id: UUID
    aggregate_revision: int
    current_version: int
    state: str
    versions: tuple[WatchProfileVersionProjection, ...]


class PatronWatchProfileService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        dispatcher: CommandDispatcher,
        policy: AuthorizationPolicyPort,
    ) -> None:
        self._session_factory = session_factory
        self._dispatcher = dispatcher
        self._policy = policy

    def create(
        self,
        *,
        actor: ActorContext,
        command: CreateOpportunityWatchProfileCommand,
        now: datetime,
    ) -> DispatchResult:
        self._authorize(actor=actor, profile_id=command.profile_id, now=now, write=True)
        return self._dispatcher.dispatch(
            command=command, context=self._context(actor=actor, now=now)
        )

    def add_version(
        self,
        *,
        actor: ActorContext,
        command: AddOpportunityWatchProfileVersionCommand,
        now: datetime,
    ) -> DispatchResult:
        with self._session_factory() as session:
            exists = session.scalar(
                sa.select(OpportunityWatchProfileRecord.id).where(
                    OpportunityWatchProfileRecord.tenant_id == actor.tenant_id,
                    OpportunityWatchProfileRecord.id == command.profile_id,
                )
            )
        if exists is None:
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        self._authorize(actor=actor, profile_id=command.profile_id, now=now, write=True)
        return self._dispatcher.dispatch(
            command=command, context=self._context(actor=actor, now=now)
        )

    def read(
        self, *, actor: ActorContext, profile_id: UUID, now: datetime
    ) -> WatchProfileProjection:
        self._authorize(actor=actor, profile_id=profile_id, now=now, write=False)
        with self._session_factory() as session:
            profile = session.scalar(
                sa.select(OpportunityWatchProfileRecord).where(
                    OpportunityWatchProfileRecord.tenant_id == actor.tenant_id,
                    OpportunityWatchProfileRecord.id == profile_id,
                )
            )
            if profile is None:
                raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
            versions = tuple(
                session.scalars(
                    sa.select(OpportunityWatchProfileVersionRecord)
                    .where(
                        OpportunityWatchProfileVersionRecord.tenant_id == actor.tenant_id,
                        OpportunityWatchProfileVersionRecord.profile_id == profile_id,
                    )
                    .order_by(OpportunityWatchProfileVersionRecord.version_number)
                )
            )
        return WatchProfileProjection(
            profile_id=profile.id,
            aggregate_revision=profile.aggregate_revision,
            current_version=profile.current_version,
            state=profile.state,
            versions=tuple(
                WatchProfileVersionProjection(
                    version_id=version.id,
                    version_number=version.version_number,
                    name=version.name,
                    criteria=dict(version.criteria_json),
                    criteria_sha256=version.criteria_sha256,
                )
                for version in versions
            ),
        )

    def read_all(self, *, actor: ActorContext, now: datetime) -> tuple[WatchProfileProjection, ...]:
        self._authorize(actor=actor, profile_id=None, now=now, write=False)
        with self._session_factory() as session:
            profiles = tuple(
                session.scalars(
                    sa.select(OpportunityWatchProfileRecord)
                    .where(OpportunityWatchProfileRecord.tenant_id == actor.tenant_id)
                    .order_by(
                        OpportunityWatchProfileRecord.created_at,
                        OpportunityWatchProfileRecord.id,
                    )
                )
            )
            version_rows = tuple(
                session.scalars(
                    sa.select(OpportunityWatchProfileVersionRecord)
                    .where(OpportunityWatchProfileVersionRecord.tenant_id == actor.tenant_id)
                    .order_by(
                        OpportunityWatchProfileVersionRecord.profile_id,
                        OpportunityWatchProfileVersionRecord.version_number,
                    )
                )
            )
        versions_by_profile: dict[UUID, list[OpportunityWatchProfileVersionRecord]] = {}
        for version in version_rows:
            versions_by_profile.setdefault(version.profile_id, []).append(version)
        return tuple(
            _projection(profile, tuple(versions_by_profile.get(profile.id, [])))
            for profile in profiles
        )

    def _authorize(
        self, *, actor: ActorContext, profile_id: UUID | None, now: datetime, write: bool
    ) -> None:
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("OPPORTUNITY_PROFILE_PATRON_REQUIRED")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=(
                    Capability.OPPORTUNITY_PROFILE_WRITE
                    if write
                    else Capability.OPPORTUNITY_PROFILE_READ
                ),
                resource=AuthorizationResource(
                    resource_type="OPPORTUNITY_WATCH_PROFILE",
                    resource_id=profile_id or actor.tenant_id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.PERSONAL_OR_ADMINISTRATIVE,
                ),
                evaluated_at=now,
            ),
        )
        if not decision.allowed:
            raise PermissionError(decision.code)

    @staticmethod
    def _context(*, actor: ActorContext, now: datetime) -> CommandContext:
        return CommandContext(
            tenant_id=actor.tenant_id,
            actor_id=actor.actor_id,
            actor_kind=actor.actor_kind.value,
            received_at=now,
            identity_id=actor.identity_id,
            membership_id=actor.membership_id,
            session_id=actor.session_id,
            case_id=None,
            correlation_id=actor.correlation_id,
        )


class CreateOpportunityWatchProfileHandler:
    def execute(
        self,
        *,
        session: Session,
        command: CreateOpportunityWatchProfileCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        _require_patron(context)
        name = normalize_profile_name(command.name)
        criteria = command.criteria()
        existing = session.scalar(
            sa.select(OpportunityWatchProfileRecord).where(
                OpportunityWatchProfileRecord.tenant_id == context.tenant_id,
                OpportunityWatchProfileRecord.id == command.profile_id,
            )
        )
        if existing is not None:
            raise CommandExecutionError("OPPORTUNITY_PROFILE_ALREADY_EXISTS")
        session.add(
            OpportunityWatchProfileRecord(
                id=command.profile_id,
                tenant_id=context.tenant_id,
                aggregate_revision=0,
                name=name,
                state=WatchProfileState.ACTIVE.value,
                current_version=1,
                actor_id=context.actor_id,
                command_id=command.command_id,
                idempotency_key=command.idempotency_key,
                correlation_id=command.correlation_id,
            )
        )
        session.add(
            _version_record(
                profile_id=command.profile_id,
                version_id=uuid5(
                    NAMESPACE_URL,
                    f"smart-ao:opportunity-watch-profile:{command.profile_id}:version:1",
                ),
                version_number=1,
                name=name,
                criteria=criteria.snapshot(),
                command=command,
                context=context,
            )
        )
        return HandlerOutcome(
            result_code="OPPORTUNITY_PROFILE_CREATED",
            aggregate_refs=(
                {
                    "aggregate_type": "OpportunityWatchProfile",
                    "aggregate_id": str(command.profile_id),
                    "aggregate_revision": 0,
                    "version_number": 1,
                    "version_id": str(
                        uuid5(
                            NAMESPACE_URL,
                            f"smart-ao:opportunity-watch-profile:{command.profile_id}:version:1",
                        )
                    ),
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="OpportunityWatchProfile",
                    aggregate_id=command.profile_id,
                    aggregate_revision=0,
                    event_type="OpportunityWatchProfileCreated",
                    payload={"profile_id": str(command.profile_id), "version_number": 1},
                ),
            ),
        )


class AddOpportunityWatchProfileVersionHandler:
    def execute(
        self,
        *,
        session: Session,
        command: AddOpportunityWatchProfileVersionCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        _require_patron(context)
        profile = session.scalar(
            sa.select(OpportunityWatchProfileRecord)
            .where(
                OpportunityWatchProfileRecord.tenant_id == context.tenant_id,
                OpportunityWatchProfileRecord.id == command.profile_id,
            )
            .with_for_update()
        )
        if profile is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if profile.aggregate_revision != command.expected_revision:
            raise CommandExecutionError("VERSION_CONFLICT")
        existing = session.scalar(
            sa.select(OpportunityWatchProfileVersionRecord).where(
                OpportunityWatchProfileVersionRecord.tenant_id == context.tenant_id,
                OpportunityWatchProfileVersionRecord.id == command.version_id,
            )
        )
        if existing is not None:
            raise CommandExecutionError("OPPORTUNITY_PROFILE_VERSION_ALREADY_EXISTS")
        criteria = command.criteria()
        version_number = profile.current_version + 1
        name = normalize_profile_name(command.name or profile.name)
        session.add(
            _version_record(
                profile_id=profile.id,
                version_id=command.version_id,
                version_number=version_number,
                name=name,
                criteria=criteria.snapshot(),
                command=command,
                context=context,
            )
        )
        profile.name = name
        profile.current_version = version_number
        profile.aggregate_revision += 1
        revision = profile.aggregate_revision
        return HandlerOutcome(
            result_code="OPPORTUNITY_PROFILE_VERSION_ADDED",
            aggregate_refs=(
                {
                    "aggregate_type": "OpportunityWatchProfile",
                    "aggregate_id": str(profile.id),
                    "aggregate_revision": revision,
                    "version_number": version_number,
                    "version_id": str(command.version_id),
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="OpportunityWatchProfile",
                    aggregate_id=profile.id,
                    aggregate_revision=revision,
                    event_type="OpportunityWatchProfileVersionAdded",
                    payload={
                        "profile_id": str(profile.id),
                        "version_id": str(command.version_id),
                        "version_number": version_number,
                    },
                ),
            ),
        )


def opportunity_watch_profile_handlers() -> dict[str, CommandHandler]:
    return {
        "CreateOpportunityWatchProfile": CreateOpportunityWatchProfileHandler(),
        "AddOpportunityWatchProfileVersion": AddOpportunityWatchProfileVersionHandler(),
    }


def _require_patron(context: CommandContext) -> None:
    if context.actor_kind != ActorKind.PATRON_ADMIN.value or context.membership_id is None:
        raise CommandExecutionError("OPPORTUNITY_PROFILE_PATRON_REQUIRED")


def _version_record(
    *,
    profile_id: UUID,
    version_id: UUID,
    version_number: int,
    name: str,
    criteria: dict[str, object],
    command: CreateOpportunityWatchProfileCommand | AddOpportunityWatchProfileVersionCommand,
    context: CommandContext,
) -> OpportunityWatchProfileVersionRecord:
    return OpportunityWatchProfileVersionRecord(
        id=version_id,
        tenant_id=context.tenant_id,
        profile_id=profile_id,
        version_number=version_number,
        name=name,
        criteria_json=criteria,
        criteria_sha256=_criteria_hash(criteria),
        actor_id=context.actor_id,
        command_id=command.command_id,
        idempotency_key=command.idempotency_key,
        correlation_id=command.correlation_id,
    )


def _criteria_hash(criteria: dict[str, object]) -> str:
    canonical = json.dumps(criteria, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _projection(
    profile: OpportunityWatchProfileRecord,
    versions: tuple[OpportunityWatchProfileVersionRecord, ...],
) -> WatchProfileProjection:
    return WatchProfileProjection(
        profile_id=profile.id,
        aggregate_revision=profile.aggregate_revision,
        current_version=profile.current_version,
        state=profile.state,
        versions=tuple(
            WatchProfileVersionProjection(
                version_id=version.id,
                version_number=version.version_number,
                name=version.name,
                criteria=dict(version.criteria_json),
                criteria_sha256=version.criteria_sha256,
            )
            for version in versions
        ),
    )
