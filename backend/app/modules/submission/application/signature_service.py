from __future__ import annotations

import re
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.submission.application.signature_commands import (
    RecordSubmissionSignatureCommand,
    RequestSubmissionSignatureCommand,
)
from app.modules.submission.application.signature_reader import SubmissionSignatureReader
from app.modules.submission.infrastructure.models import (
    SubmissionPackageRecord,
    SubmissionSignatureRecord,
)
from app.platform.events.dispatcher import (
    CommandContext,
    CommandDispatcher,
    CommandExecutionError,
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


class SubmissionSignatureService:
    """Authorize patron signature commands before transactional dispatch."""

    def __init__(
        self,
        *,
        dispatcher: CommandDispatcher,
        policy: AuthorizationPolicyPort,
        provider: str,
    ) -> None:
        normalized_provider = provider.strip()
        if not re.fullmatch(r"[A-Z][A-Z0-9_.-]{1,63}", normalized_provider):
            raise ValueError("signature provider must be an uppercase closed identifier")
        self._dispatcher = dispatcher
        self._policy = policy
        self.provider = normalized_provider

    def execute(self, *, actor: ActorContext, command, now: datetime):
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or not actor.membership_is_active:
            raise PermissionError("PATRON_REQUIRED")
        if getattr(command, "provider", self.provider) != self.provider:
            raise CommandExecutionError("INVALID_PROVIDER")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.SUBMISSION_SIGNATURE_WRITE,
                resource=AuthorizationResource(
                    resource_type="SUBMISSION_SIGNATURE",
                    resource_id=command.signature_id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.SECURITY_RESTRICTED,
                ),
                evaluated_at=now,
                mfa_required=True,
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


class SubmissionSignatureReadService:
    """Authorize and return a minimal patron-only signature projection."""

    def __init__(
        self,
        *,
        reader: SubmissionSignatureReader,
        policy: AuthorizationPolicyPort,
    ) -> None:
        self._reader = reader
        self._policy = policy

    def read(self, *, actor: ActorContext, signature_id, now: datetime):
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or not actor.membership_is_active:
            raise PermissionError("PATRON_REQUIRED")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.SUBMISSION_SIGNATURE_READ,
                resource=AuthorizationResource(
                    resource_type="SUBMISSION_SIGNATURE",
                    resource_id=signature_id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.SECURITY_RESTRICTED,
                ),
                evaluated_at=now,
            ),
        )
        if not decision.allowed:
            raise PermissionError(decision.code)
        projection = self._reader.get(
            tenant_id=actor.tenant_id,
            signature_id=signature_id,
        )
        if projection is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        return projection


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
            events=(
                PendingDomainEvent(
                    aggregate_type="SubmissionSignature",
                    aggregate_id=record.id,
                    aggregate_revision=1,
                    event_type="SubmissionSignatureRequested",
                    payload={
                        "submission_package_id": str(package.id),
                        "provider": record.provider,
                        "status": record.status,
                    },
                ),
            ),
        )

    def _callback(self, *, session: Session, command, context: CommandContext) -> HandlerOutcome:
        record = session.scalar(
            sa.select(SubmissionSignatureRecord).where(
                SubmissionSignatureRecord.tenant_id == context.tenant_id,
                SubmissionSignatureRecord.id == command.signature_id,
            )
        )
        command_package_id = getattr(command, "submission_package_id", None)
        record_package_id = getattr(record, "submission_package_id", None)
        if (
            record is None
            or record.provider != command.provider
            or (
                command_package_id is not None
                and record_package_id is not None
                and command_package_id != record_package_id
            )
        ):
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
            events=(
                PendingDomainEvent(
                    aggregate_type="SubmissionSignature",
                    aggregate_id=record.id,
                    aggregate_revision=2,
                    event_type="SubmissionSignatureRecorded",
                    payload={
                        "submission_package_id": str(record.submission_package_id),
                        "provider": record.provider,
                        "status": record.status,
                        "external_submission": "NOT_PERFORMED",
                    },
                ),
            ),
        )


def submission_signature_handlers() -> dict[str, SubmissionSignatureHandler]:
    handler = SubmissionSignatureHandler()
    return {
        RequestSubmissionSignatureCommand.command_type: handler,
        RecordSubmissionSignatureCommand.command_type: handler,
    }
