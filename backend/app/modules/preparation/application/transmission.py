from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.preparation.application.transmission_commands import (
    CreatePreparationSnapshotCommand,
    TransmitPreparationSnapshotCommand,
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
from app.platform.security.models import (
    CaseAssignmentRecord,
    GeneratedTechnicalDocumentRecord,
    PreparationPackageRecord,
    PreparationReadinessRecord,
    PreparationSnapshotRecord,
    PreparationTransmissionRecord,
    TechnicalResponseDraftRecord,
)


class PreparationTransmissionService:
    """Collaborator-only orchestration for immutable preparation transmission."""

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

    def execute(self, *, actor: ActorContext, command, now: datetime) -> DispatchResult:
        if actor.actor_kind is not ActorKind.COLLABORATEUR or actor.membership_id is None:
            raise PermissionError("COLLABORATOR_REQUIRED")
        package = self._package(actor.tenant_id, command.package_id)
        if package is None:
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.PREPARATION_TRANSMIT,
                resource=AuthorizationResource(
                    resource_type="PREPARATION_PACKAGE",
                    resource_id=package.id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                    case_id=package.case_id,
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
                case_id=package.case_id,
                correlation_id=actor.correlation_id,
            ),
        )

    def _package(self, tenant_id: UUID, package_id: UUID) -> PreparationPackageRecord | None:
        with self._session_factory() as session:
            return session.scalar(
                sa.select(PreparationPackageRecord).where(
                    PreparationPackageRecord.tenant_id == tenant_id,
                    PreparationPackageRecord.id == package_id,
                )
            )


