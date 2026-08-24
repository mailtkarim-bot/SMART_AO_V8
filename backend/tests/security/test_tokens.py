from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from app.platform.security.tokens import (
    AccessTokenRejectedError,
    JwtAccessTokenCodec,
)


class FrozenClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def now(self) -> datetime:
        return self.current


NOW = datetime(2026, 8, 23, 20, 30, tzinfo=UTC)
ACTIVE_KEY = "a" * 48
OLD_KEY = "b" * 48


def make_codec(
    *,
    signing_key: str = ACTIVE_KEY,
    signing_key_id: str = "active",
    verification_keys: dict[str, str] | None = None,
) -> JwtAccessTokenCodec:
    return JwtAccessTokenCodec(
        signing_key=signing_key,
        issuer="smart-ao",
        audience="smart-ao-web",
        clock=FrozenClock(NOW),
        verification_keys=verification_keys,
        signing_key_id=signing_key_id,
    )


def test_issue_emits_kid_and_decode_accepts_active_key() -> None:
    codec = make_codec()
    token = codec.issue(identity_id=uuid4(), session_id=uuid4(), token_version=1)

    assert jwt.get_unverified_header(token)["kid"] == "active"
    assert codec.decode(token).token_version == 1


def test_decode_accepts_token_signed_by_previous_rotation_key() -> None:
    old_codec = make_codec(signing_key=OLD_KEY, signing_key_id="old")
    token = old_codec.issue(identity_id=uuid4(), session_id=uuid4(), token_version=2)
    current_codec = make_codec(verification_keys={"active": ACTIVE_KEY, "old": OLD_KEY})

    assert current_codec.decode(token).token_version == 2


def test_decode_rejects_unknown_key_id() -> None:
    payload = {
        "iss": "smart-ao",
        "aud": "smart-ao-web",
        "sub": str(uuid4()),
        "sid": str(uuid4()),
        "jti": str(uuid4()),
        "iat": int(NOW.timestamp()),
        "exp": int((NOW + timedelta(minutes=15)).timestamp()),
        "ver": 1,
    }
    token = jwt.encode(payload, ACTIVE_KEY, algorithm="HS256", headers={"kid": "retired"})

    with pytest.raises(AccessTokenRejectedError):
        make_codec().decode(token)


def test_decode_keeps_backward_compatibility_for_token_without_kid() -> None:
    payload = {
        "iss": "smart-ao",
        "aud": "smart-ao-web",
        "sub": str(uuid4()),
        "sid": str(uuid4()),
        "jti": str(uuid4()),
        "iat": int(NOW.timestamp()),
        "exp": int((NOW + timedelta(minutes=15)).timestamp()),
        "ver": 1,
    }
    token = jwt.encode(payload, ACTIVE_KEY, algorithm="HS256")

    assert make_codec().decode(token).token_version == 1


def test_constructor_rejects_invalid_key_identifier() -> None:
    with pytest.raises(ValueError, match="invalid characters"):
        make_codec(signing_key_id="active key")
