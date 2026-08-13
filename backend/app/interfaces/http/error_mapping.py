"""Safe HTTP mappings for application and security decisions."""

from __future__ import annotations

from fastapi import HTTPException

from app.platform.security.authorization import AuthorizationDecision


def authorization_http_exception(decision: AuthorizationDecision) -> HTTPException:
    """Map a denied authorization decision to its intentionally neutral response."""

    if decision.allowed:
        raise ValueError("an allowed authorization decision cannot become an HTTP error")
    return HTTPException(status_code=decision.http_status_code, detail=decision.code)
