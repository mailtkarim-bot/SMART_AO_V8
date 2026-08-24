"""FastAPI-facing authentication dependency helpers."""

from __future__ import annotations

from fastapi import HTTPException, status

from app.platform.security.authenticated_context import (
    AuthenticationContextResolver,
    UnauthenticatedError,
)
from app.platform.security.context import ActorContext


def resolve_bearer_context(
    *,
    authorization: str | None,
    context_resolver: AuthenticationContextResolver,
) -> ActorContext:
    """Resolve a Bearer header into authoritative server-side actor facts."""

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
