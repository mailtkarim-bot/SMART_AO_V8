from __future__ import annotations

import hashlib
import json
import tempfile
import zipfile
from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.decision.domain.submission_gate import evaluate_submission_gate
from app.modules.enterprise.infrastructure.models import (
    CaseCapabilityProposalRecord,
    EnterpriseCapabilityProofLinkRecord,
    EnterpriseCapabilityRecord,
    EnterpriseCapabilityVersionRecord,
    EnterpriseDocumentRecord,
)
from app.modules.preparation.infrastructure.models import (
    GeneratedTechnicalDocumentRecord,
    PreparationPackageRecord,
    PreparationReadinessRecord,
)
from app.modules.pricing.infrastructure.models import FinancialReportSnapshotRecord
from app.modules.submission.application.commands import PrepareSubmissionPackageCommand
from app.modules.submission.application.notifications import SUBMISSION_EXPORT_EMAIL_TOPIC
from app.modules.submission.application.ports import SubmissionDecisionGateReader
from app.modules.submission.infrastructure.models import SubmissionPackageRecord
from app.platform.events.dispatcher import (
    CommandContext,
    CommandDispatcher,
    CommandExecutionError,
    DispatchResult,
    HandlerOutcome,
    PendingDomainEvent,
)
from app.platform.persistence.models import DomainEventRecord, OutboxMessageRecord
from app.platform.security.audit import (
    AuditEventType,
    AuditOutcome,
    AuditSeverity,
    SecurityAuditEntry,
    SecurityAuditWriter,
)
from app.platform.security.authorization import (
    AuthorizationPolicyPort,
    AuthorizationRequest,
    AuthorizationResource,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorContext, ActorKind, DataClassification
from app.platform.storage.ports import GeneratedDocumentStorage


class SubmissionPackageService:
    """Patron-only orchestration for an immutable package ready for human submission."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        dispatcher: CommandDispatcher,
        policy: AuthorizationPolicyPort,
        storage: GeneratedDocumentStorage | None = None,
        audit_writer: SecurityAuditWriter | None = None,
        decision_gate_reader: SubmissionDecisionGateReader | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._dispatcher = dispatcher
        self._policy = policy
        self._storage = storage
        self._audit_writer = audit_writer or SecurityAuditWriter()
        self._decision_gate_reader = decision_gate_reader

    def export(
        self, *, actor: ActorContext, submission_package_id: UUID, now: datetime
    ) -> bytes:
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("SUBMISSION_PATRON_REQUIRED")
        if self._storage is None:
            raise RuntimeError("SUBMISSION_EXPORT_STORAGE_NOT_CONFIGURED")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.SUBMISSION_AUTHORIZE,
                resource=AuthorizationResource(
                    resource_type="SUBMISSION_PACKAGE",
                    resource_id=submission_package_id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.FINANCIAL_PRIVATE,
                ),
                evaluated_at=now,
            ),
        )
        if not decision.allowed:
            raise PermissionError(decision.code)
        with self._session_factory() as session:
            record = session.scalar(
                sa.select(SubmissionPackageRecord).where(
                    SubmissionPackageRecord.tenant_id == actor.tenant_id,
                    SubmissionPackageRecord.id == submission_package_id,
                )
            )
            if record is None:
                raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
            manifest_bytes = json.dumps(
                record.manifest_json, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            if hashlib.sha256(manifest_bytes).hexdigest() != record.manifest_sha256:
                raise CommandExecutionError("SUBMISSION_MANIFEST_INTEGRITY_FAILED")
            document = session.scalar(
                sa.select(GeneratedTechnicalDocumentRecord).where(
                    GeneratedTechnicalDocumentRecord.tenant_id == actor.tenant_id,
                    GeneratedTechnicalDocumentRecord.id == record.technical_document_id,
                )
            )
            if document is None:
                raise CommandExecutionError("TECHNICAL_DOCUMENT_REQUIRED")
            self._assert_decision_gate(
                session=session,
                tenant_id=actor.tenant_id,
                case_id=record.case_id,
            )
            technical_bytes = self._storage.read(storage_key=document.storage_key)
        with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b") as archive:
            with zipfile.ZipFile(
                archive,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=6,
            ) as bundle:
                for name, content in (
                    ("manifest.json", manifest_bytes),
                    ("technical-response.md", technical_bytes),
                ):
                    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o600 << 16
                    bundle.writestr(info, content)
            archive.seek(0)
            archive_bytes = archive.read()
        archive_sha256 = hashlib.sha256(archive_bytes).hexdigest()
        event_id = uuid4()
        payload = {
            "submission_package_id": str(submission_package_id),
            "manifest_sha256": record.manifest_sha256,
            "archive_sha256": archive_sha256,
            "delivery": "DOWNLOAD",
        }
        email_payload = {
            "submission_package_id": str(submission_package_id),
            "delivery": "EXPORT_READY",
        }
        with self._session_factory.begin() as session:
            self._audit_writer.record(
                session=session,
                entry=SecurityAuditEntry(
                    occurred_at=now,
                    tenant_id=actor.tenant_id,
                    actor_id=actor.actor_id,
                    identity_id=actor.identity_id,
                    session_id=actor.session_id,
                    actor_kind=actor.actor_kind.value,
                    auth_strength=None,
                    event_type=AuditEventType.SUBMISSION_PACKAGE_EXPORTED,
                    outcome=AuditOutcome.SUCCEEDED,
                    severity=AuditSeverity.INFO,
                    action="submission.export",
                    resource_type="SUBMISSION_PACKAGE",
                    resource_id=submission_package_id,
                    case_id=record.case_id,
                    correlation_id=actor.correlation_id,
                    command_id=None,
                    request_id=None,
                    source_ip_hash=None,
                    user_agent_family=None,
                    reason_code=None,
                    metadata={"channel": "download"},
                ),
            )
            session.add(
                DomainEventRecord(
                    id=event_id,
                    tenant_id=actor.tenant_id,
                    aggregate_type="SubmissionPackage",
                    aggregate_id=submission_package_id,
                    aggregate_revision=record.version,
                    event_type="SubmissionPackageExported",
                    payload_version=1,
                    payload_json=payload,
                    actor_id=actor.actor_id,
                    command_id=None,
                    correlation_id=actor.correlation_id,
                    causation_id=None,
                    occurred_at=now,
                )
            )
            session.add(
                OutboxMessageRecord(
                    id=uuid4(),
                    tenant_id=actor.tenant_id,
                    event_id=event_id,
                    topic="submission.package.exported",
                    payload_version=1,
                    payload_json=payload,
                    status="PENDING",
                    attempt_count=0,
                    next_attempt_at=now,
                    published_at=None,
                    last_error_code=None,
                    dedupe_key=f"submission-export:{event_id}",
                )
            )
            session.add(
                OutboxMessageRecord(
                    id=uuid4(),
                    tenant_id=actor.tenant_id,
                    event_id=event_id,
                    topic=SUBMISSION_EXPORT_EMAIL_TOPIC,
                    payload_version=1,
                    payload_json=email_payload,
                    status="PENDING",
                    attempt_count=0,
                    next_attempt_at=now,
                    published_at=None,
                    last_error_code=None,
                    dedupe_key=f"submission-export-email:{event_id}",
                )
            )
        return archive_bytes

    def _assert_decision_gate(self, *, session: Session, tenant_id: UUID, case_id: UUID) -> None:
        if self._decision_gate_reader is None:
            raise CommandExecutionError("DECISION_GATE_NOT_CONFIGURED")
        snapshot = self._decision_gate_reader.read(
            session=session,
            tenant_id=tenant_id,
            case_id=case_id,
        )
        if snapshot is None:
            raise CommandExecutionError("DECISION_GATE_NOT_AVAILABLE")
        result = evaluate_submission_gate(snapshot)
        if not result.can_submit:
            raise CommandExecutionError("DECISION_SUBMISSION_BLOCKED")

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

    def __init__(self, *, decision_gate_reader: SubmissionDecisionGateReader | None = None) -> None:
        self._decision_gate_reader = decision_gate_reader

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
        if preparation.state not in {"GENERATED", "READY", "A_REVIEW"}:
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
        _assert_decision_gate(
            reader=self._decision_gate_reader,
            session=session,
            tenant_id=UUID(str(context.tenant_id)),
            case_id=preparation.case_id,
        )
        enterprise_entries = self._validated_enterprise_entries(
            session=session,
            preparation=preparation,
            context=context,
        )
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
            "schema_version": 2,
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
                *enterprise_entries,
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

    def _validated_enterprise_entries(
        self, *, session: Session, preparation: PreparationPackageRecord, context: CommandContext
    ) -> tuple[dict[str, object], ...]:
        proposals = list(
            session.scalars(
                sa.select(CaseCapabilityProposalRecord)
                .where(
                    CaseCapabilityProposalRecord.tenant_id == context.tenant_id,
                    CaseCapabilityProposalRecord.case_id == preparation.case_id,
                    CaseCapabilityProposalRecord.assignment_id == preparation.assignment_id,
                )
                .order_by(CaseCapabilityProposalRecord.id)
            ).all()
        )
        entries: list[dict[str, object]] = []
        for proposal in proposals:
            if proposal.validity_state != "CURRENT":
                raise CommandExecutionError("CAPABILITY_PROOF_EXPIRED")
            capability = session.scalar(
                sa.select(EnterpriseCapabilityRecord).where(
                    EnterpriseCapabilityRecord.tenant_id == context.tenant_id,
                    EnterpriseCapabilityRecord.id == proposal.capability_id,
                )
            )
            version = session.scalar(
                sa.select(EnterpriseCapabilityVersionRecord).where(
                    EnterpriseCapabilityVersionRecord.tenant_id == context.tenant_id,
                    EnterpriseCapabilityVersionRecord.id == proposal.capability_version_id,
                    EnterpriseCapabilityVersionRecord.capability_id == proposal.capability_id,
                )
            )
            if capability is None or version is None or capability.state != "ACTIVE":
                raise CommandExecutionError("CAPABILITY_PROOF_UNAUTHORIZED")
            if version.valid_from > context.received_at or (
                version.valid_until is not None and version.valid_until <= context.received_at
            ):
                raise CommandExecutionError("CAPABILITY_PROOF_EXPIRED")
            links = list(
                session.scalars(
                    sa.select(EnterpriseCapabilityProofLinkRecord)
                    .where(
                        EnterpriseCapabilityProofLinkRecord.tenant_id == context.tenant_id,
                        EnterpriseCapabilityProofLinkRecord.capability_version_id == version.id,
                    )
                    .order_by(EnterpriseCapabilityProofLinkRecord.document_id)
                ).all()
            )
            if not links:
                raise CommandExecutionError("CAPABILITY_PROOF_MISSING")
            proof_documents: list[dict[str, object]] = []
            for link in links:
                document = session.scalar(
                    sa.select(EnterpriseDocumentRecord).where(
                        EnterpriseDocumentRecord.tenant_id == context.tenant_id,
                        EnterpriseDocumentRecord.id == link.document_id,
                    )
                )
                if document is None or document.company_id != capability.company_id:
                    raise CommandExecutionError("CAPABILITY_PROOF_UNAUTHORIZED")
                if document.verification_status != "VALIDATED":
                    raise CommandExecutionError("CAPABILITY_PROOF_UNAUTHORIZED")
                if document.expires_at is not None and document.expires_at <= context.received_at:
                    raise CommandExecutionError("CAPABILITY_PROOF_EXPIRED")
                proof_documents.append(
                    {
                        "document_id": str(document.id),
                        "document_kind": document.document_kind,
                        "document_label": document.document_label,
                        "sha256": document.sha256,
                        "expires_at": document.expires_at.isoformat()
                        if document.expires_at is not None
                        else None,
                    }
                )
            entries.append(
                {
                    "kind": "ENTERPRISE_CAPABILITY",
                    "capability_id": str(capability.id),
                    "capability_kind": capability.capability_kind,
                    "name": capability.name,
                    "summary": capability.summary,
                    "version_id": str(version.id),
                    "version_number": version.version_number,
                    "title": version.title,
                    "description": version.description,
                    "usage_scope": version.usage_scope,
                    "proof_documents": proof_documents,
                }
            )
        return tuple(entries)


def submission_handlers(
    *, decision_gate_reader: SubmissionDecisionGateReader | None = None
) -> dict[str, PrepareSubmissionPackageHandler]:
    handler = PrepareSubmissionPackageHandler(decision_gate_reader=decision_gate_reader)
    return {PrepareSubmissionPackageCommand.command_type: handler}


def _assert_decision_gate(
    *,
    reader: SubmissionDecisionGateReader | None,
    session: Session,
    tenant_id: UUID,
    case_id: UUID,
) -> None:
    if reader is None:
        raise CommandExecutionError("DECISION_GATE_NOT_CONFIGURED")
    snapshot = reader.read(session=session, tenant_id=tenant_id, case_id=case_id)
    if snapshot is None:
        raise CommandExecutionError("DECISION_GATE_NOT_AVAILABLE")
    if not evaluate_submission_gate(snapshot).can_submit:
        raise CommandExecutionError("DECISION_SUBMISSION_BLOCKED")
