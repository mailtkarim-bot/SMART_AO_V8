"""Export the generated OpenAPI snapshot for SMART_AO V8 Assignment routes."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from app.bootstrap.application import AppRuntime, create_app
from app.interfaces.http.routes.authentication import AuthenticationHttpRuntime
from app.platform.security.authentication import AuthenticationService
from app.platform.security.tokens import JwtAccessTokenCodec
from sqlalchemy.orm import sessionmaker


class ExportClock:
    """Static clock sufficient to construct the non-executed HTTP dependencies."""

    def now(self) -> datetime:
        return datetime(2026, 8, 14, tzinfo=UTC)


class ExportPasswordVerifier:
    """Password verification is not invoked during OpenAPI schema generation."""

    def verify(self, *, password_hash: str, password: str) -> bool:
        return False


class ExportTokenGenerator:
    """Refresh token generation is not invoked during OpenAPI schema generation."""

    def generate(self) -> str:
        return "openapi-export-token"


def main() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    output_path = repository_root / "docs/reference/SMART_AO_V8_ASSIGNMENT_OPENAPI.json"
    clock = ExportClock()
    engine = sa.create_engine("postgresql+psycopg://smart_ao:smart_ao@127.0.0.1:5432/smart_ao")
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    tokens = JwtAccessTokenCodec(
        signing_key="openapi-export-signing-key-at-least-32-bytes",
        issuer="smart-ao-openapi",
        audience="smart-ao-web",
        clock=clock,
    )
    authentication_runtime = AuthenticationHttpRuntime.create(
        authentication_service=AuthenticationService(
            session_factory=sessions,
            password_verifier=ExportPasswordVerifier(),
            token_generator=ExportTokenGenerator(),
            clock=clock,
        ),
        session_factory=sessions,
        access_tokens=tokens,
        csrf_token_generator=ExportTokenGenerator(),
        clock=clock,
    )
    app = create_app(
        runtime=AppRuntime.create(session_factory=sessions),
        authentication_runtime=authentication_runtime,
    )
    assignment_paths = {
        path: operation
        for path, operation in app.openapi()["paths"].items()
        if path.startswith("/api/v1/assignments/")
    }
    payload = {
        "openapi": app.openapi()["openapi"],
        "info": app.openapi()["info"],
        "paths": assignment_paths,
        "components": app.openapi()["components"],
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
