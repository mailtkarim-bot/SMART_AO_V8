from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.submission.application.evidence_commands import RecordSubmissionEvidenceCommand
from app.modules.submission.infrastructure.models import (
    SubmissionEvidenceRecord,
    SubmissionPackageRecord,
)
from app.platform.events.dispatcher import (
    CommandContext,
    CommandDispatcher,
    CommandExecutionError,
    DispatchResult,
    HandlerOutcome,
    PendingDomainEvent,
)
from app.platform.security.authorization import (
    AuthorizationPolicyPort,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext, ActorKind, DataClassification


class SubmissionEvidenceService:
    def __init__(self, *, dispatcher: CommandDispatcher, policy: AuthorizationPolicyPort) -> None:
        self._dispatcher = dispatcher
        self._policy = policy

    def execute(self, *, actor: ActorContext, command, now: datetime) -> DispatchResult:
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("PATRON_REQUIRED")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.SUBMISSION_AUTHORIZE,
                resource=AuthorizationResource(
                    resource_type="SUBMISSION_EVIDENCE",
                    resource_id=command.evidence_id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                ),
                evaluated_at=now,
            ),
        )
        if not decision.allowed:
            raise PermissionError(decision.code)
        return self._dispatcher.dispatch(
            command=command,
            context=CommandContext(
                tenant_id=actor.tenant_id,
                actor_id=actor.actor_id,
                actor_kind=actor.actor_kind.value,
                received_at=now,
                identity_id=actor.identity_id,
                membership_id=actor.membership_id,
                session_id=actor.session_id,
                correlation_id=actor.correlation_id,
            ),
        )


class RecordSubmissionEvidenceHandler:
    """Persist patron-confirmed evidence; external submission remains outside the system."""

    def execute(self, *, session: Session, command, context: CommandContext) -> HandlerOutcome:
        package = session.scalar(
            sa.select(SubmissionPackageRecord).where(
                SubmissionPackageRecord.tenant_id == context.tenant_id,
                SubmissionPackageRecord.id == command.submission_package_id,
            )
        )
        if package is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        existing = session.scalar(
            sa.select(SubmissionEvidenceRecord).where(
                SubmissionEvidenceRecord.tenant_id == context.tenant_id,
                SubmissionEvidenceRecord.command_id == command.command_id,
            )
        )
        if existing is not None:
            raise CommandExecutionError("SUBMISSION_EVIDENCE_ALREADY_EXISTS")
        record = SubmissionEvidenceRecord(
            id=command.evidence_id,
            tenant_id=context.tenant_id,
            submission_package_id=package.id,
            case_id=package.case_id,
            evidence_type=command.evidence_type,
            status="RECEIVED",
            external_reference_hash=command.external_reference_hash,
            evidence_sha256=command.evidence_sha256,
            notes_redacted=command.notes_redacted,
            actor_id=context.actor_id,
            membership_id=context.membership_id,
            command_id=command.command_id,
            idempotency_key=command.idempotency_key,
            correlation_id=command.correlation_id,
        )
        session.add(record)
        return HandlerOutcome(
            result_code="SUBMISSION_EVIDENCE_RECORDED",
            aggregate_refs=({
                "aggregate_type": "SubmissionEvidence",
                "aggregate_id": str(record.id),
                "aggregate_revision": 1,
            },),
            events=(PendingDomainEvent(
                aggregate_type="SubmissionEvidence",
                aggregate_id=record.id,
                aggregate_revision=1,
                event_type="SubmissionEvidenceRecorded",
                payload={
                    "submission_evidence_id": str(record.id),
                    "submission_package_id": str(package.id),
                    "status": record.status,
                    "external_submission": "NOT_PERFORMED",
                },
            ),),
        )


def submission_evidence_handlers():
    handler = RecordSubmissionEvidenceHandler()
    return {RecordSubmissionEvidenceCommand.command_type: handler}
