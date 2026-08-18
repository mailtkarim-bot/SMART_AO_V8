from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class PrepareSubmissionPackageRequest(BaseModel):
    command_id: UUID
    idempotency_key: UUID
    expected_preparation_revision: int = Field(ge=0)

    def to_command(self, *, preparation_package_id: UUID):
        from app.modules.submission.application.commands import PrepareSubmissionPackageCommand

        return PrepareSubmissionPackageCommand(
            command_id=self.command_id,
            idempotency_key=self.idempotency_key,
            preparation_package_id=preparation_package_id,
            expected_preparation_revision=self.expected_preparation_revision,
        )


class SubmissionPackageCommandResponse(BaseModel):
    command_id: UUID
    idempotency_key: UUID
    result_code: str
    aggregate_refs: list[dict[str, object]]
    event_ids: list[UUID]
    replayed: bool
