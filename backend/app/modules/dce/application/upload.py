"""DCE-UPLOAD-01 ports and orchestration; binary data never enters a command payload."""

from __future__ import annotations

from collections.abc import AsyncIterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid5

from app.modules.dce.application.commands import (
    ClaimDceStagedObjectUploadCommand,
    RecordDceStagedObjectQuarantineCommand,
    RecordDceStagedObjectScanCommand,
    RejectDceStagedObjectUploadCommand,
)
from app.platform.events.dispatcher import (
    CommandContext,
    CommandDispatcher,
    CommandExecutionError,
)

SYSTEM_UPLOAD_ACTOR_ID = UUID("00000000-0000-0000-0000-000000000011")


class DceUploadError(RuntimeError):
    """Base error intentionally free of storage, scanner and document details."""


class DceUploadAlreadyClaimedError(DceUploadError):
    """Raised when an object is no longer safely reusable for another byte stream."""


class DceUploadRejectedError(DceUploadError):
    """Raised after a terminal fail-closed rejection was durably recorded."""

    def __init__(self, *, status_code: int = 422) -> None:
        super().__init__("UPLOAD_REJECTED")
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class QuarantineWriteResult:
    """Facts calculated from the bytes actually written to private quarantine."""

    byte_size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class MalwareScanResult:
    """Normalized scanner verdict; transport failures are represented as ERROR."""

    verdict: str
    scanner_name: str
    scanner_signature_version: str
    scanned_at: datetime


@dataclass(frozen=True, slots=True)
class DceUploadResult:
    """Minimal service result suitable for the deliberately sparse HTTP response."""

    storage_object_id: UUID
    state: str


class DceQuarantineStoragePort(Protocol):
    """Private object storage; callers receive no path, URL or bucket reference."""

    async def write(
        self,
        *,
        storage_key: str,
        stream: AsyncIterable[bytes],
        max_bytes: int,
    ) -> QuarantineWriteResult: ...

    async def delete(self, *, storage_key: str) -> None: ...

    async def local_path(self, *, storage_key: str): ...


class DceContentInspectionPort(Protocol):
    """Determines the actual media type from stored bytes, never from a request header."""

    async def detect_media_type(self, *, storage_key: str) -> str: ...


class DceMalwareScanPort(Protocol):
    """Scans private content; an unavailable scanner returns a fail-closed ERROR verdict."""

    async def scan(self, *, storage_key: str) -> MalwareScanResult: ...


