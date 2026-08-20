"""Private quarantine storage and malware inspection ports."""

from __future__ import annotations

from collections.abc import AsyncIterable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class QuarantineWriteResult:
    """Facts calculated from bytes written to private quarantine."""

    byte_size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class MalwareScanResult:
    """Normalized scanner verdict with no raw scanner payload."""

    verdict: str
    scanner_name: str
    scanner_signature_version: str
    scanned_at: datetime


class QuarantineStoragePort(Protocol):
    """Private object storage that never exposes paths, URLs or buckets publicly."""

    async def write(
        self,
        *,
        storage_key: str,
        stream: AsyncIterable[bytes],
        max_bytes: int,
    ) -> QuarantineWriteResult: ...

    async def delete(self, *, storage_key: str) -> None: ...

    async def local_path(self, *, storage_key: str): ...


class ContentInspectionPort(Protocol):
    """Determine actual media type from private bytes, not request headers."""

    async def detect_media_type(self, *, storage_key: str) -> str: ...


class MalwareScanPort(Protocol):
    """Scan private content and fail closed when the scanner is unavailable."""

    async def scan(self, *, storage_key: str) -> MalwareScanResult: ...
