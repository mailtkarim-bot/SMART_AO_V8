"""Private local quarantine, signature inspection and ClamAV TCP adapters for DCE-UPLOAD-01."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from collections.abc import AsyncIterable
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from uuid import uuid4

import magic

from app.modules.dce.application.upload import (
    DceContentInspectionPort,
    DceMalwareScanPort,
    DceQuarantineStoragePort,
    DceUploadRejectedError,
    MalwareScanResult,
    QuarantineWriteResult,
)

logger = logging.getLogger(__name__)


class LocalQuarantineStorageAdapter(DceQuarantineStoragePort):
    """Stores private files under a restrictive local root; no path is public API data."""

    def __init__(self, *, root: Path) -> None:
        self._root = root.resolve()

    async def write(
        self,
        *,
        storage_key: str,
        stream: AsyncIterable[bytes],
        max_bytes: int,
    ) -> QuarantineWriteResult:
        target = self._path(storage_key=storage_key)
        temporary = target.parent / f".{target.name}.{uuid4().hex}.part"
        await asyncio.to_thread(target.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(os.chmod, target.parent, 0o700)
        if target.exists():
            raise FileExistsError("private quarantine object already exists")

        digest = hashlib.sha256()
        byte_size = 0
        handle = None
        try:
            handle = await asyncio.to_thread(_create_private_file, temporary)
            async for chunk in stream:
                if not isinstance(chunk, bytes):
                    raise TypeError("upload stream must yield bytes")
                if not chunk:
                    continue
                byte_size += len(chunk)
                if byte_size > max_bytes:
                    raise DceUploadRejectedError(status_code=413)
                digest.update(chunk)
                await asyncio.to_thread(handle.write, chunk)
            await asyncio.to_thread(handle.flush)
            await asyncio.to_thread(os.fsync, handle.fileno())
            await asyncio.to_thread(handle.close)
            handle = None
            await asyncio.to_thread(_replace_without_overwrite, temporary, target)
        except Exception:
            if handle is not None:
                await asyncio.to_thread(handle.close)
            await asyncio.to_thread(_unlink_missing_ok, temporary)
            raise
        return QuarantineWriteResult(byte_size=byte_size, sha256=digest.hexdigest())

    async def delete(self, *, storage_key: str) -> None:
        await asyncio.to_thread(_unlink_missing_ok, self._path(storage_key=storage_key))

    async def read_bytes(self, *, storage_key: str, max_bytes: int) -> bytes:
        path = self._path(storage_key=storage_key)
        size = await asyncio.to_thread(path.stat)
        if size.st_size > max_bytes:
            raise ValueError("private document exceeds extraction limit")
        return await asyncio.to_thread(path.read_bytes)

    async def local_path(self, *, storage_key: str) -> Path:
        return self._path(storage_key=storage_key)

    def _path(self, *, storage_key: str) -> Path:
        relative = PurePosixPath(storage_key)
        if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
            raise ValueError("invalid private storage key")
        candidate = (self._root / Path(*relative.parts)).resolve()
        if self._root not in candidate.parents and candidate != self._root:
            raise ValueError("private storage key escapes quarantine root")
        return candidate


class PythonMagicContentInspectionAdapter(DceContentInspectionPort):
    """Uses libmagic file signatures rather than extension or HTTP Content-Type."""

    def __init__(self, *, storage: DceQuarantineStoragePort) -> None:
        self._storage = storage

    async def detect_media_type(self, *, storage_key: str) -> str:
        file_path = await self._storage.local_path(storage_key=storage_key)
        detected = await asyncio.to_thread(magic.from_file, str(file_path), mime=True)
        return str(detected).casefold()


class ClamdTcpMalwareScanAdapter(DceMalwareScanPort):
    """Streams a private file to clamd over the Docker-internal TCP network only."""

    def __init__(
        self,
        *,
        storage: DceQuarantineStoragePort,
        host: str,
        port: int,
        timeout_seconds: float,
        chunk_size: int = 64 * 1024,
    ) -> None:
        self._storage = storage
        self._host = host
        self._port = port
        self._timeout_seconds = timeout_seconds
        self._chunk_size = chunk_size

    async def scan(self, *, storage_key: str) -> MalwareScanResult:
        scanned_at = datetime.now(tz=UTC)
        try:
            version = await self._version()
            file_path = await self._storage.local_path(storage_key=storage_key)
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=self._timeout_seconds,
            )
            try:
                writer.write(b"zINSTREAM\x00")
                await writer.drain()
                with file_path.open("rb") as file_handle:
                    while chunk := await asyncio.to_thread(file_handle.read, self._chunk_size):
                        writer.write(len(chunk).to_bytes(4, byteorder="big") + chunk)
                        await writer.drain()
                writer.write(b"\x00\x00\x00\x00")
                await writer.drain()
                response = await asyncio.wait_for(
                    reader.readuntil(b"\x00"),
                    timeout=self._timeout_seconds,
                )
            finally:
                writer.close()
                await writer.wait_closed()
            verdict = _clamd_verdict(response=response)
            return MalwareScanResult(
                verdict=verdict,
                scanner_name="clamd",
                scanner_signature_version=version,
                scanned_at=scanned_at,
            )
        except Exception as error:
            logger.warning(
                "dce_clamav_scan_failed",
                extra={"scanner_name": "clamd", "error_type": type(error).__name__},
            )
            return MalwareScanResult(
                verdict="ERROR",
                scanner_name="clamd",
                scanner_signature_version="unavailable",
                scanned_at=scanned_at,
            )

    async def _version(self) -> str:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self._host, self._port),
            timeout=self._timeout_seconds,
        )
        try:
            writer.write(b"zVERSION\x00")
            await writer.drain()
            response = await asyncio.wait_for(
                reader.readuntil(b"\x00"),
                timeout=self._timeout_seconds,
            )
            return response.rstrip(b"\x00").decode("utf-8", errors="replace")[:240]
        finally:
            writer.close()
            await writer.wait_closed()


def _create_private_file(path: Path):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    return os.fdopen(descriptor, "wb")


def _replace_without_overwrite(source: Path, target: Path) -> None:
    os.link(source, target)
    source.unlink()


def _unlink_missing_ok(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _clamd_verdict(*, response: bytes) -> str:
    normalized = response.rstrip(b"\x00").decode("utf-8", errors="replace").casefold().strip()
    if not normalized.startswith("stream:"):
        return "ERROR"
    verdict_text = normalized.partition(":")[2].strip()
    if verdict_text == "ok":
        return "CLEAN"
    if verdict_text.endswith(" found"):
        return "INFECTED"
    return "ERROR"
