from __future__ import annotations

from uuid import UUID

from pydantic import Field

from app.platform.events.command_contracts import ApplicationCommand


class PrepareSubmissionPackageCommand(ApplicationCommand):
    """Freeze the latest admissible technical and official-price references for human submission."""

    command_type = "PrepareSubmissionPackage"

    preparation_package_id: UUID
    expected_preparation_revision: int = Field(ge=0)
