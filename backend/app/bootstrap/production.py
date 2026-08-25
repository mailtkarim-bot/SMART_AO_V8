from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.bootstrap.application import AppRuntime, create_app
from app.interfaces.http.routes.authentication import AuthenticationHttpRuntime
from app.modules.knowledge.infrastructure.factory import build_local_knowledge_service
from app.platform.observability.logging import configure_structured_logging
from app.platform.security.authentication import (
    Argon2idPasswordVerifier,
    AuthenticationService,
    SecureOpaqueTokenGenerator,
    UtcClock,
)
from app.platform.security.tokens import JwtAccessTokenCodec
from app.platform.security.totp import TotpService


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or value.startswith("REPLACE_WITH_"):
        raise RuntimeError(f"required production setting is missing: {name}")
    if name == "SMART_AO_JWT_SIGNING_KEY" and value.startswith("dev-only-"):
        raise RuntimeError("development JWT signing key is forbidden in production")
    return value


def _jwt_verification_keys() -> Mapping[str, str] | None:
    """Parse the optional non-logged key manifest used during JWT rotation."""

    raw_manifest = os.getenv("SMART_AO_JWT_VERIFICATION_KEYS_JSON", "").strip()
    if not raw_manifest:
        return None
    try:
        manifest = json.loads(raw_manifest)
    except json.JSONDecodeError as exc:
        raise RuntimeError("invalid SMART_AO_JWT_VERIFICATION_KEYS_JSON") from exc
    if not isinstance(manifest, dict) or not all(
        isinstance(key_id, str) and isinstance(key, str)
        for key_id, key in manifest.items()
    ):
        raise RuntimeError("JWT verification key manifest must be an object of strings")
    return manifest


def _totp_service_if_enabled(*, session_factory: sessionmaker[Session]) -> TotpService | None:
    raw_enabled = os.getenv("SMART_AO_MFA_ENABLED", "0").strip()
    if raw_enabled not in {"0", "1"}:
        raise RuntimeError("SMART_AO_MFA_ENABLED must be 0 or 1")
    if raw_enabled == "0":
        return None
    encryption_key = _required("SMART_AO_TOTP_ENCRYPTION_KEY")
    issuer = os.getenv("SMART_AO_TOTP_ISSUER", "SMART_AO").strip() or "SMART_AO"
    return TotpService(
        session_factory=session_factory,
        encryption_key=encryption_key,
        issuer=issuer,
    )


def _knowledge_service_if_enabled(*, session_factory: sessionmaker[Session]):
    if os.getenv("SMART_AO_RAG_ENABLED", "0") != "1":
        return None
    model_id = os.getenv("SMART_AO_BGE_MODEL_ID", "BAAI/bge-m3")
    cache_dir = os.getenv("SMART_AO_BGE_CACHE_DIR", "/var/lib/smart_ao/models")
    return build_local_knowledge_service(
        session_factory=session_factory,
        model_id=model_id,
        cache_dir=Path(cache_dir),
        local_files_only=os.getenv("SMART_AO_BGE_LOCAL_FILES_ONLY", "1") == "1",
    )


def build_production_app():
    configure_structured_logging()
    database_url = _required("SMART_AO_DATABASE_URL")
    signing_key = _required("SMART_AO_JWT_SIGNING_KEY")
    issuer = _required("SMART_AO_JWT_ISSUER")
    audience = _required("SMART_AO_JWT_AUDIENCE")
    signing_key_id = os.getenv("SMART_AO_JWT_KEY_ID", "active").strip() or "active"
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
            signing_key_id=signing_key_id,
            verification_keys=_jwt_verification_keys(),
        ),
        csrf_token_generator=SecureOpaqueTokenGenerator(),
        clock=clock,
        totp_service=_totp_service_if_enabled(session_factory=session_factory),
    )
    runtime = AppRuntime.create(session_factory=session_factory)
    return create_app(
        runtime=runtime,
        authentication_runtime=authentication_runtime,
        knowledge_service=_knowledge_service_if_enabled(session_factory=session_factory),
        public_notice_search=runtime.public_notice_search,
        company_registry=runtime.company_registry,
        expose_api_docs=False,
    )


app = build_production_app()
