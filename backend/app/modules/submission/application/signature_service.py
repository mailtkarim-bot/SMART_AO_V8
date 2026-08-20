from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.submission.application.signature_commands import (
    RecordSubmissionSignatureCommand,
    RequestSubmissionSignatureCommand,
)
from app.platform.events.dispatcher import (
    CommandContext,
    CommandExecutionError,
    HandlerOutcome,
    PendingDomainEvent,
)
from app.platform.security.models import SubmissionPackageRecord, SubmissionSignatureRecord


class SubmissionSignatureHandler:
    """Append signature intent and provider callback facts without claiming portal submission."""

    def execute(self, *, session: Session, command, context: CommandContext) -> HandlerOutcome:
        if command.command_type == RequestSubmissionSignatureCommand.command_type:
            return self._request(session=session, command=command, context=context)
        if command.command_type == RecordSubmissionSignatureCommand.command_type:
            return self._callback(session=session, command=command, context=context)
        raise CommandExecutionError("UNSUPPORTED_SIGNATURE_COMMAND")

    def _request(self, *, session: Session, command, context: CommandContext) -> HandlerOutcome:
        package = session.scalar(
            sa.select(SubmissionPackageRecord).where(
                SubmissionPackageRecord.tenant_id == context.tenant_id,
                SubmissionPackageRecord.id == command.submission_package_id,
            )
        )
        if package is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if package.version != command.expected_package_version:
            raise CommandExecutionError("VERSION_CONFLICT")
        record = SubmissionSignatureRecord(
            id=command.signature_id,
            tenant_id=context.tenant_id,
            submission_package_id=package.id,
            case_id=package.case_id,
            provider=command.provider,
            signer_membership_id=command.signer_membership_id,
            expected_package_version=package.version,
            status="REQUESTED",
            actor_id=context.actor_id,
            membership_id=context.membership_id,
            command_id=command.command_id,
            idempotency_key=command.idempotency_key,
            correlation_id=command.correlation_id,
        )
        session.add(record)
        return HandlerOutcome(
            result_code="SUBMISSION_SIGNATURE_REQUESTED",
            aggregate_refs=(
                {
                    "aggregate_type": "SubmissionSignature",
                    "aggregate_id": str(record.id),
                    "aggregate_revision": 1,
                },
            ),
            events=(PendingDomainEvent(
                aggregate_type="SubmissionSignature",
                aggregate_id=record.id,
                aggregate_revision=1,
                event_type="SubmissionSignatureRequested",
                payload={
                    "submission_package_id": str(package.id),
                    "provider": record.provider,
                    "status": record.status,
                },
            ),),
        )

    def _callback(self, *, session: Session, command, context: CommandContext) -> HandlerOutcome:
        record = session.scalar(sa.select(SubmissionSignatureRecord).where(
            SubmissionSignatureRecord.tenant_id == context.tenant_id,
            SubmissionSignatureRecord.id == command.signature_id,
        ))
        if record is None or record.provider != command.provider:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if record.status != "REQUESTED":
            raise CommandExecutionError("SIGNATURE_ALREADY_FINALIZED")
        record.status = command.outcome
        record.provider_reference_hash = command.provider_reference_hash
        record.signature_sha256 = command.signature_sha256
        return HandlerOutcome(
            result_code="SUBMISSION_SIGNATURE_RECORDED",
            aggregate_refs=(
                {
                    "aggregate_type": "SubmissionSignature",
                    "aggregate_id": str(record.id),
                    "aggregate_revision": 2,
                },
            ),
            events=(PendingDomainEvent(
                aggregate_type="SubmissionSignature",
                aggregate_id=record.id,
                aggregate_revision=2,
                event_type="SubmissionSignatureRecorded",
                payload={
                    "submission_package_id": str(record.submission_package_id),
                    "provider": record.provider,
                    "status": record.status,
                },
            ),),
        )


def submission_signature_handlers() -> dict[str, SubmissionSignatureHandler]:
    handler = SubmissionSignatureHandler()
    return {
        RequestSubmissionSignatureCommand.command_type: handler,
        RecordSubmissionSignatureCommand.command_type: handler,
    }
