import importlib

import pytest
import sqlalchemy as sa


@pytest.fixture
def production_module(monkeypatch):
    monkeypatch.setenv("SMART_AO_DATABASE_URL", "postgresql" + "://test")
    monkeypatch.setenv("SMART_AO_JWT_SIGNING_KEY", "test-signing-key-at-least-32-bytes-long")
    monkeypatch.setenv("SMART_AO_JWT_ISSUER", "smart-ao-test")
    monkeypatch.setenv("SMART_AO_JWT_AUDIENCE", "smart-ao-web")
    monkeypatch.setattr(sa, "create_engine", lambda *args, **kwargs: object())
    return importlib.import_module("app.bootstrap.production")


def test_required_returns_trimmed_value(monkeypatch, production_module):
    monkeypatch.setenv("SMART_AO_TEST_SETTING", "  configured  ")

    assert production_module._required("SMART_AO_TEST_SETTING") == "configured"


@pytest.mark.parametrize(
    "value", [None, "", "   ", "REPLACE_WITH_SECRET", "REPLACE_WITH_DATABASE_URL"]
)
def test_required_rejects_missing_and_placeholder_values(monkeypatch, production_module, value):
    if value is None:
        monkeypatch.delenv("SMART_AO_TEST_SETTING", raising=False)
    else:
        monkeypatch.setenv("SMART_AO_TEST_SETTING", value)

    with pytest.raises(RuntimeError, match="SMART_AO_TEST_SETTING"):
        production_module._required("SMART_AO_TEST_SETTING")


def test_required_rejects_development_jwt_key(monkeypatch, production_module):
    monkeypatch.setenv("SMART_AO_JWT_SIGNING_KEY", "dev-only-signing-key-change-me-0123456789")

    with pytest.raises(RuntimeError, match="development JWT signing key"):
        production_module._required("SMART_AO_JWT_SIGNING_KEY")


def test_jwt_verification_key_manifest_is_optional_and_strict(monkeypatch, production_module):
    monkeypatch.delenv("SMART_AO_JWT_VERIFICATION_KEYS_JSON", raising=False)
    assert production_module._jwt_verification_keys() is None

    monkeypatch.setenv(
        "SMART_AO_JWT_VERIFICATION_KEYS_JSON",
        '{"previous":"' + ("x" * 32) + '"}',
    )
    assert production_module._jwt_verification_keys() == {"previous": "x" * 32}

    monkeypatch.setenv("SMART_AO_JWT_VERIFICATION_KEYS_JSON", "[]")
    with pytest.raises(RuntimeError, match="must be an object"):
        production_module._jwt_verification_keys()


def test_build_production_app_returns_fastapi_application(monkeypatch, production_module):
    monkeypatch.setattr(production_module.sa, "create_engine", lambda *args, **kwargs: object())

    application = production_module.build_production_app()

    assert application is not None
    assert application.title
    assert application.openapi_url is None
    assert application.docs_url is None
    assert application.redoc_url is None
    assert production_module.app is not None


def test_required_does_not_accept_placeholder_with_surrounding_whitespace(
    monkeypatch, production_module
):
    monkeypatch.setenv("SMART_AO_TEST_SETTING", "  REPLACE_WITH_VALUE  ")

    with pytest.raises(RuntimeError, match="required production setting"):
        production_module._required("SMART_AO_TEST_SETTING")



def test_totp_service_is_disabled_by_default(monkeypatch, production_module) -> None:
    monkeypatch.setenv("SMART_AO_MFA_ENABLED", "0")
    monkeypatch.delenv("SMART_AO_TOTP_ENCRYPTION_KEY", raising=False)

    assert production_module._totp_service_if_enabled(
        session_factory=production_module.sessionmaker()
    ) is None


def test_totp_service_requires_key_when_mfa_is_enabled(monkeypatch, production_module) -> None:
    monkeypatch.setenv("SMART_AO_MFA_ENABLED", "1")
    monkeypatch.delenv("SMART_AO_TOTP_ENCRYPTION_KEY", raising=False)

    with pytest.raises(RuntimeError, match="SMART_AO_TOTP_ENCRYPTION_KEY"):
        production_module._totp_service_if_enabled(
            session_factory=production_module.sessionmaker()
        )


def test_totp_service_is_constructed_from_out_of_band_key(monkeypatch, production_module) -> None:
    from cryptography.fernet import Fernet

    monkeypatch.setenv("SMART_AO_MFA_ENABLED", "1")
    monkeypatch.setenv(
        "SMART_AO_TOTP_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii")
    )
    monkeypatch.setenv("SMART_AO_TOTP_ISSUER", "SMART_AO_PREPROD")

    service = production_module._totp_service_if_enabled(
        session_factory=production_module.sessionmaker()
    )

    assert isinstance(service, production_module.TotpService)
