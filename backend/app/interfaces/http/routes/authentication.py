"""HTTP boundary for anonymous login and refresh flows with secure cookies."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session, sessionmaker

from app.platform.security.audit import (
    AuditEventType,
    AuditOutcome,
    AuditSeverity,
    SecurityAuditEntry,
    SecurityAuditWriter,
)
from app.platform.security.authenticated_context import (
    AuthenticationContextResolver,
    UnauthenticatedError,
)
from app.platform.security.authentication import (
    AuditedAuthenticationService,
    AuthenticationService,
    InvalidCredentialsError,
    RefreshRejectedError,
)
from app.platform.security.rate_limit import LoginRateLimiter
from app.platform.security.tokens import JwtAccessTokenCodec

_REFRESH_COOKIE_NAME = "smart_ao_refresh"
_CSRF_COOKIE_NAME = "smart_ao_csrf"
_CSRF_HEADER_NAME = "X-CSRF-Token"


class CsrfTokenGenerator(Protocol):
    """Generates an opaque double-submit CSRF token."""

    def generate(self) -> str: ...


class Clock(Protocol):
    """Provides the current time for cookie lifetime calculation."""

    def now(self) -> datetime: ...


@dataclass(frozen=True, slots=True)
class AuthenticationHttpRuntime:
    """Dependencies owned by the authentication HTTP boundary."""

    authentication_service: AuthenticationService | AuditedAuthenticationService
    session_factory: sessionmaker[Session]
    access_tokens: JwtAccessTokenCodec
    csrf_token_generator: CsrfTokenGenerator
    clock: Clock
    context_resolver: AuthenticationContextResolver
    rate_limiter: LoginRateLimiter = field(default_factory=LoginRateLimiter.from_environment)

    @classmethod
    def create(
        cls,
        *,
        authentication_service: AuthenticationService,
        session_factory: sessionmaker[Session],
        access_tokens: JwtAccessTokenCodec,
        csrf_token_generator: CsrfTokenGenerator,
        clock: Clock,
        rate_limiter: LoginRateLimiter | None = None,
    ) -> AuthenticationHttpRuntime:
        audited_service = (
            authentication_service
            if isinstance(authentication_service, AuditedAuthenticationService)
            else AuditedAuthenticationService(
                core=authentication_service,
                session_factory=session_factory,
                writer=SecurityAuditWriter(),
                clock=clock,
            )
        )
        return cls(
            authentication_service=audited_service,
            session_factory=session_factory,
            access_tokens=access_tokens,
            csrf_token_generator=csrf_token_generator,
            clock=clock,
            context_resolver=AuthenticationContextResolver(
                session_factory=session_factory,
                access_tokens=access_tokens,
                clock=clock,
            ),
            rate_limiter=rate_limiter or LoginRateLimiter.from_environment(),
        )


class LoginRequest(BaseModel):
    """Anonymous credential submission; tenant is selected only before session creation."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)
    tenant_id: UUID


