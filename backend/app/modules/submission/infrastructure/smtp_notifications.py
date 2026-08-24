"""Optional SMTP adapter for safe submission export notices."""

from __future__ import annotations

from email.message import EmailMessage
from typing import Any
from uuid import UUID

from app.modules.submission.application.notifications import (
    SubmissionExportNotificationPort,
)


class SmtpNotificationUnavailable(RuntimeError):
    """The SMTP server did not accept the notification safely."""


class AioSmtpSubmissionExportNotifier(SubmissionExportNotificationPort):
    """Send a minimal export-ready email; never attach or serialize package data."""

    def __init__(
        self,
        *,
        hostname: str,
        port: int,
        sender: str,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = False,
        start_tls: bool | None = None,
        timeout_seconds: float = 10.0,
        smtp_module: Any | None = None,
    ) -> None:
        if not hostname.strip():
            raise ValueError("SMTP hostname is required")
        if not 1 <= port <= 65535:
            raise ValueError("SMTP port is invalid")
        if timeout_seconds <= 0 or timeout_seconds > 60:
            raise ValueError("SMTP timeout must be between 0 and 60 seconds")
        _validate_address(sender)
        if (username is None) != (password is None):
            raise ValueError("SMTP username and password must be supplied together")
        self._hostname = hostname
        self._port = port
        self._sender = sender
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._start_tls = start_tls
        self._timeout_seconds = timeout_seconds
        self._smtp = smtp_module or _load_smtp_module()

    async def send_export_ready(self, *, recipient: str, package_id: UUID) -> None:
        _validate_address(recipient)
        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = recipient
        message["Subject"] = "SMART AO — dossier de soumission disponible"
        message.set_content(
            "Votre dossier de soumission est disponible dans SMART AO.\n"
            f"Référence technique : {package_id}.\n\n"
            "Cette notification ne contient ni document, ni montant, ni donnée financière."
        )
        kwargs: dict[str, object] = {
            "hostname": self._hostname,
            "port": self._port,
            "timeout": self._timeout_seconds,
            "use_tls": self._use_tls,
        }
        if self._start_tls is not None:
            kwargs["start_tls"] = self._start_tls
        if self._username is not None:
            kwargs["username"] = self._username
            kwargs["password"] = self._password
        try:
            await self._smtp.send(message, **kwargs)
        except Exception as exc:
            raise SmtpNotificationUnavailable("SMTP notification failed") from exc


def _load_smtp_module() -> Any:
    try:
        import aiosmtplib
    except ImportError as exc:
        raise RuntimeError("notifications extra is not installed") from exc
    return aiosmtplib


def _validate_address(address: str) -> None:
    normalized = address.strip()
    if (
        not normalized
        or "\r" in normalized
        or "\n" in normalized
        or "@" not in normalized
        or len(normalized) > 254
    ):
        raise ValueError("SMTP email address is invalid")
