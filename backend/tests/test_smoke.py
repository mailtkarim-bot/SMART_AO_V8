from app.bootstrap.application import create_app


def test_application_exposes_healthcheck() -> None:
    app = create_app()
    assert any(route.path == "/healthz" for route in app.routes)
