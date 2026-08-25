from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import magic

MAX_SCAN_CHUNK_BYTES = 64 * 1024
EXPECTED_MEDIA_TYPES = frozenset(
    {
        "application/zip",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
)


@dataclass(frozen=True, slots=True)
class PricingFileSecurityResult:
    detected_media_type: str
    malware_verdict: str
    scanner_signature_version: str
    scanned_at: datetime


class PricingFileSecurityPort(Protocol):
    async def inspect(
        self,
        *,
        payload: bytes,
        filename: str,
        content_type: str | None,
    ) -> PricingFileSecurityResult: ...


class LibmagicClamdPricingFileSecurity:
    """Checks the XLSX signature and scans its bytes through private clamd TCP."""

    def __init__(self, *, host: str, port: int, timeout_seconds: float) -> None:
        if not host:
            raise ValueError("clamd host is required")
        if not 1 <= port <= 65535:
            raise ValueError("clamd port is invalid")
        if not 0 < timeout_seconds <= 120:
            raise ValueError("clamd timeout is invalid")
        self._host = host
        self._port = port
        self._timeout_seconds = timeout_seconds

    async def inspect(
        self,
        *,
        payload: bytes,
        filename: str,
        content_type: str | None,
    ) -> PricingFileSecurityResult:
        if not filename.casefold().endswith(".xlsx") or filename.casefold().endswith(".xlsm"):
            raise ValueError("IMPORT_XLSX_REQUIRED")
        detected = str(await asyncio.to_thread(magic.from_buffer, payload, mime=True)).casefold()
        if detected not in EXPECTED_MEDIA_TYPES:
            raise ValueError("IMPORT_SIGNATURE_REJECTED")
        verdict, signature_version = await self._scan(payload)
        if verdict == "FOUND":
            raise ValueError("IMPORT_MALWARE_DETECTED")
        if verdict != "CLEAN":
            raise ValueError("IMPORT_MALWARE_SCAN_UNAVAILABLE")
        return PricingFileSecurityResult(
            detected_media_type=detected,
            malware_verdict=verdict,
            scanner_signature_version=signature_version,
            scanned_at=datetime.now(tz=UTC),
        )

    async def _scan(self, payload: bytes) -> tuple[str, str]:
        try:
            signature_version = await self._version()
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=self._timeout_seconds,
            )
            try:
                writer.write(b"zINSTREAM\x00")
                await writer.drain()
                for offset in range(0, len(payload), MAX_SCAN_CHUNK_BYTES):
                    chunk = payload[offset : offset + MAX_SCAN_CHUNK_BYTES]
                    writer.write(len(chunk).to_bytes(4, byteorder="big") + chunk)
                    await writer.drain()
                writer.write(b"\x00\x00\x00\x00")
                await writer.drain()
                response = await asyncio.wait_for(
                    reader.readuntil(b"\x00"), timeout=self._timeout_seconds
                )
            finally:
                writer.close()
                await writer.wait_closed()
            return _clamd_verdict(response), signature_version
        except Exception:
            return "ERROR", "unavailable"

    async def _version(self) -> str:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self._host, self._port),
            timeout=self._timeout_seconds,
        )
        try:
            writer.write(b"zVERSION\x00")
            await writer.drain()
            response = await asyncio.wait_for(
                reader.readuntil(b"\x00"), timeout=self._timeout_seconds
            )
            return response.rstrip(b"\x00").decode("utf-8", errors="replace")[:240]
        finally:
            writer.close()
            await writer.wait_closed()


def _clamd_verdict(response: bytes) -> str:
    normalized = response.rstrip(b"\x00").decode("utf-8", errors="replace").upper()
    if normalized.endswith("OK"):
        return "CLEAN"
    if "FOUND" in normalized:
        return "FOUND"
    return "ERROR"
