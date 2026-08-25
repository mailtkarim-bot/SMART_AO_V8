from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from app.platform.persistence.models import TenantRecord
from app.platform.security.models import (
    AuthSessionRecord,
    IdentityRecord,
    TenantMembershipRecord,
    TotpFactorRecord,
    TotpRecoveryCodeRecord,
)
from app.platform.security.totp import (
    TotpService,
    TotpVerificationError,
    _matching_counter,
    _otpauth_uri,
    _totp_code,
)
from cryptography.fernet import Fernet
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)


def test_totp_matches_rfc6238_sha1_vector() -> None:
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # pragma: allowlist secret
    assert _totp_code(secret, 59 // 30) == "287082"
    assert _matching_counter(secret=secret, code="287082", now=datetime.fromtimestamp(59, UTC)) == 1


def test_otpauth_uri_is_standard_and_encodes_account() -> None:
    uri = _otpauth_uri(
        secret="JBSWY3DPEHPK3PXP",  # pragma: allowlist secret
        issuer="SMART_AO",
        account="patron@example.test",
    )
    assert uri.startswith("otpauth://totp/SMART_AO%3Apatron%40example.test?")
    assert "secret=JBSWY3DPEHPK3PXP" in uri
    assert "issuer=SMART_AO" in uri
    assert "digits=6" in uri
    assert "period=30" in uri


def _seed_identity(engine: Engine) -> tuple[UUID, UUID]:
    tenant_id = uuid4()
    identity_id = uuid4()
    membership_id = uuid4()
    session_id = uuid4()
    with Session(engine) as session:
        session.add(
            TenantRecord(id=tenant_id, slug=f"totp-{tenant_id.hex[:16]}", lifecycle="ACTIVE")
        )
        session.add(
            IdentityRecord(
                id=identity_id,
                email_normalized=f"patron-{identity_id.hex[:12]}@example.test",
                lifecycle="ACTIVE",
                email_verified_at=NOW,
            )
        )
        session.flush()
        session.add(
            TenantMembershipRecord(
                id=membership_id,
                tenant_id=tenant_id,
                identity_id=identity_id,
                role="PATRON_ADMIN",
                state="ACTIVE",
                activated_at=NOW,
                revoked_at=None,
            )
        )
        session.flush()
        session.add(
            AuthSessionRecord(
                id=session_id,
                tenant_id=tenant_id,
                membership_id=membership_id,
                identity_id=identity_id,
                state="ACTIVE",
                auth_strength="PASSWORD",
                token_version=1,
                issued_at=NOW,
                last_seen_at=NOW,
                expires_at=NOW + timedelta(hours=8),
                absolute_expires_at=NOW + timedelta(hours=12),
                mfa_verified_at=None,
                revoked_at=None,
                revoke_reason=None,
            )
        )
        session.commit()
    return identity_id, session_id


@pytest.mark.db
@pytest.mark.security
def test_totp_enrollment_confirmation_step_up_replay_recovery_and_disable(
    database_engine: Engine,
    session_factory: sessionmaker[Session],
) -> None:
    identity_id, session_id = _seed_identity(database_engine)
    service = TotpService(
        session_factory=session_factory,
        encryption_key=Fernet.generate_key().decode("ascii"),
    )

    enrollment = service.begin_enrollment(identity_id=identity_id, now=NOW)
    assert len(enrollment.recovery_codes) == 10
    assert all(len(code) == 14 for code in enrollment.recovery_codes)
    secret = enrollment.otpauth_uri.split("secret=", 1)[1].split("&", 1)[0]
    first_code = _totp_code(secret, int(NOW.timestamp()) // 30)

    service.confirm_enrollment(
        identity_id=identity_id,
        factor_id=enrollment.factor_id,
        code=first_code,
        now=NOW,
        session_id=session_id,
    )
    with Session(database_engine) as session:
        factor = session.get(TotpFactorRecord, enrollment.factor_id)
        auth_session = session.get(AuthSessionRecord, session_id)
        assert factor is not None and factor.state == "ACTIVE"
        assert auth_session is not None and auth_session.auth_strength == "MFA"
        assert auth_session.mfa_verified_at == NOW

    next_time = NOW + timedelta(seconds=30)
    next_code = _totp_code(secret, int(next_time.timestamp()) // 30)
    result = service.verify_step_up(session_id=session_id, code=next_code, now=next_time)
    assert not result.used_recovery_code
    with pytest.raises(TotpVerificationError, match="TOTP_CODE_INVALID"):
        service.verify_step_up(session_id=session_id, code=next_code, now=next_time)

    recovery_code = enrollment.recovery_codes[0]
    recovery_result = service.verify_step_up(
        session_id=session_id, code=recovery_code, now=next_time + timedelta(seconds=1)
    )
    assert recovery_result.used_recovery_code
    with pytest.raises(TotpVerificationError, match="TOTP_CODE_INVALID"):
        service.verify_step_up(
            session_id=session_id, code=recovery_code, now=next_time + timedelta(seconds=2)
        )

    service.disable(
        identity_id=identity_id,
        code=_totp_code(secret, int(next_time.timestamp()) // 30 + 1),
        now=next_time + timedelta(seconds=30),
    )
    with Session(database_engine) as session:
        factor = session.get(TotpFactorRecord, enrollment.factor_id)
        auth_session = session.get(AuthSessionRecord, session_id)
        assert factor is not None and factor.state == "DISABLED"
        assert auth_session is not None and auth_session.auth_strength == "PASSWORD"
        assert auth_session.mfa_verified_at is None
        assert session.scalar(
            sa.select(sa.func.count()).select_from(TotpRecoveryCodeRecord)
        ) == 10
