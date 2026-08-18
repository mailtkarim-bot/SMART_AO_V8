from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.submission.application.commands import PrepareSubmissionPackageCommand
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
from app.platform.security.models import (
    FinancialReportSnapshotRecord,
    GeneratedTechnicalDocumentRecord,
    PreparationPackageRecord,
    PreparationReadinessRecord,
    SubmissionPackageRecord,
)


class SubmissionPackageService:
    """Patron-only orchestration for an immutable package ready for human submission."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        dispatcher: CommandDispatcher,
        policy: AuthorizationPolicyPort,
    ) -> None:
        self._session_factory = session_factory
        self._dispatcher = dispatcher
        self._policy = policy

    def prepare(
        self,
        *,
        actor: ActorContext,
        command: PrepareSubmissionPackageCommand,
        now: datetime,
    ) -> DispatchResult:
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("SUBMISSION_PATRON_REQUIRED")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.SUBMISSION_AUTHORIZE,
                resource=AuthorizationResource(
                    resource_type="PREPARATION_PACKAGE_SUBMISSION",
                    resource_id=command.preparation_package_id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.FINANCIAL_PRIVATE,
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


class PrepareSubmissionPackageHandler:
    """Freeze server-resolved references; never claim external submission success."""

    def execute(
        self,
        *,
        session: Session,
        command: PrepareSubmissionPackageCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        if context.actor_kind != ActorKind.PATRON_ADMIN.value or context.membership_id is None:
            raise CommandExecutionError("SUBMISSION_PATRON_REQUIRED")
        preparation = session.scalar(
            sa.select(PreparationPackageRecord)
            .where(
                PreparationPackageRecord.tenant_id == context.tenant_id,
                PreparationPackageRecord.id == command.preparation_package_id,
            )
            .with_for_update()
        )
        if preparation is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if preparation.aggregate_revision != command.expected_preparation_revision:
            raise CommandExecutionError("VERSION_CONFLICT")
        if preparation.state != "GENERATED":
            raise CommandExecutionError("PREPARATION_NOT_GENERATED")
        readiness = session.scalar(
            sa.select(PreparationReadinessRecord)
            .where(
                PreparationReadinessRecord.tenant_id == context.tenant_id,
                PreparationReadinessRecord.package_id == preparation.id,
            )
            .order_by(PreparationReadinessRecord.revision.desc())
            .limit(1)
        )
        if readiness is None:
            raise CommandExecutionError("READINESS_NOT_FOUND")
        if readiness.state == "BLOCKED":
            raise CommandExecutionError("PREPARATION_BLOCKED")
        document = session.scalar(
            sa.select(GeneratedTechnicalDocumentRecord)
            .where(
                GeneratedTechnicalDocumentRecord.tenant_id == context.tenant_id,
                GeneratedTechnicalDocumentRecord.package_id == preparation.id,
                GeneratedTechnicalDocumentRecord.state == "GENERATED",
            )
            .order_by(
                GeneratedTechnicalDocumentRecord.version.desc(),
                GeneratedTechnicalDocumentRecord.id.desc(),
            )
            .limit(1)
        )
        if document is None:
            raise CommandExecutionError("TECHNICAL_DOCUMENT_REQUIRED")
        snapshot = session.scalar(
            sa.select(FinancialReportSnapshotRecord)
            .where(
                FinancialReportSnapshotRecord.tenant_id == context.tenant_id,
                FinancialReportSnapshotRecord.case_id == preparation.case_id,
                FinancialReportSnapshotRecord.state == "PUBLISHED",
            )
            .order_by(
                FinancialReportSnapshotRecord.published_at.desc(),
                FinancialReportSnapshotRecord.id.desc(),
            )
            .limit(1)
        )
        if snapshot is None:
            raise CommandExecutionError("OFFICIAL_PRICE_NOT_PUBLISHED")
        version = (
            session.scalar(
                sa.select(sa.func.coalesce(sa.func.max(SubmissionPackageRecord.version), 0)).where(
                    SubmissionPackageRecord.tenant_id == context.tenant_id,
                    SubmissionPackageRecord.preparation_package_id == preparation.id,
                )
            )
            + 1
        )
        manifest = {
            "schema_version": 1,
            "case_id": str(preparation.case_id),
            "preparation_package_id": str(preparation.id),
            "dce_version_id": str(preparation.dce_version_id),
            "readiness": {
                "revision": readiness.revision,
                "state": readiness.state,
                "blocker_codes": sorted(readiness.blocker_codes_json),
                "warning_codes": sorted(readiness.warning_codes_json),
            },
            "entries": [
                {
                    "kind": document.document_kind,
                    "document_id": str(document.id),
                    "version": document.version,
                    "sha256": document.content_sha256,
                },
                {
                    "kind": "OFFICIAL_PRICING_VERSION",
                    "snapshot_id": str(snapshot.id),
                    "revision": snapshot.aggregate_revision,
                },
            ],
            "external_submission": "NOT_PERFORMED",
        }
        serialized = json.dumps(
            manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        manifest_sha256 = hashlib.sha256(serialized).hexdigest()
        record = SubmissionPackageRecord(
            id=uuid4(),
            tenant_id=context.tenant_id,
            preparation_package_id=preparation.id,
            case_id=preparation.case_id,
            dce_version_id=preparation.dce_version_id,
            technical_document_id=document.id,
            technical_document_version=document.version,
            financial_snapshot_id=snapshot.id,
            financial_snapshot_revision=snapshot.aggregate_revision,
            version=version,
            state="PRET_CONTROLE",
            manifest_sha256=manifest_sha256,
            manifest_json=manifest,
            actor_id=context.actor_id,
            membership_id=context.membership_id,
            command_id=command.command_id,
            idempotency_key=command.idempotency_key,
            correlation_id=command.correlation_id,
        )
        session.add(record)
        return HandlerOutcome(
            result_code="SUBMISSION_PACKAGE_PREPARED",
            aggregate_refs=(
                {
                    "aggregate_type": "SubmissionPackage",
                    "aggregate_id": str(record.id),
                    "aggregate_revision": record.version,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="SubmissionPackage",
                    aggregate_id=record.id,
                    aggregate_revision=record.version,
                    event_type="SubmissionPackagePrepared",
                    payload={
                        "submission_package_id": str(record.id),
                        "preparation_package_id": str(preparation.id),
                        "version": record.version,
                        "state": record.state,
                        "manifest_sha256": manifest_sha256,
                        "external_submission": "NOT_PERFORMED",
                    },
                ),
            ),
        )


def submission_handlers() -> dict[str, PrepareSubmissionPackageHandler]:
    handler = PrepareSubmissionPackageHandler()
    return {PrepareSubmissionPackageCommand.command_type: handler}