class AccessTokenResponse(BaseModel):
    """Browser response that deliberately excludes the refresh-token value."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 900


def build_authentication_router(*, runtime: AuthenticationHttpRuntime) -> APIRouter:
    """Build anonymous authentication routes without coupling to business modules."""
    router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])

    @router.post("/login", response_model=AccessTokenResponse)
    def login(request: LoginRequest, http_request: Request) -> JSONResponse:
        source_ip = _source_ip(http_request)
        decision = runtime.rate_limiter.check(
            namespace="login",
            identity=request.email,
            source_ip=source_ip,
        )
        if not decision.allowed:
            _record_rate_limit_denial(
                runtime=runtime,
                event_type=AuditEventType.AUTH_LOGIN_DENIED,
                action="auth.login",
                source_ip=source_ip,
            )
            raise _rate_limited(decision.retry_after_seconds)
        try:
            result = runtime.authentication_service.login(
                email=request.email,
                password=request.password,
                tenant_id=request.tenant_id,
            )
        except InvalidCredentialsError as error:
            runtime.rate_limiter.record_failure(
                namespace="login",
                identity=request.email,
                source_ip=source_ip,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="INVALID_CREDENTIALS",
            ) from error

        runtime.rate_limiter.record_success(
            namespace="login",
            identity=request.email,
            source_ip=source_ip,
        )
        access_token = runtime.access_tokens.issue(
            identity_id=result.identity_id,
            session_id=result.session_id,
            token_version=result.token_version,
        )
        response = JSONResponse(
            status_code=status.HTTP_200_OK,
            content=AccessTokenResponse(access_token=access_token).model_dump(mode="json"),
        )
        _set_authentication_cookies(
            response,
            refresh_token=result.refresh_token,
            csrf_token=runtime.csrf_token_generator.generate(),
            max_age_seconds=_seconds_until(result.session_absolute_expires_at, runtime.clock.now()),
        )
        return response

    @router.post("/refresh", response_model=AccessTokenResponse)
    def refresh(
        request: Request,
        csrf_header: str | None = Header(default=None, alias=_CSRF_HEADER_NAME),
    ) -> JSONResponse:
        source_ip = _source_ip(request)
        decision = runtime.rate_limiter.check(
            namespace="refresh",
            identity=None,
            source_ip=source_ip,
        )
        if not decision.allowed:
            _record_rate_limit_denial(
                runtime=runtime,
                event_type=AuditEventType.AUTH_REFRESH_DENIED,
                action="auth.refresh",
                source_ip=source_ip,
            )
            raise _rate_limited(decision.retry_after_seconds)
        try:
            _require_csrf(request=request, csrf_header=csrf_header)
            refresh_token = request.cookies.get(_REFRESH_COOKIE_NAME)
            if refresh_token is None:
                raise RefreshRejectedError
            result = runtime.authentication_service.refresh(refresh_token=refresh_token)
        except HTTPException:
            runtime.rate_limiter.record_failure(
                namespace="refresh",
                identity=None,
                source_ip=source_ip,
            )
            raise
        except RefreshRejectedError as error:
            runtime.rate_limiter.record_failure(
                namespace="refresh",
                identity=None,
                source_ip=source_ip,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="REFRESH_REJECTED",
            ) from error

        runtime.rate_limiter.record_success(
            namespace="refresh",
            identity=None,
            source_ip=source_ip,
        )
        access_token = runtime.access_tokens.issue(
            identity_id=result.identity_id,
            session_id=result.session_id,
            token_version=result.token_version,
        )
        response = JSONResponse(
            status_code=status.HTTP_200_OK,
            content=AccessTokenResponse(access_token=access_token).model_dump(mode="json"),
        )
        _set_authentication_cookies(
            response,
            refresh_token=result.refresh_token,
            csrf_token=runtime.csrf_token_generator.generate(),
            max_age_seconds=_seconds_until(result.session_absolute_expires_at, runtime.clock.now()),
        )
        return response

    @router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
    def logout(
        request: Request,
        authorization: str | None = Header(default=None),
        csrf_header: str | None = Header(default=None, alias=_CSRF_HEADER_NAME),
    ) -> Response:
        context = _resolve_authenticated_context(
            authorization=authorization,
            context_resolver=runtime.context_resolver,
        )
        _require_csrf(request=request, csrf_header=csrf_header)
        if context.session_id is None or not runtime.authentication_service.logout(
            session_id=context.session_id
        ):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHENTICATED")
        response = Response(status_code=status.HTTP_204_NO_CONTENT)
        _clear_authentication_cookies(response)
        return response

    return router


def _source_ip(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


def _rate_limited(retry_after_seconds: int) -> HTTPException:
    error = HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="RATE_LIMITED",
    )
    error.headers = {"Retry-After": str(max(1, retry_after_seconds))}
    return error


def _record_rate_limit_denial(
    *,
    runtime: AuthenticationHttpRuntime,
    event_type: AuditEventType,
    action: str,
    source_ip: str,
) -> None:
    with runtime.session_factory.begin() as session:
        SecurityAuditWriter().record(
            session=session,
            entry=SecurityAuditEntry(
                occurred_at=runtime.clock.now(),
                tenant_id=None,
                actor_id=None,
                identity_id=None,
                session_id=None,
                actor_kind=None,
                auth_strength=None,
                event_type=event_type,
                outcome=AuditOutcome.DENIED,
                severity=AuditSeverity.WARNING,
                action=action,
                resource_type="AUTHENTICATION",
                resource_id=None,
                case_id=None,
                correlation_id=None,
                command_id=None,
                request_id=None,
                source_ip_hash=hashlib.sha256(source_ip.encode("utf-8")).hexdigest(),
                user_agent_family=None,
                reason_code="RATE_LIMITED",
                metadata={"channel": "http", "reason_class": "THROTTLE"},
            ),
        )


def _resolve_authenticated_context(
    *,
    authorization: str | None,
    context_resolver: AuthenticationContextResolver,
):
    if authorization is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHENTICATED")
    scheme, _, access_token = authorization.partition(" ")
    if scheme.casefold() != "bearer" or not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHENTICATED")
    try:
        return context_resolver.resolve(access_token=access_token)
    except UnauthenticatedError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="UNAUTHENTICATED",
        ) from error


def _require_csrf(*, request: Request, csrf_header: str | None) -> None:
    csrf_cookie = request.cookies.get(_CSRF_COOKIE_NAME)
    if (
        csrf_header is None
        or csrf_cookie is None
        or not hmac.compare_digest(csrf_header, csrf_cookie)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF_REJECTED")


def _set_authentication_cookies(
    response: JSONResponse,
    *,
    refresh_token: str,
    csrf_token: str,
    max_age_seconds: int,
) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=max_age_seconds,
        path="/api/v1/auth",
        secure=True,
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        key=_CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=max_age_seconds,
        path="/",
        secure=True,
        httponly=False,
        samesite="strict",
    )


def _clear_authentication_cookies(response: Response) -> None:
    response.delete_cookie(
        key=_REFRESH_COOKIE_NAME,
        path="/api/v1/auth",
        secure=True,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        key=_CSRF_COOKIE_NAME,
        path="/",
        secure=True,
        httponly=False,
        samesite="strict",
    )


def _seconds_until(expires_at: datetime, current: datetime) -> int:
    seconds = int((expires_at - current).total_seconds())
    return max(seconds, 1)
