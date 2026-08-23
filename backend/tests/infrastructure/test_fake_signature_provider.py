from __future__ import annotations

from uuid import UUID

import pytest
from app.interfaces.http.routes.patron_submission_signature import _verify_callback_signature
from app.modules.submission.infrastructure.fake_signature_provider import (
    SignatureProviderTestAdapter,
)
from fastapi import HTTPException

SECRET = "test-signature-callback-secret-0123456789"  # pragma: allowlist secret
SIGNATURE_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001")
PACKAGE_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0002")
DELIVERY_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0003")


def test_test_provider_builds_a_closed_hmac_callback() -> None:
    callback = SignatureProviderTestAdapter(callback_secret=SECRET).build_callback(
        delivery_id=DELIVERY_ID,
        signature_id=SIGNATURE_ID,
        submission_package_id=PACKAGE_ID,
    )

    assert callback.payload.provider == "TEST_PROVIDER"
    assert callback.payload.outcome == "SIGNED"
    assert callback.payload.delivery_id == DELIVERY_ID
    assert callback.payload.model_dump(mode="json").keys() == {
        "delivery_id",
        "submission_package_id",
        "provider",
        "provider_reference_hash",
        "signature_sha256",
        "outcome",
    }
    assert callback.body == callback.payload.model_dump_json().encode("utf-8")
    assert callback.signature_header.startswith("sha256=")
    assert len(callback.signature_header) == 71


def test_test_provider_is_deterministic_for_same_delivery() -> None:
    provider = SignatureProviderTestAdapter(callback_secret=SECRET)
    first = provider.build_callback(
        delivery_id=DELIVERY_ID,
        signature_id=SIGNATURE_ID,
        submission_package_id=PACKAGE_ID,
    )
    second = provider.build_callback(
        delivery_id=DELIVERY_ID,
        signature_id=SIGNATURE_ID,
        submission_package_id=PACKAGE_ID,
    )

    assert first.body == second.body
    assert first.signature_header == second.signature_header


def test_test_provider_callback_matches_raw_body_hmac_verification() -> None:
    callback = SignatureProviderTestAdapter(callback_secret=SECRET).build_callback(
        delivery_id=DELIVERY_ID,
        signature_id=SIGNATURE_ID,
        submission_package_id=PACKAGE_ID,
    )

    _verify_callback_signature(
        secret=SECRET,
        signature_header=callback.signature_header,
        body=callback.body,
    )

    with pytest.raises(HTTPException) as error:
        _verify_callback_signature(
            secret=SECRET,
            signature_header=callback.signature_header,
            body=callback.body + b" ",
        )
    assert error.value.status_code == 401


def test_test_provider_rejects_a_weak_secret() -> None:
    with pytest.raises(ValueError, match="32"):
        SignatureProviderTestAdapter(callback_secret="weak")  # pragma: allowlist secret
