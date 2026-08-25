"""HTTP boundary for anonymous login and refresh flows with secure cookies."""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass, field
from datetime import datetime
from ipaddress import IPv4Network, IPv6Network, ip_address, ip_network
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
from app.platform.security.context import ActorContext
from app.platform.security.models import AuthSessionRecord
from app.platform.security.rate_limit import LoginRateLimiter
from app.platform.security.tokens import JwtAccessTokenCodec
from app.platform.security.totp import (
    TotpEnrollmentError,
    TotpService,
    TotpVerificationError,
)

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
    totp_service: TotpService | None = None
    trusted_proxy_networks: tuple[IPv4Network | IPv6Network, ...] = field(
        default_factory=lambda: _trusted_proxy_networks_from_environment()
    )

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
        trusted_proxy_networks: tuple[IPv4Network | IPv6Network, ...] | None = None,
        totp_service: TotpService | None = None,
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
            totp_service=(
                totp_service
                if totp_service is not None
                else TotpService.from_environment(session_factory=session_factory)
            ),
            trusted_proxy_networks=(
                trusted_proxy_networks
                if trusted_proxy_networks is not None
                else _trusted_proxy_networks_from_environment()
            ),
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


class CurrentActorResponse(BaseModel):
    """Minimal server-resolved identity facts safe for the browser shell."""

    actor_id: UUID
    identity_id: UUID
    actor_kind: str
    membership_state: str


class TotpCodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(min_length=6, max_length=32)


class TotpEnrollmentResponse(BaseModel):
    factor_id: UUID
    otpauth_uri: str
    recovery_codes: tuple[str, ...]
    expires_at: datetime


class TotpConfirmRequest(TotpCodeRequest):
    factor_id: UUID


class TotpStepUpResponse(AccessTokenResponse):
    used_recovery_code: bool = False


