from __future__ import annotations

import asyncio

import pytest
from app.modules.pricing.application.file_security import (
    LibmagicClamdPricingFileSecurity,
    _clamd_verdict,
)


def test_clamd_verdict_mapping_is_conservative() -> None:
    assert _clamd_verdict(b"stream: OK\x00") == "CLEAN"
    assert _clamd_verdict(b"stream: Eicar-Test-Signature FOUND\x00") == "FOUND"
    assert _clamd_verdict(b"unexpected\x00") == "ERROR"


def test_pricing_security_accepts_signature_and_clean_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = LibmagicClamdPricingFileSecurity(
        host="clamav",
        port=3310,
        timeout_seconds=3,
    )
    monkeypatch.setattr(
        "app.modules.pricing.application.file_security.magic.from_buffer",
        lambda payload, mime=True: "application/zip",
    )

    async def clean_scan(payload: bytes) -> tuple[str, str]:
        assert payload == b"xlsx-bytes"
        return "CLEAN", "ClamAV 1.4"

    monkeypatch.setattr(adapter, "_scan", clean_scan)
    result = asyncio.run(
        adapter.inspect(
            payload=b"xlsx-bytes",
            filename="pricing.xlsx",
            content_type="application/octet-stream",
        )
    )

    assert result.detected_media_type == "application/zip"
    assert result.malware_verdict == "CLEAN"
    assert result.scanner_signature_version == "ClamAV 1.4"
    assert result.scanned_at.tzinfo is not None


def test_pricing_security_rejects_signature_before_clamd(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = LibmagicClamdPricingFileSecurity(
        host="clamav",
        port=3310,
        timeout_seconds=3,
    )
    monkeypatch.setattr(
        "app.modules.pricing.application.file_security.magic.from_buffer",
        lambda payload, mime=True: "text/plain",
    )

    with pytest.raises(ValueError, match="IMPORT_SIGNATURE_REJECTED"):
        asyncio.run(
            adapter.inspect(
                payload=b"not-xlsx",
                filename="pricing.xlsx",
                content_type=None,
            )
        )


def test_pricing_security_rejects_malware(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = LibmagicClamdPricingFileSecurity(
        host="clamav",
        port=3310,
        timeout_seconds=3,
    )
    monkeypatch.setattr(
        "app.modules.pricing.application.file_security.magic.from_buffer",
        lambda payload, mime=True: "application/zip",
    )

    async def infected_scan(payload: bytes) -> tuple[str, str]:
        return "FOUND", "ClamAV 1.4"

    monkeypatch.setattr(adapter, "_scan", infected_scan)
    with pytest.raises(ValueError, match="IMPORT_MALWARE_DETECTED"):
        asyncio.run(
            adapter.inspect(
                payload=b"eicar",
                filename="pricing.xlsx",
                content_type=None,
            )
        )
