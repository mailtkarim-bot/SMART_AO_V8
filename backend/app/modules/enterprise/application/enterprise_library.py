from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.enterprise.application.enterprise_commands import (
    CreateEnterpriseCompanyCommand,
    RegisterEnterpriseDocumentCommand,
)
from app.modules.enterprise.infrastructure.models import (
    EnterpriseCompanyRecord,
    EnterpriseDocumentRecord,
    EnterpriseDocumentUploadRecord,
    EnterpriseDocumentVerificationRecord,
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
class EnterpriseDocumentProjection:
    document_id: UUID
    document_kind: str
    document_label: str
    issued_at: datetime
    expires_at: datetime | None
    verification_status: str
    verification_revision: int


@dataclass(frozen=True, slots=True)
class EnterpriseCompanyProjection:
    company_id: UUID
    aggregate_revision: int
    legal_name: str
    trade_name: str | None
    siren: str
    siret: str
    vat_number: str
    address_line1: str
    postal_code: str
    city: str
    country_code: str
    documents: tuple[EnterpriseDocumentProjection, ...]


class EnterpriseLibraryService:
    """Authorize patron-owned company and document writes before any private lookup."""

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

    def read_company(
        self,
        *,
        actor: ActorContext,
        now: datetime,
    ) -> EnterpriseCompanyProjection:
        self._authorize(
            actor=actor,
            resource_id=actor.tenant_id,
            now=now,
            capability=Capability.ENTERPRISE_LIBRARY_READ,
        )
        with self._session_factory() as session:
            company = session.scalar(
                sa.select(EnterpriseCompanyRecord).where(
                    EnterpriseCompanyRecord.tenant_id == actor.tenant_id,
                )
            )
            if company is None:
                raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
            rows = session.execute(
                sa.select(
                    EnterpriseDocumentRecord.id,
                    EnterpriseDocumentRecord.document_kind,
                    EnterpriseDocumentRecord.document_label,
                    EnterpriseDocumentRecord.issued_at,
                    EnterpriseDocumentRecord.expires_at,
                    EnterpriseDocumentRecord.verification_status,
                    sa.select(EnterpriseDocumentVerificationRecord.outcome)
                    .where(
                        EnterpriseDocumentVerificationRecord.tenant_id
                        == EnterpriseDocumentRecord.tenant_id,
                        EnterpriseDocumentVerificationRecord.document_id
                        == EnterpriseDocumentRecord.id,
                    )
                    .order_by(EnterpriseDocumentVerificationRecord.revision.desc())
                    .limit(1)
                    .scalar_subquery()
                    .label("latest_verification"),
                    sa.func.coalesce(
                        sa.select(sa.func.max(EnterpriseDocumentVerificationRecord.revision))
                        .where(
                            EnterpriseDocumentVerificationRecord.tenant_id
                            == EnterpriseDocumentRecord.tenant_id,
                            EnterpriseDocumentVerificationRecord.document_id
                            == EnterpriseDocumentRecord.id,
                        )
                        .scalar_subquery(),
                        0,
                    ).label("verification_revision"),
                )
                .where(
                    EnterpriseDocumentRecord.tenant_id == actor.tenant_id,
                    EnterpriseDocumentRecord.company_id == company.id,
                )
                .order_by(EnterpriseDocumentRecord.created_at, EnterpriseDocumentRecord.id)
            ).all()
        return EnterpriseCompanyProjection(
            company_id=company.id,
            aggregate_revision=company.aggregate_revision,
            legal_name=company.legal_name,
            trade_name=company.trade_name,
            siren=company.siren,
            siret=company.siret,
            vat_number=company.vat_number,
            address_line1=company.address_line1,
            postal_code=company.postal_code,
            city=company.city,
            country_code=company.country_code,
            documents=tuple(
                EnterpriseDocumentProjection(
                    document_id=row.id,
                    document_kind=row.document_kind,
                    document_label=row.document_label,
                    issued_at=row.issued_at,
                    expires_at=row.expires_at,
                    verification_status=row.latest_verification or row.verification_status,
                    verification_revision=row.verification_revision,
                )
                for row in rows
            ),
        )

    def create_company(
        self,
        *,
        actor: ActorContext,
        command: CreateEnterpriseCompanyCommand,
        now: datetime,
    ) -> DispatchResult:
        self._authorize(actor=actor, resource_id=command.company_id, now=now)
        return self._dispatcher.dispatch(
            command=command,
            context=self._context(actor=actor, now=now),
        )

    def register_document(
        self,
        *,
        actor: ActorContext,
        command: RegisterEnterpriseDocumentCommand,
        now: datetime,
    ) -> DispatchResult:
        classification = (
            DataClassification.FINANCIAL_PRIVATE
            if command.document_kind == "RIB"
            else DataClassification.PERSONAL_OR_ADMINISTRATIVE
        )
        self._authorize(
            actor=actor,
            resource_id=command.company_id,
            now=now,
            classification=classification,
        )
        with self._session_factory() as session:
            exists = session.scalar(
                sa.select(EnterpriseCompanyRecord.id).where(
                    EnterpriseCompanyRecord.tenant_id == actor.tenant_id,
                    EnterpriseCompanyRecord.id == command.company_id,
                )
            )
            upload = session.scalar(
                sa.select(EnterpriseDocumentUploadRecord).where(
                    EnterpriseDocumentUploadRecord.tenant_id == actor.tenant_id,
                    EnterpriseDocumentUploadRecord.id == command.storage_object_id,
                    EnterpriseDocumentUploadRecord.company_id == command.company_id,
                    EnterpriseDocumentUploadRecord.state == "CLEAN",
                )
            )
        if exists is None:
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        if upload is None:
            raise PermissionError("DOCUMENT_UPLOAD_NOT_CLEAN")
        command = command.model_copy(
            update={
                "document_id": upload.document_id,
                "document_kind": upload.document_kind,
                "document_label": upload.document_label,
                "original_filename": upload.original_filename,
                "sha256": upload.sha256,
            }
        )
        return self._dispatcher.dispatch(
            command=command,
            context=self._context(actor=actor, now=now),
        )

    def _authorize(
        self,
        *,
        actor: ActorContext,
        resource_id: UUID,
        now: datetime,
        classification: DataClassification = DataClassification.PERSONAL_OR_ADMINISTRATIVE,
        capability: Capability = Capability.ENTERPRISE_LIBRARY_WRITE,
    ) -> None:
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("ENTERPRISE_LIBRARY_PATRON_REQUIRED")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=capability,
                resource=AuthorizationResource(
                    resource_type="ENTERPRISE_LIBRARY",
                    resource_id=resource_id,
                    tenant_id=actor.tenant_id,
                    classification=classification,
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


class CreateEnterpriseCompanyHandler:
    """Create the single legal company root for the tenant."""

    def execute(
        self,
        *,
        session: Session,
        command: CreateEnterpriseCompanyCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        if context.actor_kind != ActorKind.PATRON_ADMIN.value or context.membership_id is None:
            raise CommandExecutionError("ENTERPRISE_LIBRARY_PATRON_REQUIRED")
        existing = session.scalar(
            sa.select(EnterpriseCompanyRecord)
            .where(
                EnterpriseCompanyRecord.tenant_id == context.tenant_id,
                EnterpriseCompanyRecord.id == command.company_id,
            )
            .with_for_update()
        )
        if existing is not None:
            raise CommandExecutionError("ENTERPRISE_COMPANY_ALREADY_EXISTS")
        session.add(
            EnterpriseCompanyRecord(
                id=command.company_id,
                tenant_id=context.tenant_id,
                aggregate_revision=0,
                legal_name=command.legal_name,
                trade_name=command.trade_name,
                siren=command.siren,
                siret=command.siret,
                vat_number=command.vat_number,
                address_line1=command.address_line1,
                postal_code=command.postal_code,
                city=command.city,
                country_code=command.country_code,
            )
        )
        return HandlerOutcome(
            result_code="ENTERPRISE_COMPANY_CREATED",
            aggregate_refs=(
                {
                    "aggregate_type": "EnterpriseCompany",
                    "aggregate_id": str(command.company_id),
                    "aggregate_revision": 0,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="EnterpriseCompany",
                    aggregate_id=command.company_id,
                    aggregate_revision=0,
                    event_type="EnterpriseCompanyCreated",
                    payload={
                        "company_id": str(command.company_id),
                        "resulting_revision": 0,
                    },
                ),
            ),
        )


class RegisterEnterpriseDocumentHandler:
    """Append one immutable proof document and advance the company revision."""

    def execute(
        self,
        *,
        session: Session,
        command: RegisterEnterpriseDocumentCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        if context.actor_kind != ActorKind.PATRON_ADMIN.value or context.membership_id is None:
            raise CommandExecutionError("ENTERPRISE_LIBRARY_PATRON_REQUIRED")
        company = session.scalar(
            sa.select(EnterpriseCompanyRecord)
            .where(
                EnterpriseCompanyRecord.tenant_id == context.tenant_id,
                EnterpriseCompanyRecord.id == command.company_id,
            )
            .with_for_update()
        )
        if company is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if company.aggregate_revision != command.expected_revision:
            raise CommandExecutionError("VERSION_CONFLICT")
        upload = session.scalar(
            sa.select(EnterpriseDocumentUploadRecord)
            .where(
                EnterpriseDocumentUploadRecord.tenant_id == context.tenant_id,
                EnterpriseDocumentUploadRecord.id == command.storage_object_id,
                EnterpriseDocumentUploadRecord.company_id == command.company_id,
                EnterpriseDocumentUploadRecord.document_id == command.document_id,
                EnterpriseDocumentUploadRecord.state == "CLEAN",
            )
            .with_for_update()
        )
        if upload is None:
            raise CommandExecutionError("DOCUMENT_UPLOAD_NOT_CLEAN")
        command.sha256 = upload.sha256
        session.add(
            EnterpriseDocumentRecord(
                id=command.document_id,
                tenant_id=context.tenant_id,
                company_id=company.id,
                document_kind=command.document_kind,
                document_label=command.document_label,
                storage_object_id=command.storage_object_id,
                original_filename=command.original_filename,
                issued_at=command.issued_at,
                expires_at=command.expires_at,
                sha256=command.sha256,
                verification_status=command.verification_status,
                registered_by_membership_id=context.membership_id,
                command_id=command.command_id,
                idempotency_key=command.idempotency_key,
                correlation_id=command.correlation_id,
            )
        )
        company.aggregate_revision += 1
        revision = company.aggregate_revision
        return HandlerOutcome(
            result_code="ENTERPRISE_DOCUMENT_REGISTERED",
            aggregate_refs=(
                {
                    "aggregate_type": "EnterpriseCompany",
                    "aggregate_id": str(company.id),
                    "aggregate_revision": revision,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="EnterpriseCompany",
                    aggregate_id=company.id,
                    aggregate_revision=revision,
                    event_type="EnterpriseDocumentRegistered",
                    payload={
                        "company_id": str(company.id),
                        "document_id": str(command.document_id),
                        "document_kind": command.document_kind,
                        "resulting_revision": revision,
                    },
                ),
            ),
        )


def enterprise_library_handlers() -> dict[str, CommandHandler]:
    """Return the closed dispatcher registry for enterprise library writes."""

    return {
        "CreateEnterpriseCompany": CreateEnterpriseCompanyHandler(),
        "RegisterEnterpriseDocument": RegisterEnterpriseDocumentHandler(),
    }
