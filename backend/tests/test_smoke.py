from app.bootstrap.application import create_app


def test_application_exposes_healthcheck() -> None:
    app = create_app()
    assert any(getattr(route, "path", None) == "/healthz" for route in app.routes)
