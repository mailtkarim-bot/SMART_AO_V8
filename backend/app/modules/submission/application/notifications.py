"""Application port for safe submission-export notifications."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class SubmissionExportNotificationPort(Protocol):
    async def send_export_ready(self, *, recipient: str, package_id: UUID) -> None:
        """Notify that an export exists without transferring its contents."""
        ...