def build_authentication_router(*, runtime: AuthenticationHttpRuntime) -> APIRouter:
    """Build anonymous authentication routes without coupling to business modules."""
    router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])

    @router.post("/login", response_model=AccessTokenResponse)
    def login(request: LoginRequest, http_request: Request) -> JSONResponse:
        source_ip = _source_ip(
            http_request, trusted_proxy_networks=runtime.trusted_proxy_networks
        )
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
        source_ip = _source_ip(
            request, trusted_proxy_networks=runtime.trusted_proxy_networks
        )
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

    @router.post("/mfa/totp/enroll", response_model=TotpEnrollmentResponse)
    def begin_totp_enrollment(
        http_request: Request,
        authorization: str | None = Header(default=None),
        csrf_header: str | None = Header(default=None, alias=_CSRF_HEADER_NAME),
    ) -> TotpEnrollmentResponse:
        context = _resolve_authenticated_context(
            authorization=authorization,
            context_resolver=runtime.context_resolver,
        )
        _require_authenticated_session(context)
        _require_csrf(request=http_request, csrf_header=csrf_header)
        identity, source_ip = _mfa_rate_limit_identity(
            runtime=runtime, context=context, request=http_request, namespace="mfa-enroll"
        )
        decision = runtime.rate_limiter.check(
            namespace="mfa-enroll", identity=identity, source_ip=source_ip
        )
        if not decision.allowed:
            _record_mfa_rate_limit_denial(
                runtime=runtime, context=context, action="auth.mfa.enrollment.start"
            )
            raise _rate_limited(decision.retry_after_seconds)
        service = _require_totp_service(runtime)
        try:
            result = service.begin_enrollment(
                identity_id=context.identity_id,
                now=runtime.clock.now(),
            )
        except TotpEnrollmentError as error:
            runtime.rate_limiter.record_failure(
                namespace="mfa-enroll", identity=identity, source_ip=source_ip
            )
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        runtime.rate_limiter.record_success(
            namespace="mfa-enroll", identity=identity, source_ip=source_ip
        )
        _record_mfa_event(
            runtime=runtime,
            context=context,
            event_type=AuditEventType.AUTH_MFA_ENROLLMENT_STARTED,
            outcome=AuditOutcome.SUCCEEDED,
            severity=AuditSeverity.INFO,
            action="auth.mfa.enrollment.start",
            reason_code="MFA_ENROLLMENT_STARTED",
        )
        return TotpEnrollmentResponse(
            factor_id=result.factor_id,
            otpauth_uri=result.otpauth_uri,
            recovery_codes=result.recovery_codes,
            expires_at=result.expires_at,
        )

    @router.post("/mfa/totp/confirm", response_model=AccessTokenResponse)
    def confirm_totp_enrollment(
        request: TotpConfirmRequest,
        http_request: Request,
        authorization: str | None = Header(default=None),
        csrf_header: str | None = Header(default=None, alias=_CSRF_HEADER_NAME),
    ) -> JSONResponse:
        context = _resolve_authenticated_context(
            authorization=authorization,
            context_resolver=runtime.context_resolver,
        )
        _require_authenticated_session(context)
        _require_csrf(request=http_request, csrf_header=csrf_header)
        identity, source_ip = _mfa_rate_limit_identity(
            runtime=runtime, context=context, request=http_request, namespace="mfa"
        )
        decision = runtime.rate_limiter.check(
            namespace="mfa", identity=identity, source_ip=source_ip
        )
        if not decision.allowed:
            _record_mfa_rate_limit_denial(
                runtime=runtime, context=context, action="auth.mfa.enrollment.confirm"
            )
            raise _rate_limited(decision.retry_after_seconds)
        service = _require_totp_service(runtime)
        try:
            service.confirm_enrollment(
                identity_id=context.identity_id,
                factor_id=request.factor_id,
                code=request.code,
                now=runtime.clock.now(),
                session_id=context.session_id,
            )
        except TotpVerificationError as error:
            runtime.rate_limiter.record_failure(
                namespace="mfa", identity=identity, source_ip=source_ip
            )
            _record_mfa_event(
                runtime=runtime,
                context=context,
                event_type=AuditEventType.AUTH_MFA_VERIFICATION_DENIED,
                outcome=AuditOutcome.DENIED,
                severity=AuditSeverity.WARNING,
                action="auth.mfa.enrollment.confirm",
                reason_code=str(error),
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(error),
            ) from error
        runtime.rate_limiter.record_success(
            namespace="mfa", identity=identity, source_ip=source_ip
        )
        _record_mfa_event(
            runtime=runtime,
            context=context,
            event_type=AuditEventType.AUTH_MFA_ENROLLMENT_CONFIRMED,
            outcome=AuditOutcome.SUCCEEDED,
            severity=AuditSeverity.INFO,
            action="auth.mfa.enrollment.confirm",
            reason_code="MFA_ENROLLMENT_CONFIRMED",
        )
        return _issue_access_token_response(runtime=runtime, context=context, auth_strength="MFA")

    @router.post("/mfa/totp/step-up", response_model=TotpStepUpResponse)
    def verify_totp_step_up(
        request: TotpCodeRequest,
        http_request: Request,
        authorization: str | None = Header(default=None),
        csrf_header: str | None = Header(default=None, alias=_CSRF_HEADER_NAME),
    ) -> JSONResponse:
        context = _resolve_authenticated_context(
            authorization=authorization,
            context_resolver=runtime.context_resolver,
        )
        session_id = _require_authenticated_session(context)
        _require_csrf(request=http_request, csrf_header=csrf_header)
        source_ip = _source_ip(
            http_request, trusted_proxy_networks=runtime.trusted_proxy_networks
        )
        identity = str(context.identity_id)
        decision = runtime.rate_limiter.check(
            namespace="mfa", identity=identity, source_ip=source_ip
        )
        if not decision.allowed:
            raise _rate_limited(decision.retry_after_seconds)
        service = _require_totp_service(runtime)
        try:
            result = service.verify_step_up(
                session_id=session_id,
                code=request.code,
                now=runtime.clock.now(),
            )
        except TotpVerificationError as error:
            runtime.rate_limiter.record_failure(
                namespace="mfa", identity=identity, source_ip=source_ip
            )
            _record_mfa_event(
                runtime=runtime,
                context=context,
                event_type=AuditEventType.AUTH_MFA_VERIFICATION_DENIED,
                outcome=AuditOutcome.DENIED,
                severity=AuditSeverity.WARNING,
                action="auth.mfa.step_up",
                reason_code=str(error),
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(error),
            ) from error
        runtime.rate_limiter.record_success(
            namespace="mfa", identity=identity, source_ip=source_ip
        )
        _record_mfa_event(
            runtime=runtime,
            context=context,
            event_type=(
                AuditEventType.AUTH_MFA_RECOVERY_USED
                if result.used_recovery_code
                else AuditEventType.AUTH_MFA_STEP_UP_SUCCEEDED
            ),
            outcome=AuditOutcome.SUCCEEDED,
            severity=AuditSeverity.INFO,
            action="auth.mfa.step_up",
            reason_code=(
                "MFA_RECOVERY_USED"
                if result.used_recovery_code
                else "MFA_STEP_UP_SUCCEEDED"
            ),
        )
        return _issue_access_token_response(
            runtime=runtime,
            context=context,
            auth_strength="MFA_STEP_UP",
            used_recovery_code=result.used_recovery_code,
        )

    @router.post("/mfa/totp/disable", status_code=status.HTTP_204_NO_CONTENT)
    def disable_totp(
        request: TotpCodeRequest,
        http_request: Request,
        authorization: str | None = Header(default=None),
        csrf_header: str | None = Header(default=None, alias=_CSRF_HEADER_NAME),
    ) -> Response:
        context = _resolve_authenticated_context(
            authorization=authorization,
            context_resolver=runtime.context_resolver,
        )
        _require_authenticated_session(context)
        _require_csrf(request=http_request, csrf_header=csrf_header)
        identity, source_ip = _mfa_rate_limit_identity(
            runtime=runtime, context=context, request=http_request, namespace="mfa"
        )
        decision = runtime.rate_limiter.check(
            namespace="mfa", identity=identity, source_ip=source_ip
        )
        if not decision.allowed:
            _record_mfa_rate_limit_denial(
                runtime=runtime, context=context, action="auth.mfa.disable"
            )
            raise _rate_limited(decision.retry_after_seconds)
        service = _require_totp_service(runtime)
        try:
            service.disable(
                identity_id=context.identity_id,
                code=request.code,
                now=runtime.clock.now(),
            )
        except TotpVerificationError as error:
            runtime.rate_limiter.record_failure(
                namespace="mfa", identity=identity, source_ip=source_ip
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(error),
            ) from error
        runtime.rate_limiter.record_success(
            namespace="mfa", identity=identity, source_ip=source_ip
        )
        _record_mfa_event(
            runtime=runtime,
            context=context,
            event_type=AuditEventType.AUTH_MFA_DISABLED,
            outcome=AuditOutcome.SUCCEEDED,
            severity=AuditSeverity.WARNING,
            action="auth.mfa.disable",
            reason_code="MFA_DISABLED",
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get("/me", response_model=CurrentActorResponse)
    def current_actor(authorization: str | None = Header(default=None)) -> CurrentActorResponse:
        context = _resolve_authenticated_context(
            authorization=authorization,
            context_resolver=runtime.context_resolver,
        )
        return CurrentActorResponse(
            actor_id=context.actor_id,
            identity_id=context.identity_id,
            actor_kind=str(context.actor_kind),
            membership_state=str(context.membership_state),
        )

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


def _require_authenticated_session(context: ActorContext) -> UUID:
    if context.session_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHENTICATED")
    return context.session_id


def _mfa_rate_limit_identity(
    *,
    runtime: AuthenticationHttpRuntime,
    context: ActorContext,
    request: Request,
    namespace: str,
) -> tuple[str, str]:
    del namespace
    return (
        str(context.identity_id),
        _source_ip(request, trusted_proxy_networks=runtime.trusted_proxy_networks),
    )


def _record_mfa_rate_limit_denial(
    *, runtime: AuthenticationHttpRuntime, context: ActorContext, action: str
) -> None:
    _record_mfa_event(
        runtime=runtime,
        context=context,
        event_type=AuditEventType.AUTH_MFA_VERIFICATION_DENIED,
        outcome=AuditOutcome.DENIED,
        severity=AuditSeverity.WARNING,
        action=action,
        reason_code="RATE_LIMITED",
    )


def _require_totp_service(runtime: AuthenticationHttpRuntime) -> TotpService:
    if runtime.totp_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MFA_NOT_CONFIGURED",
        )
    return runtime.totp_service


