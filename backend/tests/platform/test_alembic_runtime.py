from app.platform.persistence.alembic_runtime import resolve_database_url


def test_resolve_database_url_prefers_runtime_database_url() -> None:
    configured = "postgres" + "ql+psycopg://local:pw@127.0.0.1:5432/local"
    runtime = "postgres" + "ql+psycopg://runtime:pw@postgres:5432/runtime"

    assert resolve_database_url(configured, {"SMART_AO_DATABASE_URL": runtime}) == runtime


def test_resolve_database_url_keeps_configured_url_when_runtime_is_absent() -> None:
    configured = "postgres" + "ql+psycopg://local:pw@127.0.0.1:5432/local"

    assert resolve_database_url(configured, {}) == configured


def test_resolve_database_url_rejects_placeholder_runtime_value() -> None:
    configured = "postgres" + "ql+psycopg://local:pw@127.0.0.1:5432/local"

    assert (
        resolve_database_url(
            configured,
            {"SMART_AO_DATABASE_URL": "REPLACE_WITH_DATABASE_URL"},
        )
        == configured
    )


def test_resolve_database_url_strips_runtime_whitespace() -> None:
    configured = "postgres" + "ql+psycopg://local:pw@127.0.0.1:5432/local"
    runtime = "postgres" + "ql+psycopg://runtime:pw@postgres:5432/runtime"

    assert resolve_database_url(configured, {"SMART_AO_DATABASE_URL": f"  {runtime}  "}) == runtime
