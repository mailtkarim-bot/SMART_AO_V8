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