def _issue_access_token_response(
    *,
    runtime: AuthenticationHttpRuntime,
    context: ActorContext,
    auth_strength: str,
    used_recovery_code: bool = False,
) -> JSONResponse:
    if context.session_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHENTICATED")
    with runtime.session_factory() as session:
        auth_session = session.get(AuthSessionRecord, context.session_id)
        if auth_session is None or auth_session.state != "ACTIVE":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UNAUTHENTICATED")
        access_token = runtime.access_tokens.issue(
            identity_id=context.identity_id,
            session_id=context.session_id,
            token_version=auth_session.token_version,
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=TotpStepUpResponse(
            access_token=access_token,
            used_recovery_code=used_recovery_code,
        ).model_dump(mode="json"),
    )


def _record_mfa_event(
    *,
    runtime: AuthenticationHttpRuntime,
    context,
    event_type: AuditEventType,
    outcome: AuditOutcome,
    severity: AuditSeverity,
    action: str,
    reason_code: str,
) -> None:
    with runtime.session_factory.begin() as session:
        SecurityAuditWriter().record(
            session=session,
            entry=SecurityAuditEntry(
                occurred_at=runtime.clock.now(),
                tenant_id=context.tenant_id,
                actor_id=context.actor_id,
                identity_id=context.identity_id,
                session_id=context.session_id,
                actor_kind=context.actor_kind.value,
                auth_strength=auth_strength_for_event(event_type),
                event_type=event_type,
                outcome=outcome,
                severity=severity,
                action=action,
                resource_type="AUTH_MFA",
                resource_id=None,
                case_id=None,
                correlation_id=context.correlation_id,
                command_id=None,
                request_id=None,
                source_ip_hash=None,
                user_agent_family=None,
                reason_code=reason_code,
                metadata={"channel": "http", "reason_class": "totp"},
            ),
        )


