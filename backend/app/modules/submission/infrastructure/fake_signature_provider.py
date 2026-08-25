"""Deterministic provider double for signature callback tests.

This adapter never performs network I/O and must not be used as a production
provider. It only emits a valid callback body and its HMAC envelope.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from uuid import UUID

from app.modules.submission.public.signature_contracts import (
    RecordSubmissionSignatureCallbackRequest,
)


@dataclass(frozen=True, slots=True)
class TestSignatureCallback:
    payload: RecordSubmissionSignatureCallbackRequest
    body: bytes
    signature_header: str


class SignatureProviderTestAdapter:
    """Build deterministic, locally verifiable callbacks for integration tests."""

    provider = "TEST_PROVIDER"

    def __init__(self, *, callback_secret: str) -> None:
        normalized_secret = callback_secret.strip()
        if len(normalized_secret) < 32:
            raise ValueError("test provider callback secret must have at least 32 characters")
        self._callback_secret = normalized_secret.encode("utf-8")

    def build_callback(
        self,
        *,
        delivery_id: UUID,
        signature_id: UUID,
        submission_package_id: UUID,
        outcome: str = "SIGNED",
    ) -> TestSignatureCallback:
        provider_reference_hash = _digest(
            f"provider-reference:{signature_id}:{submission_package_id}:{delivery_id}"
        )
        signature_sha256 = _digest(f"signature:{signature_id}:{outcome}:{delivery_id}")
        payload = RecordSubmissionSignatureCallbackRequest(
            delivery_id=delivery_id,
            submission_package_id=submission_package_id,
            provider=self.provider,
            provider_reference_hash=provider_reference_hash,
            signature_sha256=signature_sha256,
            outcome=outcome,
        )
        body = payload.model_dump_json().encode("utf-8")
        digest = hmac.new(self._callback_secret, body, hashlib.sha256).hexdigest()
        return TestSignatureCallback(
            payload=payload,
            body=body,
            signature_header=f"sha256={digest}",
        )


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
