from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.enterprise.application.enterprise_capability_commands import (
    AddEnterpriseCapabilityVersionCommand,
    CreateEnterpriseCapabilityCommand,
)
from app.platform.events.dispatcher import (
    CommandContext,
    CommandDispatcher,
    CommandExecutionError,
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
from app.platform.security.models import (
    EnterpriseCapabilityProofLinkRecord,
    EnterpriseCapabilityRecord,
    EnterpriseCapabilityVersionRecord,
    EnterpriseCompanyRecord,
    EnterpriseDocumentRecord,
)


@dataclass(frozen=True, slots=True)
class EnterpriseCapabilityVersionProjection:
    version_id: UUID
    version_number: int
    title: str
    description: str
    valid_from: datetime
    valid_until: datetime | None
    usage_scope: str
    proof_document_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class EnterpriseCapabilityProjection:
    capability_id: UUID
    company_id: UUID
    aggregate_revision: int
    capability_kind: str
    name: str
    summary: str
    state: str
    versions: tuple[EnterpriseCapabilityVersionProjection, ...]


class EnterpriseCapabilityService:
    """Patron-owned capability catalog; no Case assessment is created here."""

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

    def create_capability(
        self,
        *,
        actor: ActorContext,
        command: CreateEnterpriseCapabilityCommand,
        now: datetime,
    ) -> DispatchResult:
        self._authorize(actor=actor, resource_id=command.company_id, now=now, write=True)
        return self._dispatcher.dispatch(
            command=command, context=self._context(actor=actor, now=now)
        )

    def add_version(
        self,
        *,
        actor: ActorContext,
        command: AddEnterpriseCapabilityVersionCommand,
        now: datetime,
    ) -> DispatchResult:
        with self._session_factory() as session:
            capability = session.scalar(
                sa.select(EnterpriseCapabilityRecord).where(
                    EnterpriseCapabilityRecord.tenant_id == actor.tenant_id,
                    EnterpriseCapabilityRecord.id == command.capability_id,
                )
            )
        if capability is None:
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        self._authorize(actor=actor, resource_id=capability.company_id, now=now, write=True)
        return self._dispatcher.dispatch(
            command=command, context=self._context(actor=actor, now=now)
        )

    def read_capabilities(
        self,
        *,
        actor: ActorContext,
        company_id: UUID,
        now: datetime,
    ) -> tuple[EnterpriseCapabilityProjection, ...]:
        self._authorize(actor=actor, resource_id=company_id, now=now, write=False)
        with self._session_factory() as session:
            company_exists = session.scalar(
                sa.select(EnterpriseCompanyRecord.id).where(
                    EnterpriseCompanyRecord.tenant_id == actor.tenant_id,
                    EnterpriseCompanyRecord.id == company_id,
                )
            )
            if company_exists is None:
                raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
            capabilities = list(
                session.scalars(
                    sa.select(EnterpriseCapabilityRecord)
                    .where(
                        EnterpriseCapabilityRecord.tenant_id == actor.tenant_id,
                        EnterpriseCapabilityRecord.company_id == company_id,
                    )
                    .order_by(EnterpriseCapabilityRecord.created_at, EnterpriseCapabilityRecord.id)
                )
            )
            versions = (
                list(
                    session.scalars(
                        sa.select(EnterpriseCapabilityVersionRecord)
                        .where(
                            EnterpriseCapabilityVersionRecord.tenant_id == actor.tenant_id,
                            EnterpriseCapabilityVersionRecord.capability_id.in_(
                                [item.id for item in capabilities]
                            ),
                        )
                        .order_by(
                            EnterpriseCapabilityVersionRecord.capability_id,
                            EnterpriseCapabilityVersionRecord.version_number,
                        )
                    )
                )
                if capabilities
                else []
            )
            links = (
                list(
                    session.scalars(
                        sa.select(EnterpriseCapabilityProofLinkRecord).where(
                            EnterpriseCapabilityProofLinkRecord.tenant_id == actor.tenant_id,
                            EnterpriseCapabilityProofLinkRecord.capability_version_id.in_(
                                [item.id for item in versions]
                            ),
                        )
                    )
                )
                if versions
                else []
            )
        links_by_version: dict[UUID, list[UUID]] = {}
        for link in links:
            links_by_version.setdefault(link.capability_version_id, []).append(link.document_id)
        versions_by_capability: dict[UUID, list[EnterpriseCapabilityVersionProjection]] = {}
        for version in versions:
            versions_by_capability.setdefault(version.capability_id, []).append(
                EnterpriseCapabilityVersionProjection(
                    version_id=version.id,
                    version_number=version.version_number,
                    title=version.title,
                    description=version.description,
                    valid_from=version.valid_from,
                    valid_until=version.valid_until,
                    usage_scope=version.usage_scope,
                    proof_document_ids=tuple(sorted(links_by_version.get(version.id, []), key=str)),
                )
            )
        return tuple(
            EnterpriseCapabilityProjection(
                capability_id=item.id,
                company_id=item.company_id,
                aggregate_revision=item.aggregate_revision,
                capability_kind=item.capability_kind,
                name=item.name,
                summary=item.summary,
                state=item.state,
                versions=tuple(versions_by_capability.get(item.id, [])),
            )
            for item in capabilities
        )

    def _authorize(
        self, *, actor: ActorContext, resource_id: UUID, now: datetime, write: bool
    ) -> None:
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("ENTERPRISE_CAPABILITY_PATRON_REQUIRED")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.ENTERPRISE_CAPABILITY_WRITE
                if write
                else Capability.ENTERPRISE_CAPABILITY_READ,
                resource=AuthorizationResource(
                    resource_type="ENTERPRISE_CAPABILITY",
                    resource_id=resource_id,
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


class CreateEnterpriseCapabilityHandler:
    """Create a capability root under the single tenant company."""

    def execute(
        self,
        *,
        session: Session,
        command: CreateEnterpriseCapabilityCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        if context.actor_kind != ActorKind.PATRON_ADMIN.value or context.membership_id is None:
            raise CommandExecutionError("ENTERPRISE_CAPABILITY_PATRON_REQUIRED")
        company = session.scalar(
            sa.select(EnterpriseCompanyRecord).where(
                EnterpriseCompanyRecord.tenant_id == context.tenant_id,
                EnterpriseCompanyRecord.id == command.company_id,
            )
        )
        if company is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        existing = session.scalar(
            sa.select(EnterpriseCapabilityRecord).where(
                EnterpriseCapabilityRecord.tenant_id == context.tenant_id,
                EnterpriseCapabilityRecord.id == command.capability_id,
            )
        )
        if existing is not None:
            raise CommandExecutionError("CAPABILITY_ALREADY_EXISTS")
        session.add(
            EnterpriseCapabilityRecord(
                id=command.capability_id,
                tenant_id=context.tenant_id,
                company_id=company.id,
                aggregate_revision=0,
                capability_kind=command.capability_kind,
                name=command.name,
                summary=command.summary,
                state=command.state,
                command_id=command.command_id,
                idempotency_key=command.idempotency_key,
                correlation_id=command.correlation_id,
            )
        )
        return HandlerOutcome(
            result_code="ENTERPRISE_CAPABILITY_CREATED",
            aggregate_refs=(
                {
                    "aggregate_type": "EnterpriseCapability",
                    "aggregate_id": str(command.capability_id),
                    "aggregate_revision": 0,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="EnterpriseCapability",
                    aggregate_id=command.capability_id,
                    aggregate_revision=0,
                    event_type="EnterpriseCapabilityCreated",
                    payload={
                        "capability_id": str(command.capability_id),
                        "company_id": str(command.company_id),
                        "capability_kind": command.capability_kind,
                        "resulting_revision": 0,
                    },
                ),
            ),
        )


class AddEnterpriseCapabilityVersionHandler:
    """Append a dated capability version and opaque links to company documents."""

    def execute(
        self,
        *,
        session: Session,
        command: AddEnterpriseCapabilityVersionCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        if context.actor_kind != ActorKind.PATRON_ADMIN.value or context.membership_id is None:
            raise CommandExecutionError("ENTERPRISE_CAPABILITY_PATRON_REQUIRED")
        capability = session.scalar(
            sa.select(EnterpriseCapabilityRecord)
            .where(
                EnterpriseCapabilityRecord.tenant_id == context.tenant_id,
                EnterpriseCapabilityRecord.id == command.capability_id,
            )
            .with_for_update()
        )
        if capability is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if capability.aggregate_revision != command.expected_revision:
            raise CommandExecutionError("VERSION_CONFLICT")
        existing_version = session.scalar(
            sa.select(EnterpriseCapabilityVersionRecord).where(
                EnterpriseCapabilityVersionRecord.tenant_id == context.tenant_id,
                EnterpriseCapabilityVersionRecord.id == command.version_id,
            )
        )
        if existing_version is not None:
            raise CommandExecutionError("CAPABILITY_VERSION_ALREADY_EXISTS")
        documents = (
            list(
                session.scalars(
                    sa.select(EnterpriseDocumentRecord).where(
                        EnterpriseDocumentRecord.tenant_id == context.tenant_id,
                        EnterpriseDocumentRecord.company_id == capability.company_id,
                        EnterpriseDocumentRecord.id.in_(command.proof_document_ids),
                    )
                )
            )
            if command.proof_document_ids
            else []
        )
        if len(documents) != len(command.proof_document_ids):
            raise CommandExecutionError("PROOF_NOT_FOUND_OR_FORBIDDEN")
        if any(document.verification_status == "REJECTED" for document in documents):
            raise CommandExecutionError("PROOF_NOT_AUTHORIZED")
        latest_number = (
            session.scalar(
                sa.select(sa.func.max(EnterpriseCapabilityVersionRecord.version_number)).where(
                    EnterpriseCapabilityVersionRecord.tenant_id == context.tenant_id,
                    EnterpriseCapabilityVersionRecord.capability_id == capability.id,
                )
            )
            or 0
        )
        version_number = int(latest_number) + 1
        session.add(
            EnterpriseCapabilityVersionRecord(
                id=command.version_id,
                tenant_id=context.tenant_id,
                capability_id=capability.id,
                version_number=version_number,
                title=command.title,
                description=command.description,
                valid_from=command.valid_from,
                valid_until=command.valid_until,
                usage_scope=command.usage_scope,
                created_by_membership_id=context.membership_id,
                command_id=command.command_id,
                idempotency_key=command.idempotency_key,
                correlation_id=command.correlation_id,
            )
        )
        session.flush()
        for document_id in command.proof_document_ids:
            session.add(
                EnterpriseCapabilityProofLinkRecord(
                    id=uuid4(),
                    tenant_id=context.tenant_id,
                    capability_version_id=command.version_id,
                    document_id=document_id,
                    relation_label="SUPPORTS_CAPABILITY",
                )
            )
        capability.aggregate_revision += 1
        revision = capability.aggregate_revision
        return HandlerOutcome(
            result_code="ENTERPRISE_CAPABILITY_VERSION_ADDED",
            aggregate_refs=(
                {
                    "aggregate_type": "EnterpriseCapability",
                    "aggregate_id": str(capability.id),
                    "aggregate_revision": revision,
                    "version_id": str(command.version_id),
                    "version_number": version_number,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="EnterpriseCapability",
                    aggregate_id=capability.id,
                    aggregate_revision=revision,
                    event_type="EnterpriseCapabilityVersionAdded",
                    payload={
                        "capability_id": str(capability.id),
                        "version_id": str(command.version_id),
                        "version_number": version_number,
                        "proof_count": len(command.proof_document_ids),
                        "resulting_revision": revision,
                    },
                ),
            ),
        )


def enterprise_capability_handlers() -> dict[str, object]:
    return {
        "CreateEnterpriseCapability": CreateEnterpriseCapabilityHandler(),
        "AddEnterpriseCapabilityVersion": AddEnterpriseCapabilityVersionHandler(),
    }