def auth_strength_for_event(event_type: AuditEventType) -> str | None:
    if event_type in {
        AuditEventType.AUTH_MFA_STEP_UP_SUCCEEDED,
        AuditEventType.AUTH_MFA_RECOVERY_USED,
    }:
        return "MFA_STEP_UP"
    return "MFA"


def _source_ip(
    request: Request,
    *,
    trusted_proxy_networks: tuple[IPv4Network | IPv6Network, ...] = (),
) -> str:
    """Resolve the source IP without trusting client-supplied headers by default.

    ``X-Forwarded-For`` is considered only when the direct peer belongs to an
    explicitly configured proxy network. The first address is then the address
    asserted by that trusted edge proxy; direct clients cannot forge it.
    """
    peer = request.client.host if request.client is not None else "unknown"
    if not trusted_proxy_networks:
        return peer
    try:
        peer_address = ip_address(peer)
    except ValueError:
        return peer
    if not any(peer_address in network for network in trusted_proxy_networks):
        return peer
    forwarded_for = request.headers.get("x-forwarded-for")
    if not forwarded_for:
        return peer
    candidate = forwarded_for.split(",", 1)[0].strip()
    try:
        ip_address(candidate)
    except ValueError:
        return peer
    return candidate


def _trusted_proxy_networks_from_environment() -> tuple[IPv4Network | IPv6Network, ...]:
    raw = os.getenv("SMART_AO_TRUSTED_PROXY_CIDRS", "").strip()
    if not raw:
        return ()
    networks: list[IPv4Network | IPv6Network] = []
    for value in raw.split(","):
        normalized = value.strip()
        if not normalized:
            continue
        try:
            networks.append(ip_network(normalized, strict=False))
        except ValueError as error:
            raise RuntimeError(
                "SMART_AO_TRUSTED_PROXY_CIDRS must contain valid CIDR networks"
            ) from error
    return tuple(networks)


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
