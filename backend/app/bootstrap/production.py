from __future__ import annotations

import os

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.bootstrap.application import AppRuntime, create_app
from app.interfaces.http.routes.authentication import AuthenticationHttpRuntime
from app.platform.security.authentication import (
    Argon2idPasswordVerifier,
    AuthenticationService,
    SecureOpaqueTokenGenerator,
    UtcClock,
)
from app.platform.security.tokens import JwtAccessTokenCodec


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or value.startswith("REPLACE_WITH_"):
        raise RuntimeError(f"required production setting is missing: {name}")
    return value


def build_production_app():
    database_url = _required("SMART_AO_DATABASE_URL")
    signing_key = _required("SMART_AO_JWT_SIGNING_KEY")
    issuer = _required("SMART_AO_JWT_ISSUER")
    audience = _required("SMART_AO_JWT_AUDIENCE")
    engine = sa.create_engine(
        database_url,
        pool_pre_ping=True,
        pool_recycle=1_800,
    )
    session_factory: sessionmaker[Session] = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )
    clock = UtcClock()
    authentication_runtime = AuthenticationHttpRuntime.create(
        authentication_service=AuthenticationService(
            session_factory=session_factory,
            password_verifier=Argon2idPasswordVerifier(),
            token_generator=SecureOpaqueTokenGenerator(),
            clock=clock,
        ),
        session_factory=session_factory,
        access_tokens=JwtAccessTokenCodec(
            signing_key=signing_key,
            issuer=issuer,
            audience=audience,
            clock=clock,
        ),
        csrf_token_generator=SecureOpaqueTokenGenerator(),
        clock=clock,
    )
    return create_app(
        runtime=AppRuntime.create(session_factory=session_factory),
        authentication_runtime=authentication_runtime,
    )


app = build_production_app()
