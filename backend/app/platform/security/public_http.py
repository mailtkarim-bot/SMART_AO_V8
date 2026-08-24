"""Safe outbound HTTPS primitives for provider-facing adapters."""

from __future__ import annotations

import ipaddress
import socket
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.response import addinfourl


class _NoRedirectHandler(HTTPRedirectHandler):
    """Reject redirects so a validated public destination cannot pivot internally."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, "redirects are disabled", headers, fp)


_NO_REDIRECT_OPENER = build_opener(_NoRedirectHandler)


def validate_public_https_destination(url: str) -> None:
    """Reject credentials, non-HTTPS URLs and DNS answers in non-public ranges."""

    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ValueError("outbound URL must be HTTPS without credentials or fragments")
    try:
        destinations = socket.getaddrinfo(
            parsed.hostname,
            parsed.port or 443,
            type=socket.SOCK_STREAM,
        )
    except OSError as exc:
        raise ValueError("outbound DNS resolution failed") from exc
    if not destinations:
        raise ValueError("outbound DNS resolution failed")
    for destination in destinations:
        address = ipaddress.ip_address(destination[4][0])
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            raise ValueError("outbound destination is not public")


def open_public_https(request: Request, *, timeout: float) -> addinfourl:
    """Open one validated HTTPS request without following redirects."""

    validate_public_https_destination(request.full_url)
    return _NO_REDIRECT_OPENER.open(request, timeout=timeout)
