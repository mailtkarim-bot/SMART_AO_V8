from uuid import UUID

from pydantic import Field

from app.platform.events.command_contracts import ApplicationCommand


class CreatePreparationSnapshotCommand(ApplicationCommand):
    """Freeze the current non-financial preparation facts for patron review."""

    command_type = "CreatePreparationSnapshot"

    package_id: UUID
    snapshot_id: UUID
    expected_package_revision: int = Field(ge=0)


class TransmitPreparationSnapshotCommand(ApplicationCommand):
    """Transmit one immutable preparation snapshot to the patron."""

    command_type = "TransmitPreparationSnapshot"

    package_id: UUID
    snapshot_id: UUID
    transmission_id: UUID
    expected_package_revision: int = Field(ge=0)
