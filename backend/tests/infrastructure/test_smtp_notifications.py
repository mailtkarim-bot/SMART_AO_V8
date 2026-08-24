from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from app.modules.submission.infrastructure.smtp_notifications import (
    AioSmtpSubmissionExportNotifier,
    SmtpNotificationUnavailable,
)


class FakeSmtp:
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.failure = failure
        self.calls: list[tuple[object, dict[str, object]]] = []

    async def send(self, message, **kwargs):
        self.calls.append((message, kwargs))
        if self.failure is not None:
            raise self.failure


def test_notifier_sends_minimal_export_notice_without_sensitive_payload() -> None:
    smtp = FakeSmtp()
    notifier = AioSmtpSubmissionExportNotifier(
        hostname="smtp.example.test",
        port=587,
        sender="no-reply@example.test",
        username="smtp-user",
        password="smtp-password",  # pragma: allowlist secret
        use_tls=False,
        start_tls=True,
        timeout_seconds=7,
        smtp_module=smtp,
    )
    package_id = uuid4()

    asyncio.run(
        notifier.send_export_ready(
            recipient="patron@example.test",
            package_id=package_id,
        )
    )

    assert len(smtp.calls) == 1
    message, kwargs = smtp.calls[0]
    assert message["From"] == "no-reply@example.test"
    assert message["To"] == "patron@example.test"
    assert "dossier de soumission disponible" in message["Subject"]
    body = message.get_content()
    assert str(package_id) in body
    assert "montant" in body
    assert "document" in body
    assert kwargs == {
        "hostname": "smtp.example.test",
        "port": 587,
        "timeout": 7,
        "use_tls": False,
        "start_tls": True,
        "username": "smtp-user",
        "password": "smtp-password",  # pragma: allowlist secret
    }


def test_notifier_normalizes_smtp_failure_without_leaking_error() -> None:
    smtp = FakeSmtp(failure=RuntimeError("password=do-not-leak"))
    notifier = AioSmtpSubmissionExportNotifier(
        hostname="smtp.example.test",
        port=465,
        sender="no-reply@example.test",
        use_tls=True,
        smtp_module=smtp,
    )

    with pytest.raises(SmtpNotificationUnavailable, match="SMTP notification failed") as error:
        asyncio.run(
            notifier.send_export_ready(
                recipient="patron@example.test",
                package_id=uuid4(),
            )
        )

    assert "do-not-leak" not in str(error.value)


@pytest.mark.parametrize("address", ["", "not-an-email", "a\nb@example.test", "a\rb@example.test"])
def test_notifier_rejects_invalid_recipient(address: str) -> None:
    smtp = FakeSmtp()
    notifier = AioSmtpSubmissionExportNotifier(
        hostname="smtp.example.test",
        port=587,
        sender="no-reply@example.test",
        smtp_module=smtp,
    )

    with pytest.raises(ValueError, match="email address"):
        asyncio.run(notifier.send_export_ready(recipient=address, package_id=uuid4()))
    assert smtp.calls == []


def test_notifier_requires_credentials_as_a_pair() -> None:
    with pytest.raises(ValueError, match="together"):
        AioSmtpSubmissionExportNotifier(
            hostname="smtp.example.test",
            port=587,
            sender="no-reply@example.test",
            username="smtp-user",
            smtp_module=FakeSmtp(),
        )
