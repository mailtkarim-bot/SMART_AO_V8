from __future__ import annotations

from collections.abc import AsyncIterable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.enterprise.application.enterprise_library import EnterpriseLibraryService
from app.modules.enterprise.application.enterprise_upload_commands import (
    FinalizeEnterpriseDocumentUploadCommand,
    PrepareEnterpriseDocumentUploadCommand,
    VerifyEnterpriseDocumentCommand,
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
from app.platform.security.authorization import AuthorizationPolicyPort
from app.platform.security.context import ActorContext, ActorKind
from app.platform.storage.quarantine import (
    ContentInspectionPort,
    MalwareScanPort,
    QuarantineStoragePort,
)


@dataclass(frozen=True, slots=True)
class EnterpriseUploadTarget:
    upload_id: UUID
    tenant_id: UUID
    company_id: UUID
    document_id: UUID
    document_kind: str
    document_label: str
    original_filename: str
    storage_key: str
    expected_byte_size: int
    expires_at: datetime
    state: str
    sha256: str | None


@dataclass(frozen=True, slots=True)
class EnterpriseUploadResult:
    upload_id: UUID
    state: str


class EnterpriseUploadRejectedError(RuntimeError):
    def __init__(self, *, status_code: int = 422) -> None:
        super().__init__("UPLOAD_REJECTED")
        self.status_code = status_code


class EnterpriseUploadAlreadyClaimedError(RuntimeError):
    pass


class EnterprisePrivateUploadService:
    """Company-private upload orchestration; no path, URL or hash enters public responses."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        dispatcher: CommandDispatcher,
        policy: AuthorizationPolicyPort,
        storage: QuarantineStoragePort,
        inspector: ContentInspectionPort,
        scanner: MalwareScanPort,
        allowed_media_types: frozenset[str],
        max_bytes: int = 2_000_000_000,
    ) -> None:
        self._session_factory = session_factory
        self._dispatcher = dispatcher
        self._policy = policy
        self._storage = storage
        self._inspector = inspector
        self._scanner = scanner
        self._allowed_media_types = allowed_media_types
        self._max_bytes = max_bytes

    def prepare(
        self, *, actor: ActorContext, command: PrepareEnterpriseDocumentUploadCommand, now: datetime
    ) -> DispatchResult:
        EnterpriseLibraryService(
            session_factory=self._session_factory, dispatcher=self._dispatcher, policy=self._policy
        )._authorize(actor=actor, resource_id=command.company_id, now=now)
        return self._dispatcher.dispatch(command=command, context=self._context(actor, now))

    def target(self, *, tenant_id: UUID, upload_id: UUID) -> EnterpriseUploadTarget | None:
        with self._session_factory() as session:
            record = session.scalar(
                sa.select(EnterpriseDocumentUploadRecord).where(
                    EnterpriseDocumentUploadRecord.tenant_id == tenant_id,
                    EnterpriseDocumentUploadRecord.id == upload_id,
                )
            )
            if record is None:
                return None
            return EnterpriseUploadTarget(
                upload_id=record.id,
                tenant_id=record.tenant_id,
                company_id=record.company_id,
                document_id=record.document_id,
                document_kind=record.document_kind,
                document_label=record.document_label,
                original_filename=record.original_filename,
                storage_key=record.storage_key,
                expected_byte_size=record.expected_byte_size,
                expires_at=record.expires_at,
                state=record.state,
                sha256=record.sha256,
            )

    async def upload(
        self,
        *,
        actor: ActorContext,
        upload_id: UUID,
        stream: AsyncIterable[bytes],
        content_length: int | None,
    ) -> EnterpriseUploadResult:
        now = datetime.now(tz=UTC)
        EnterpriseLibraryService(
            session_factory=self._session_factory, dispatcher=self._dispatcher, policy=self._policy
        )._authorize(actor=actor, resource_id=upload_id, now=now)
        target = self.target(tenant_id=actor.tenant_id, upload_id=upload_id)
        if target is None:
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        with self._session_factory() as session:
            row = session.scalar(
                sa.select(EnterpriseDocumentUploadRecord)
                .where(
                    EnterpriseDocumentUploadRecord.tenant_id == actor.tenant_id,
                    EnterpriseDocumentUploadRecord.id == upload_id,
                )
                .with_for_update()
            )
            if row is None:
                raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
            if row.state == "CLEAN":
                existing_document = session.scalar(
                    sa.select(EnterpriseDocumentRecord).where(
                        EnterpriseDocumentRecord.tenant_id == actor.tenant_id,
                        EnterpriseDocumentRecord.id == row.document_id,
                    )
                )
                if existing_document is not None:
                    return EnterpriseUploadResult(upload_id=upload_id, state="CLEAN")
            elif row.state != "AWAITING_UPLOAD":
                raise EnterpriseUploadAlreadyClaimedError()
            else:
                row.state = "UPLOADING"
                session.commit()
        if content_length is not None and content_length > self._max_bytes:
            self._reject(upload_id=upload_id, code="UPLOAD_LIMIT_EXCEEDED")
            raise EnterpriseUploadRejectedError(status_code=413)
        try:
            result = await self._storage.write(
                storage_key=target.storage_key, stream=stream, max_bytes=self._max_bytes
            )
            if result.byte_size == 0:
                raise EnterpriseUploadRejectedError()
            media_type = await self._inspector.detect_media_type(storage_key=target.storage_key)
            if (
                result.byte_size != target.expected_byte_size
                or media_type not in self._allowed_media_types
            ):
                self._reject(upload_id=upload_id, code="MEDIA_TYPE_NOT_ALLOWED")
                await self._storage.delete(storage_key=target.storage_key)
                raise EnterpriseUploadRejectedError()
            with self._session_factory() as session:
                row = session.scalar(
                    sa.select(EnterpriseDocumentUploadRecord)
                    .where(
                        EnterpriseDocumentUploadRecord.tenant_id == actor.tenant_id,
                        EnterpriseDocumentUploadRecord.id == upload_id,
                    )
                    .with_for_update()
                )
                row.actual_byte_size = result.byte_size
                row.sha256 = result.sha256
                row.media_type = media_type
                row.state = "QUARANTINED"
                session.commit()
            scan = await self._scanner.scan(storage_key=target.storage_key)
            with self._session_factory() as session:
                row = session.scalar(
                    sa.select(EnterpriseDocumentUploadRecord)
                    .where(
                        EnterpriseDocumentUploadRecord.tenant_id == actor.tenant_id,
                        EnterpriseDocumentUploadRecord.id == upload_id,
                    )
                    .with_for_update()
                )
                row.scan_verdict = scan.verdict
                row.scanner_name = scan.scanner_name
                row.scanner_signature_version = scan.scanner_signature_version
                row.scanned_at = scan.scanned_at
                row.state = "CLEAN" if scan.verdict == "CLEAN" else "REJECTED"
                if scan.verdict != "CLEAN":
                    row.rejection_code = "MALWARE_SCAN_REJECTED"
                session.commit()
            if scan.verdict != "CLEAN":
                await self._storage.delete(storage_key=target.storage_key)
                raise EnterpriseUploadRejectedError()
            clean_target = self.target(tenant_id=actor.tenant_id, upload_id=upload_id)
            if clean_target is None or clean_target.sha256 is None:
                raise EnterpriseUploadRejectedError()
            self._finalize_clean_upload(actor=actor, target=clean_target)
            return EnterpriseUploadResult(upload_id=upload_id, state="CLEAN")
        except EnterpriseUploadRejectedError:
            raise
        except Exception as error:
            self._reject(upload_id=upload_id, code="STORAGE_OR_SCAN_FAILED")
            with suppress(Exception):
                await self._storage.delete(storage_key=target.storage_key)
            raise EnterpriseUploadRejectedError() from error

    def verify(
        self, *, actor: ActorContext, command: VerifyEnterpriseDocumentCommand, now: datetime
    ) -> DispatchResult:
        EnterpriseLibraryService(
            session_factory=self._session_factory, dispatcher=self._dispatcher, policy=self._policy
        )._authorize(actor=actor, resource_id=command.company_id, now=now)
        with self._session_factory() as session:
            document = session.scalar(
                sa.select(EnterpriseDocumentRecord).where(
                    EnterpriseDocumentRecord.tenant_id == actor.tenant_id,
                    EnterpriseDocumentRecord.company_id == command.company_id,
                    EnterpriseDocumentRecord.id == command.document_id,
                )
            )
        if document is None:
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        return self._dispatcher.dispatch(command=command, context=self._context(actor, now))

    def _finalize_clean_upload(
        self, *, actor: ActorContext, target: EnterpriseUploadTarget
    ) -> None:
        self._dispatcher.dispatch(
            command=FinalizeEnterpriseDocumentUploadCommand(
                command_id=uuid5(NAMESPACE_URL, f"enterprise-finalize:{target.upload_id}"),
                idempotency_key=uuid5(NAMESPACE_URL, f"enterprise-finalize-key:{target.upload_id}"),
                correlation_id=actor.correlation_id,
                upload_id=target.upload_id,
                company_id=target.company_id,
                document_id=target.document_id,
            ),
            context=self._context(actor, datetime.now(tz=UTC)),
        )

    def _reject(self, *, upload_id: UUID, code: str) -> None:
        with self._session_factory() as session:
            row = session.scalar(
                sa.select(EnterpriseDocumentUploadRecord)
                .where(EnterpriseDocumentUploadRecord.id == upload_id)
                .with_for_update()
            )
            if row is not None:
                row.state = "REJECTED"
                row.rejection_code = code
                session.commit()

    @staticmethod
    def _context(actor: ActorContext, now: datetime) -> CommandContext:
        return CommandContext(
            tenant_id=actor.tenant_id,
            actor_id=actor.actor_id,
            actor_kind=actor.actor_kind.value,
            received_at=now,
            identity_id=actor.identity_id,
            membership_id=actor.membership_id,
            session_id=actor.session_id,
            correlation_id=actor.correlation_id,
        )


class PrepareEnterpriseDocumentUploadHandler:
    def execute(
        self,
        *,
        session: Session,
        command: PrepareEnterpriseDocumentUploadCommand,
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
        existing = session.scalar(
            sa.select(EnterpriseDocumentUploadRecord)
            .where(
                EnterpriseDocumentUploadRecord.tenant_id == context.tenant_id,
                EnterpriseDocumentUploadRecord.id == command.upload_id,
            )
            .with_for_update()
        )
        if existing is not None:
            raise CommandExecutionError("ENTERPRISE_UPLOAD_ALREADY_EXISTS")
        session.add(
            EnterpriseDocumentUploadRecord(
                id=command.upload_id,
                tenant_id=context.tenant_id,
                company_id=command.company_id,
                document_id=command.document_id,
                document_kind=command.document_kind,
                document_label=command.document_label,
                original_filename=command.original_filename,
                storage_key=command.storage_key,
                expected_byte_size=command.expected_byte_size,
                state="AWAITING_UPLOAD",
                expires_at=command.expires_at,
                created_by_membership_id=context.membership_id,
                command_id=command.command_id,
                idempotency_key=command.idempotency_key,
                correlation_id=command.correlation_id,
            )
        )
        return HandlerOutcome(
            result_code="ENTERPRISE_DOCUMENT_UPLOAD_PREPARED",
            aggregate_refs=(
                {
                    "aggregate_type": "EnterpriseDocumentUpload",
                    "aggregate_id": str(command.upload_id),
                    "aggregate_revision": 0,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="EnterpriseDocumentUpload",
                    aggregate_id=command.upload_id,
                    aggregate_revision=0,
                    event_type="EnterpriseDocumentUploadPrepared",
                    payload={
                        "upload_id": str(command.upload_id),
                        "company_id": str(command.company_id),
                        "document_id": str(command.document_id),
                    },
                ),
            ),
        )


class FinalizeEnterpriseDocumentUploadHandler:
    def execute(
        self,
        *,
        session: Session,
        command: FinalizeEnterpriseDocumentUploadCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        if context.actor_kind != ActorKind.PATRON_ADMIN.value or context.membership_id is None:
            raise CommandExecutionError("ENTERPRISE_LIBRARY_PATRON_REQUIRED")
        upload = session.scalar(
            sa.select(EnterpriseDocumentUploadRecord)
            .where(
                EnterpriseDocumentUploadRecord.tenant_id == context.tenant_id,
                EnterpriseDocumentUploadRecord.id == command.upload_id,
                EnterpriseDocumentUploadRecord.company_id == command.company_id,
                EnterpriseDocumentUploadRecord.document_id == command.document_id,
            )
            .with_for_update()
        )
        if upload is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if upload.state != "CLEAN" or upload.sha256 is None:
            raise CommandExecutionError("DOCUMENT_UPLOAD_NOT_CLEAN")
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
        existing = session.scalar(
            sa.select(EnterpriseDocumentRecord).where(
                EnterpriseDocumentRecord.tenant_id == context.tenant_id,
                EnterpriseDocumentRecord.id == command.document_id,
            )
        )
        if existing is not None:
            raise CommandExecutionError("ENTERPRISE_DOCUMENT_ALREADY_EXISTS")
        session.add(
            EnterpriseDocumentRecord(
                id=command.document_id,
                tenant_id=context.tenant_id,
                company_id=command.company_id,
                document_kind=upload.document_kind,
                document_label=upload.document_label,
                storage_object_id=command.upload_id,
                original_filename=upload.original_filename,
                issued_at=min(
                    context.received_at, upload.expires_at - timedelta(microseconds=1)
                ),
                expires_at=upload.expires_at,
                sha256=upload.sha256,
                verification_status="PENDING",
                registered_by_membership_id=context.membership_id,
                command_id=command.command_id,
                idempotency_key=command.idempotency_key,
                correlation_id=command.correlation_id,
            )
        )
        company.aggregate_revision += 1
        return HandlerOutcome(
            result_code="ENTERPRISE_DOCUMENT_REGISTERED",
            aggregate_refs=(
                {
                    "aggregate_type": "EnterpriseCompany",
                    "aggregate_id": str(company.id),
                    "aggregate_revision": company.aggregate_revision,
                },
                {
                    "aggregate_type": "EnterpriseDocument",
                    "aggregate_id": str(command.document_id),
                    "aggregate_revision": 0,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="EnterpriseCompany",
                    aggregate_id=company.id,
                    aggregate_revision=company.aggregate_revision,
                    event_type="EnterpriseDocumentRegistered",
                    payload={
                        "company_id": str(company.id),
                        "document_id": str(command.document_id),
                        "source": "PRIVATE_UPLOAD_CLEAN",
                    },
                ),
            ),
        )


class VerifyEnterpriseDocumentHandler:
    def execute(
        self, *, session: Session, command: VerifyEnterpriseDocumentCommand, context: CommandContext
    ) -> HandlerOutcome:
        if context.actor_kind != ActorKind.PATRON_ADMIN.value or context.membership_id is None:
            raise CommandExecutionError("ENTERPRISE_LIBRARY_PATRON_REQUIRED")
        document = session.scalar(
            sa.select(EnterpriseDocumentRecord).where(
                EnterpriseDocumentRecord.tenant_id == context.tenant_id,
                EnterpriseDocumentRecord.company_id == command.company_id,
                EnterpriseDocumentRecord.id == command.document_id,
            )
        )
        if document is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        upload = session.scalar(
            sa.select(EnterpriseDocumentUploadRecord).where(
                EnterpriseDocumentUploadRecord.tenant_id == context.tenant_id,
                EnterpriseDocumentUploadRecord.document_id == command.document_id,
                EnterpriseDocumentUploadRecord.state == "CLEAN",
            )
        )
        if upload is None:
            raise CommandExecutionError("DOCUMENT_UPLOAD_NOT_CLEAN")
        current_record = session.scalar(
            sa.select(EnterpriseDocumentVerificationRecord)
            .where(
                EnterpriseDocumentVerificationRecord.tenant_id == context.tenant_id,
                EnterpriseDocumentVerificationRecord.document_id == command.document_id,
            )
            .order_by(EnterpriseDocumentVerificationRecord.revision.desc())
            .limit(1)
            .with_for_update()
        )
        current_revision = 0 if current_record is None else current_record.revision
        if current_revision != command.expected_verification_revision:
            raise CommandExecutionError("VERSION_CONFLICT")
        revision = 0 if current_record is None else current_revision + 1
        session.add(
            EnterpriseDocumentVerificationRecord(
                id=UUID(int=command.command_id.int),
                tenant_id=context.tenant_id,
                document_id=command.document_id,
                revision=revision,
                outcome=command.outcome,
                reason_code=command.reason_code,
                membership_id=context.membership_id,
                command_id=command.command_id,
                idempotency_key=command.idempotency_key,
                correlation_id=command.correlation_id,
            )
        )
        return HandlerOutcome(
            result_code="ENTERPRISE_DOCUMENT_VERIFIED",
            aggregate_refs=(
                {
                    "aggregate_type": "EnterpriseDocument",
                    "aggregate_id": str(command.document_id),
                    "aggregate_revision": revision,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="EnterpriseDocument",
                    aggregate_id=command.document_id,
                    aggregate_revision=revision,
                    event_type="EnterpriseDocumentVerified",
                    payload={
                        "document_id": str(command.document_id),
                        "outcome": command.outcome,
                        "resulting_revision": revision,
                    },
                ),
            ),
        )


def enterprise_upload_handlers() -> dict[str, CommandHandler]:
    return {
        "PrepareEnterpriseDocumentUpload": PrepareEnterpriseDocumentUploadHandler(),
        "FinalizeEnterpriseDocumentUpload": FinalizeEnterpriseDocumentUploadHandler(),
        "VerifyEnterpriseDocument": VerifyEnterpriseDocumentHandler(),
    }