class DceUploadService:
    """Coordinates short DB transactions around a streamed private side effect."""

    def __init__(
        self,
        *,
        dispatcher: CommandDispatcher,
        storage: DceQuarantineStoragePort,
        inspector: DceContentInspectionPort,
        scanner: DceMalwareScanPort,
        allowed_media_types: frozenset[str],
        max_bytes: int = 2_000_000_000,
    ) -> None:
        self._dispatcher = dispatcher
        self._storage = storage
        self._inspector = inspector
        self._scanner = scanner
        self._allowed_media_types = allowed_media_types
        self._max_bytes = max_bytes

    async def upload(
        self,
        *,
        tenant_id: UUID,
        actor_id: UUID,
        actor_kind: str,
        storage_object_id: UUID,
        storage_key: str,
        expected_byte_size: int,
        idempotency_key: UUID,
        stream: AsyncIterable[bytes],
        content_length: int | None,
    ) -> DceUploadResult:
        """Receive one stream; every failure leaves the staged object non-admissible."""

        received_at = datetime.now(tz=UTC)
        user_context = CommandContext(
            tenant_id=tenant_id,
            actor_id=actor_id,
            actor_kind=actor_kind,
            received_at=received_at,
        )
        try:
            claim_result = self._dispatcher.dispatch(
                command=ClaimDceStagedObjectUploadCommand(
                    command_id=_system_command_id(storage_object_id, "claim", idempotency_key),
                    idempotency_key=idempotency_key,
                    correlation_id=idempotency_key,
                    storage_object_id=storage_object_id,
                ),
                context=user_context,
            )
        except CommandExecutionError as error:
            raise DceUploadAlreadyClaimedError() from error
        if claim_result.replayed:
            raise DceUploadAlreadyClaimedError()

        if content_length is not None and content_length > self._max_bytes:
            await self._reject_before_quarantine(
                tenant_id=tenant_id,
                storage_object_id=storage_object_id,
                rejection_code="UPLOAD_LIMIT_EXCEEDED",
            )
            raise DceUploadRejectedError(status_code=413)

        try:
            write_result = await self._storage.write(
                storage_key=storage_key,
                stream=stream,
                max_bytes=self._max_bytes,
            )
        except DceUploadRejectedError:
            await self._reject_before_quarantine(
                tenant_id=tenant_id,
                storage_object_id=storage_object_id,
                rejection_code="UPLOAD_LIMIT_EXCEEDED",
            )
            raise
        except Exception as error:
            await self._reject_before_quarantine(
                tenant_id=tenant_id,
                storage_object_id=storage_object_id,
                rejection_code="STORAGE_WRITE_FAILED",
            )
            raise DceUploadRejectedError() from error

        if write_result.byte_size == 0:
            await self._delete_quarantine(storage_key=storage_key)
            await self._reject_before_quarantine(
                tenant_id=tenant_id,
                storage_object_id=storage_object_id,
                rejection_code="UPLOAD_INTERRUPTED",
            )
            raise DceUploadRejectedError()

        try:
            media_type = await self._inspector.detect_media_type(storage_key=storage_key)
        except Exception as error:
            await self._delete_quarantine(storage_key=storage_key)
            await self._reject_before_quarantine(
                tenant_id=tenant_id,
                storage_object_id=storage_object_id,
                rejection_code="INSPECTION_ERROR",
            )
            raise DceUploadRejectedError() from error

        content_allowed = media_type in self._allowed_media_types
        self._record_quarantine(
            tenant_id=tenant_id,
            storage_object_id=storage_object_id,
            actual_byte_size=write_result.byte_size,
            sha256=write_result.sha256,
            media_type=media_type,
            content_allowed=content_allowed,
        )
        if write_result.byte_size != expected_byte_size or not content_allowed:
            await self._delete_quarantine(storage_key=storage_key)
            raise DceUploadRejectedError()

        scan_result = await self._scan(storage_key=storage_key)
        final_state = self._record_scan(
            tenant_id=tenant_id,
            storage_object_id=storage_object_id,
            actual_byte_size=write_result.byte_size,
            sha256=write_result.sha256,
            media_type=media_type,
            scan_result=scan_result,
        )
        if final_state != "CLEAN":
            await self._delete_quarantine(storage_key=storage_key)
            raise DceUploadRejectedError()
        if write_result.byte_size != expected_byte_size:
            raise DceUploadRejectedError()
        return DceUploadResult(storage_object_id=storage_object_id, state="CLEAN")

    def _record_quarantine(
        self,
        *,
        tenant_id: UUID,
        storage_object_id: UUID,
        actual_byte_size: int,
        sha256: str,
        media_type: str,
        content_allowed: bool,
    ) -> None:
        self._dispatcher.dispatch(
            command=RecordDceStagedObjectQuarantineCommand(
                command_id=_system_command_id(storage_object_id, "quarantine"),
                idempotency_key=_system_command_id(storage_object_id, "quarantine-receipt"),
                correlation_id=storage_object_id,
                storage_object_id=storage_object_id,
                actual_byte_size=actual_byte_size,
                sha256=sha256,
                media_type=media_type,
                content_allowed=content_allowed,
            ),
            context=_system_context(tenant_id=tenant_id),
        )

    def _record_scan(
        self,
        *,
        tenant_id: UUID,
        storage_object_id: UUID,
        actual_byte_size: int,
        sha256: str,
        media_type: str,
        scan_result: MalwareScanResult,
    ) -> str:
        self._dispatcher.dispatch(
            command=RecordDceStagedObjectScanCommand(
                command_id=_system_command_id(storage_object_id, "scan"),
                idempotency_key=_system_command_id(storage_object_id, "scan-receipt"),
                correlation_id=storage_object_id,
                storage_object_id=storage_object_id,
                actual_byte_size=actual_byte_size,
                sha256=sha256,
                media_type=media_type,
                scan_verdict=scan_result.verdict,
                scanner_name=scan_result.scanner_name,
                scanner_signature_version=scan_result.scanner_signature_version,
                scanned_at=scan_result.scanned_at,
            ),
            context=_system_context(tenant_id=tenant_id),
        )
        return "CLEAN" if scan_result.verdict == "CLEAN" else "REJECTED"

    async def _reject_before_quarantine(
        self,
        *,
        tenant_id: UUID,
        storage_object_id: UUID,
        rejection_code: str,
    ) -> None:
        try:
            self._dispatcher.dispatch(
                command=RejectDceStagedObjectUploadCommand(
                    command_id=_system_command_id(storage_object_id, f"reject:{rejection_code}"),
                    idempotency_key=_system_command_id(
                        storage_object_id,
                        f"reject-receipt:{rejection_code}",
                    ),
                    correlation_id=storage_object_id,
                    storage_object_id=storage_object_id,
                    rejection_code=rejection_code,
                ),
                context=_system_context(tenant_id=tenant_id),
            )
        except CommandExecutionError:
            return

    async def _delete_quarantine(self, *, storage_key: str) -> None:
        try:
            await self._storage.delete(storage_key=storage_key)
        except Exception:
            return

    async def _scan(self, *, storage_key: str) -> MalwareScanResult:
        try:
            return await self._scanner.scan(storage_key=storage_key)
        except Exception:
            return MalwareScanResult(
                verdict="ERROR",
                scanner_name="clamd",
                scanner_signature_version="unavailable",
                scanned_at=datetime.now(tz=UTC),
            )


def _system_context(*, tenant_id: UUID) -> CommandContext:
    return CommandContext(
        tenant_id=tenant_id,
        actor_id=SYSTEM_UPLOAD_ACTOR_ID,
        actor_kind="SYSTEM",
        received_at=datetime.now(tz=UTC),
    )


def _system_command_id(storage_object_id: UUID, operation: str, key: UUID | None = None) -> UUID:
    suffix = f"{operation}:{key}" if key is not None else operation
    return uuid5(storage_object_id, suffix)