class PreparationTransmissionHandler:
    """Own immutable snapshots and append-only patron transmissions."""

    def execute(self, *, session: Session, command, context: CommandContext) -> HandlerOutcome:
        if context.actor_kind != ActorKind.COLLABORATEUR.value or context.membership_id is None:
            raise CommandExecutionError("COLLABORATOR_REQUIRED")
        package = session.scalar(
            sa.select(PreparationPackageRecord)
            .where(
                PreparationPackageRecord.tenant_id == context.tenant_id,
                PreparationPackageRecord.id == command.package_id,
            )
            .with_for_update()
        )
        if package is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if package.aggregate_revision != command.expected_package_revision:
            raise CommandExecutionError("VERSION_CONFLICT")
        self._ensure_assignment(session=session, package=package, context=context)
        if command.command_type == CreatePreparationSnapshotCommand.command_type:
            return self._create_snapshot(
                session=session, package=package, command=command, context=context
            )
        if command.command_type == TransmitPreparationSnapshotCommand.command_type:
            return self._transmit_snapshot(
                session=session, package=package, command=command, context=context
            )
        raise CommandExecutionError(
            f"unsupported preparation transmission command: {command.command_type}"
        )

    def _ensure_assignment(
        self, *, session: Session, package: PreparationPackageRecord, context: CommandContext
    ) -> None:
        assignment = session.scalar(
            sa.select(CaseAssignmentRecord).where(
                CaseAssignmentRecord.tenant_id == context.tenant_id,
                CaseAssignmentRecord.id == package.assignment_id,
                CaseAssignmentRecord.case_id == package.case_id,
                CaseAssignmentRecord.membership_id == context.membership_id,
                CaseAssignmentRecord.state == "ACTIVE",
            )
        )
        if assignment is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if Capability.WORK_TASK_WRITE.value not in assignment.scope_actions_json:
            raise CommandExecutionError("ASSIGNMENT_SCOPE_FORBIDDEN")

    def _create_snapshot(
        self,
        *,
        session: Session,
        package: PreparationPackageRecord,
        command,
        context: CommandContext,
    ) -> HandlerOutcome:
        if package.state not in {"GENERATED", "A_REVIEW"}:
            raise CommandExecutionError("PREPARATION_NOT_GENERATED")
        readiness = session.scalar(
            sa.select(PreparationReadinessRecord)
            .where(
                PreparationReadinessRecord.tenant_id == context.tenant_id,
                PreparationReadinessRecord.package_id == package.id,
            )
            .order_by(PreparationReadinessRecord.revision.desc())
            .limit(1)
        )
        if readiness is None:
            raise CommandExecutionError("READINESS_NOT_FOUND")
        if readiness.state == "BLOCKED":
            raise CommandExecutionError("PREPARATION_BLOCKED")
        documents = list(
            session.scalars(
                sa.select(GeneratedTechnicalDocumentRecord)
                .where(
                    GeneratedTechnicalDocumentRecord.tenant_id == context.tenant_id,
                    GeneratedTechnicalDocumentRecord.package_id == package.id,
                    GeneratedTechnicalDocumentRecord.state == "GENERATED",
                )
                .order_by(
                    GeneratedTechnicalDocumentRecord.version.desc(),
                    GeneratedTechnicalDocumentRecord.id.desc(),
                )
            ).all()
        )
        if not documents:
            raise CommandExecutionError("TECHNICAL_DOCUMENT_REQUIRED")
        drafts = list(
            session.scalars(
                sa.select(TechnicalResponseDraftRecord)
                .where(
                    TechnicalResponseDraftRecord.tenant_id == context.tenant_id,
                    TechnicalResponseDraftRecord.package_id == package.id,
                )
                .order_by(
                    TechnicalResponseDraftRecord.draft_id,
                    TechnicalResponseDraftRecord.version.desc(),
                )
            ).all()
        )
        latest_drafts: dict[UUID, TechnicalResponseDraftRecord] = {}
        for draft in drafts:
            latest_drafts.setdefault(draft.draft_id, draft)
        version = (
            session.scalar(
                sa.select(
                    sa.func.coalesce(sa.func.max(PreparationSnapshotRecord.version), 0)
                ).where(
                    PreparationSnapshotRecord.tenant_id == context.tenant_id,
                    PreparationSnapshotRecord.package_id == package.id,
                )
            )
            + 1
        )
        manifest = {
            "schema_version": 1,
            "case_id": str(package.case_id),
            "package_id": str(package.id),
            "dce_version_id": str(package.dce_version_id),
            "readiness": {
                "revision": readiness.revision,
                "state": readiness.state,
                "blocker_codes": sorted(readiness.blocker_codes_json),
                "warning_codes": sorted(readiness.warning_codes_json),
            },
            "documents": [
                {
                    "document_id": str(document.id),
                    "version": document.version,
                    "kind": document.document_kind,
                    "sha256": document.content_sha256,
                }
                for document in documents[:1]
            ],
            "response_drafts": [
                {
                    "draft_id": str(draft.draft_id),
                    "version": draft.version,
                    "state": draft.state,
                    "section_codes": sorted(draft.section_codes_json),
                    "source_refs": sorted(draft.source_refs_json),
                }
                for draft in latest_drafts.values()
            ],
        }
        manifest_sha256 = hashlib.sha256(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        snapshot = PreparationSnapshotRecord(
            id=command.snapshot_id,
            tenant_id=context.tenant_id,
            package_id=package.id,
            case_id=package.case_id,
            dce_version_id=package.dce_version_id,
            readiness_id=readiness.id,
            technical_document_id=documents[0].id,
            technical_document_version=documents[0].version,
            version=version,
            state="READY_FOR_PATRON_REVIEW",
            manifest_sha256=manifest_sha256,
            manifest_json=manifest,
            actor_id=context.actor_id,
            membership_id=context.membership_id,
            command_id=command.command_id,
            idempotency_key=command.idempotency_key,
            correlation_id=command.correlation_id,
        )
        session.add(snapshot)
        package.aggregate_revision += 1
        package.state = "READY"
        return HandlerOutcome(
            result_code="PREPARATION_SNAPSHOT_CREATED",
            aggregate_refs=(
                {
                    "aggregate_type": "PreparationSnapshot",
                    "aggregate_id": str(snapshot.id),
                    "aggregate_revision": snapshot.version,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="PreparationSnapshot",
                    aggregate_id=snapshot.id,
                    aggregate_revision=snapshot.version,
                    event_type="PreparationSnapshotCreated",
                    payload={
                        "snapshot_id": str(snapshot.id),
                        "package_id": str(package.id),
                        "version": snapshot.version,
                        "state": snapshot.state,
                        "manifest_sha256": manifest_sha256,
                    },
                ),
            ),
        )

    def _transmit_snapshot(
        self,
        *,
        session: Session,
        package: PreparationPackageRecord,
        command,
        context: CommandContext,
    ) -> HandlerOutcome:
        snapshot = session.scalar(
            sa.select(PreparationSnapshotRecord).where(
                PreparationSnapshotRecord.tenant_id == context.tenant_id,
                PreparationSnapshotRecord.id == command.snapshot_id,
                PreparationSnapshotRecord.package_id == package.id,
                PreparationSnapshotRecord.state == "READY_FOR_PATRON_REVIEW",
            )
        )
        if snapshot is None:
            raise CommandExecutionError("SNAPSHOT_NOT_FOUND_OR_FORBIDDEN")
        existing = session.scalar(
            sa.select(PreparationTransmissionRecord).where(
                PreparationTransmissionRecord.tenant_id == context.tenant_id,
                PreparationTransmissionRecord.snapshot_id == snapshot.id,
            )
        )
        if existing is not None:
            raise CommandExecutionError("SNAPSHOT_ALREADY_TRANSMITTED")
        transmission = PreparationTransmissionRecord(
            id=command.transmission_id,
            tenant_id=context.tenant_id,
            package_id=package.id,
            snapshot_id=snapshot.id,
            state="TRANSMITTED_TO_PATRON",
            actor_id=context.actor_id,
            membership_id=context.membership_id,
            command_id=command.command_id,
            idempotency_key=command.idempotency_key,
            correlation_id=command.correlation_id,
        )
        session.add(transmission)
        package.aggregate_revision += 1
        package.state = "A_REVIEW"
        return HandlerOutcome(
            result_code="PREPARATION_TRANSMITTED_TO_PATRON",
            aggregate_refs=(
                {
                    "aggregate_type": "PreparationTransmission",
                    "aggregate_id": str(transmission.id),
                    "aggregate_revision": package.aggregate_revision,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="PreparationTransmission",
                    aggregate_id=transmission.id,
                    aggregate_revision=package.aggregate_revision,
                    event_type="PreparationTransmittedToPatron",
                    payload={
                        "transmission_id": str(transmission.id),
                        "snapshot_id": str(snapshot.id),
                        "package_id": str(package.id),
                        "state": transmission.state,
                    },
                ),
            ),
        )


def preparation_transmission_handlers() -> dict[str, PreparationTransmissionHandler]:
    handler = PreparationTransmissionHandler()
    return {
        CreatePreparationSnapshotCommand.command_type: handler,
        TransmitPreparationSnapshotCommand.command_type: handler,
    }
