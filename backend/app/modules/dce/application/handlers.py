"""Command handlers owned by the DCE module."""

from __future__ import annotations

import json
from hashlib import sha256
from uuid import UUID, uuid4, uuid5

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.dce.application.analysis import is_valid_rc_observation
from app.modules.dce.application.classification import (
    ClassificationDocument,
    ClassificationFragment,
    ClassificationProjection,
    classification_input_manifest_sha256,
    project_dce_classification,
)
from app.modules.dce.application.commands import (
    ClaimDceStagedObjectUploadCommand,
    CreateConsultationCommand,
    ExpireDceStagedObjectCommand,
    PrepareDceStagingCommand,
    RecordCaseDceImpactRunCommand,
    RecordDceDocumentClassificationRunCommand,
    RecordDceDocumentExtractionCommand,
    RecordDceRcAnalysisCommand,
    RecordDceRequirementConfirmationCommand,
    RecordDceRequirementMaterializationRunCommand,
    RecordDceStagedObjectQuarantineCommand,
    RecordDceStagedObjectScanCommand,
    RegisterDceVersionCommand,
    RejectDceStagedObjectUploadCommand,
)
from app.modules.dce.application.impact import (
    expected_impact_items,
    impact_manifest_sha256,
    load_impact_requirements,
)
from app.modules.dce.application.requirements import (
    RequirementSignal,
    project_requirements,
    requirements_manifest_sha256,
)
from app.modules.dce.domain.consultation import BuyerIdentity, Consultation
from app.modules.dce.domain.dce_version import DceDocument, DceVersion
from app.modules.dce.infrastructure.mappings import to_dce_version_persistence_state
from app.modules.dce.infrastructure.models.case_dce_impact import (
    CaseDceImpactItemRecord,
    CaseDceImpactRunRecord,
)
from app.modules.dce.infrastructure.models.consultation import ConsultationRecord
from app.modules.dce.infrastructure.models.dce_classification import (
    DceDocumentClassificationEvidenceRecord,
    DceDocumentClassificationResultRecord,
    DceDocumentClassificationRunRecord,
)
from app.modules.dce.infrastructure.models.dce_extraction import (
    DceDocumentExtractionFragmentRecord,
    DceDocumentExtractionRecord,
)
from app.modules.dce.infrastructure.models.dce_rc_analysis import (
    DceRcAnalysisRunRecord,
    DceRcRequirementObservationRecord,
    DceRcRequirementSourceRecord,
)
from app.modules.dce.infrastructure.models.dce_requirement_confirmations import (
    DceRequirementConfirmationCurrentRecord,
    DceRequirementConfirmationRecord,
)
from app.modules.dce.infrastructure.models.dce_requirements import (
    DceRequirementMaterializationRunRecord,
    DceRequirementRecord,
    DceRequirementSourceRecord,
)
from app.modules.dce.infrastructure.models.dce_staging import DceStagedObjectRecord
from app.modules.dce.infrastructure.models.dce_version import (
    DceDocumentClassificationRecord,
    DceDocumentRecord,
    DceVersionRecord,
)
from app.platform.events.dispatcher import CommandContext, HandlerOutcome, PendingDomainEvent
from app.platform.security.audit import (
    AuditEventType,
    AuditOutcome,
    AuditSeverity,
    SecurityAuditEntry,
    SecurityAuditWriter,
)


class CreateConsultationHandler:
    """Create only the Consultation root and its first durable event."""

    def execute(
        self,
        *,
        session: Session,
        command: CreateConsultationCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        consultation = Consultation.create(
            consultation_id=command.consultation_id,
            tenant_id=UUID(str(context.tenant_id)),
            buyer=BuyerIdentity(
                legal_name=command.buyer_legal_name,
                normalized_identifier=command.buyer_normalized_id,
            ),
            external_reference=command.external_reference,
            subject=command.object_label,
            initial_source=command.source_channel,
        )
        session.add(
            ConsultationRecord(
                id=consultation.id,
                tenant_id=consultation.tenant_id,
                aggregate_revision=consultation.aggregate_revision,
                functional_identity_hash=_functional_identity_hash(consultation),
                buyer_legal_name=consultation.buyer.legal_name,
                buyer_normalized_id=consultation.buyer.normalized_identifier,
                external_reference=consultation.external_reference,
                object_label=consultation.subject,
                location_label=command.location_label,
                source_channel=command.source_channel,
                source_reference=command.source_reference,
                source_received_at=command.source_received_at,
                lifecycle=consultation.lifecycle.value,
                freshness=consultation.freshness.value,
                metadata_history_json=[],
                created_by_actor_id=context.actor_id,
                updated_by_actor_id=context.actor_id,
            )
        )
        event = PendingDomainEvent(
            aggregate_type="CONSULTATION",
            aggregate_id=consultation.id,
            aggregate_revision=consultation.aggregate_revision,
            event_type="CONSULTATION_CREATED",
            payload={
                "consultation_id": str(consultation.id),
                "tenant_id": str(consultation.tenant_id),
            },
        )
        return HandlerOutcome(
            result_code="CONSULTATION_CREATED",
            aggregate_refs=(
                {
                    "aggregate_type": "DCE",
                    "aggregate_id": str(consultation.id),
                    "aggregate_revision": consultation.aggregate_revision,
                },
            ),
            events=(event,),
        )


class PrepareDceStagingHandler:
    """Create a private server-keyed staging intent before binary upload exists."""

    def execute(
        self,
        *,
        session: Session,
        command: PrepareDceStagingCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        consultation = session.scalar(
            sa.select(ConsultationRecord).where(
                ConsultationRecord.tenant_id == context.tenant_id,
                ConsultationRecord.id == command.consultation_id,
            )
        )
        if consultation is None or consultation.aggregate_revision != command.consultation_revision:
            raise ValueError("CONSULTATION_REQUIRED_OR_STALE")
        if command.expires_at <= context.received_at:
            raise ValueError("DCE_STAGING_EXPIRY_REQUIRED")

        staged_object = DceStagedObjectRecord(
            id=command.storage_object_id,
            tenant_id=context.tenant_id,
            consultation_id=command.consultation_id,
            storage_key=_staging_storage_key(
                tenant_id=UUID(str(context.tenant_id)),
                storage_object_id=command.storage_object_id,
            ),
            original_filename=command.original_filename,
            expected_byte_size=command.expected_byte_size,
            actual_byte_size=None,
            sha256=None,
            media_type=None,
            source_channel=command.source_channel,
            state="AWAITING_UPLOAD",
            scan_verdict=None,
            scanner_name=None,
            scanner_signature_version=None,
            scanned_at=None,
            rejection_code=None,
            expires_at=command.expires_at,
            consumed_by_dce_version_id=None,
            consumed_at=None,
            created_by_actor_id=context.actor_id,
            updated_by_actor_id=context.actor_id,
        )
        session.add(staged_object)
        event = PendingDomainEvent(
            aggregate_type="DCE_STAGED_OBJECT",
            aggregate_id=staged_object.id,
            aggregate_revision=0,
            event_type="DCE_STAGING_PREPARED",
            payload={
                "storage_object_id": str(staged_object.id),
                "tenant_id": str(context.tenant_id),
                "consultation_id": str(staged_object.consultation_id),
            },
        )
        return HandlerOutcome(
            result_code="DCE_STAGING_PREPARED",
            aggregate_refs=(
                {
                    "aggregate_type": "DCE_STAGED_OBJECT",
                    "aggregate_id": str(staged_object.id),
                    "aggregate_revision": 0,
                },
            ),
            events=(event,),
        )


class ClaimDceStagedObjectUploadHandler:
    """Reserve one staged object in a short transaction before receiving its bytes."""

    def execute(
        self,
        *,
        session: Session,
        command: ClaimDceStagedObjectUploadCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        staged_object = session.scalar(
            sa.select(DceStagedObjectRecord)
            .where(
                DceStagedObjectRecord.tenant_id == context.tenant_id,
                DceStagedObjectRecord.id == command.storage_object_id,
            )
            .with_for_update()
        )
        if staged_object is None or staged_object.state != "AWAITING_UPLOAD":
            raise ValueError("DCE_STAGED_OBJECT_NOT_AWAITING_UPLOAD")
        if staged_object.expires_at <= context.received_at:
            raise ValueError("DCE_STAGED_OBJECT_EXPIRED")

        staged_object.state = "UPLOADING"
        staged_object.updated_by_actor_id = context.actor_id
        event = PendingDomainEvent(
            aggregate_type="DCE_STAGED_OBJECT",
            aggregate_id=staged_object.id,
            aggregate_revision=0,
            event_type="DCE_STAGING_UPLOAD_CLAIMED",
            payload={
                "storage_object_id": str(staged_object.id),
                "tenant_id": str(context.tenant_id),
                "consultation_id": str(staged_object.consultation_id),
            },
        )
        return HandlerOutcome(
            result_code="DCE_STAGING_UPLOAD_CLAIMED",
            aggregate_refs=(
                {
                    "aggregate_type": "DCE_STAGED_OBJECT",
                    "aggregate_id": str(staged_object.id),
                    "aggregate_revision": 0,
                },
            ),
            events=(event,),
        )


class RecordDceStagedObjectQuarantineHandler:
    """Persist trusted stream facts before a scanner can make an admissibility verdict."""

    def execute(
        self,
        *,
        session: Session,
        command: RecordDceStagedObjectQuarantineCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        if context.actor_kind != "SYSTEM":
            raise ValueError("DCE_STAGING_SYSTEM_ACTOR_REQUIRED")
        staged_object = session.scalar(
            sa.select(DceStagedObjectRecord)
            .where(
                DceStagedObjectRecord.tenant_id == context.tenant_id,
                DceStagedObjectRecord.id == command.storage_object_id,
            )
            .with_for_update()
        )
        if staged_object is None or staged_object.state != "UPLOADING":
            raise ValueError("DCE_STAGED_OBJECT_NOT_UPLOADING")

        staged_object.actual_byte_size = command.actual_byte_size
        staged_object.sha256 = command.sha256.lower()
        staged_object.media_type = command.media_type
        staged_object.updated_by_actor_id = context.actor_id
        if command.actual_byte_size != staged_object.expected_byte_size:
            staged_object.state = "REJECTED"
            staged_object.rejection_code = "BYTE_SIZE_MISMATCH"
        elif not command.content_allowed:
            staged_object.state = "REJECTED"
            staged_object.rejection_code = "MEDIA_TYPE_NOT_ALLOWED"
        else:
            staged_object.state = "QUARANTINED"
            staged_object.rejection_code = None

        event = PendingDomainEvent(
            aggregate_type="DCE_STAGED_OBJECT",
            aggregate_id=staged_object.id,
            aggregate_revision=0,
            event_type="DCE_STAGING_QUARANTINE_RECORDED",
            payload={
                "storage_object_id": str(staged_object.id),
                "tenant_id": str(context.tenant_id),
                "consultation_id": str(staged_object.consultation_id),
                "state": staged_object.state,
            },
            topic=(
                "dce_staging_retention"
                if staged_object.state == "REJECTED"
                else "cockpit_projection"
            ),
        )
        return HandlerOutcome(
            result_code="DCE_STAGING_QUARANTINE_RECORDED",
            aggregate_refs=(
                {
                    "aggregate_type": "DCE_STAGED_OBJECT",
                    "aggregate_id": str(staged_object.id),
                    "aggregate_revision": 0,
                },
            ),
            events=(event,),
        )


class RejectDceStagedObjectUploadHandler:
    """Fail closed after a trusted upload service detects a terminal stream failure."""

    def execute(
        self,
        *,
        session: Session,
        command: RejectDceStagedObjectUploadCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        if context.actor_kind != "SYSTEM":
            raise ValueError("DCE_STAGING_SYSTEM_ACTOR_REQUIRED")
        staged_object = session.scalar(
            sa.select(DceStagedObjectRecord)
            .where(
                DceStagedObjectRecord.tenant_id == context.tenant_id,
                DceStagedObjectRecord.id == command.storage_object_id,
            )
            .with_for_update()
        )
        if staged_object is None or staged_object.state != "UPLOADING":
            raise ValueError("DCE_STAGED_OBJECT_NOT_UPLOADING")

        staged_object.state = "REJECTED"
        staged_object.rejection_code = command.rejection_code
        staged_object.updated_by_actor_id = context.actor_id
        event = PendingDomainEvent(
            aggregate_type="DCE_STAGED_OBJECT",
            aggregate_id=staged_object.id,
            aggregate_revision=0,
            event_type="DCE_STAGING_UPLOAD_REJECTED",
            payload={
                "storage_object_id": str(staged_object.id),
                "tenant_id": str(context.tenant_id),
                "consultation_id": str(staged_object.consultation_id),
            },
            topic="dce_staging_retention",
        )
        return HandlerOutcome(
            result_code="DCE_STAGING_UPLOAD_REJECTED",
            aggregate_refs=(
                {
                    "aggregate_type": "DCE_STAGED_OBJECT",
                    "aggregate_id": str(staged_object.id),
                    "aggregate_revision": 0,
                },
            ),
            events=(event,),
        )


class ExpireDceStagedObjectHandler:
    """Expire an unconsumed object before its physical deletion is performed by an outbox worker."""

    def execute(
        self,
        *,
        session: Session,
        command: ExpireDceStagedObjectCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        if context.actor_kind != "SYSTEM":
            raise ValueError("DCE_STAGING_SYSTEM_ACTOR_REQUIRED")
        staged_object = session.scalar(
            sa.select(DceStagedObjectRecord)
            .where(
                DceStagedObjectRecord.tenant_id == context.tenant_id,
                DceStagedObjectRecord.id == command.storage_object_id,
            )
            .with_for_update()
        )
        if staged_object is None or staged_object.state in {"CONSUMED", "EXPIRED"}:
            raise ValueError("DCE_STAGED_OBJECT_NOT_EXPIRABLE")
        if staged_object.expires_at > context.received_at:
            raise ValueError("DCE_STAGED_OBJECT_NOT_EXPIRED")

        staged_object.state = "EXPIRED"
        staged_object.updated_by_actor_id = context.actor_id
        event = PendingDomainEvent(
            aggregate_type="DCE_STAGED_OBJECT",
            aggregate_id=staged_object.id,
            aggregate_revision=0,
            event_type="DCE_STAGING_EXPIRED",
            payload={
                "storage_object_id": str(staged_object.id),
                "tenant_id": str(context.tenant_id),
                "consultation_id": str(staged_object.consultation_id),
            },
            topic="dce_staging_retention",
        )
        return HandlerOutcome(
            result_code="DCE_STAGING_EXPIRED",
            aggregate_refs=(
                {
                    "aggregate_type": "DCE_STAGED_OBJECT",
                    "aggregate_id": str(staged_object.id),
                    "aggregate_revision": 0,
                },
            ),
            events=(event,),
        )


class RecordDceStagedObjectScanHandler:
    """Record a trusted fail-closed verdict after an upload reached quarantine."""

    def execute(
        self,
        *,
        session: Session,
        command: RecordDceStagedObjectScanCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        if context.actor_kind != "SYSTEM":
            raise ValueError("DCE_STAGING_SYSTEM_ACTOR_REQUIRED")
        staged_object = session.scalar(
            sa.select(DceStagedObjectRecord)
            .where(
                DceStagedObjectRecord.tenant_id == context.tenant_id,
                DceStagedObjectRecord.id == command.storage_object_id,
            )
            .with_for_update()
        )
        if staged_object is None or staged_object.state != "QUARANTINED":
            raise ValueError("DCE_STAGED_OBJECT_NOT_QUARANTINED")

        staged_object.actual_byte_size = command.actual_byte_size
        staged_object.sha256 = command.sha256.lower()
        staged_object.media_type = command.media_type
        staged_object.scan_verdict = command.scan_verdict
        staged_object.scanner_name = command.scanner_name
        staged_object.scanner_signature_version = command.scanner_signature_version
        staged_object.scanned_at = command.scanned_at
        staged_object.updated_by_actor_id = context.actor_id
        if command.actual_byte_size != staged_object.expected_byte_size:
            staged_object.state = "REJECTED"
            staged_object.rejection_code = "BYTE_SIZE_MISMATCH"
        elif command.scan_verdict == "CLEAN":
            staged_object.state = "CLEAN"
            staged_object.rejection_code = None
        elif command.scan_verdict == "INFECTED":
            staged_object.state = "REJECTED"
            staged_object.rejection_code = "MALWARE_DETECTED"
        else:
            staged_object.state = "REJECTED"
            staged_object.rejection_code = "SCAN_ERROR"

        event = PendingDomainEvent(
            aggregate_type="DCE_STAGED_OBJECT",
            aggregate_id=staged_object.id,
            aggregate_revision=0,
            event_type="DCE_STAGING_SCAN_RECORDED",
            payload={
                "storage_object_id": str(staged_object.id),
                "tenant_id": str(context.tenant_id),
                "consultation_id": str(staged_object.consultation_id),
                "state": staged_object.state,
            },
            topic=(
                "dce_staging_retention"
                if staged_object.state == "REJECTED"
                else "cockpit_projection"
            ),
        )
        return HandlerOutcome(
            result_code="DCE_STAGING_SCAN_RECORDED",
            aggregate_refs=(
                {
                    "aggregate_type": "DCE_STAGED_OBJECT",
                    "aggregate_id": str(staged_object.id),
                    "aggregate_revision": 0,
                },
            ),
            events=(event,),
        )


class RecordDceDocumentExtractionHandler:
    """Persist a bounded deterministic projection without exposing its source original."""

    def execute(
        self,
        *,
        session: Session,
        command: RecordDceDocumentExtractionCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        if context.actor_kind != "SYSTEM":
            raise ValueError("DCE_EXTRACTION_SYSTEM_ACTOR_REQUIRED")

        document = session.scalar(
            sa.select(DceDocumentRecord)
            .where(
                DceDocumentRecord.tenant_id == context.tenant_id,
                DceDocumentRecord.id == command.dce_document_id,
            )
            .with_for_update()
        )
        if document is None:
            raise ValueError("DCE_DOCUMENT_REQUIRED")
        dce_version = session.scalar(
            sa.select(DceVersionRecord)
            .where(
                DceVersionRecord.tenant_id == context.tenant_id,
                DceVersionRecord.id == document.dce_version_id,
            )
            .with_for_update()
        )
        staged_object = session.scalar(
            sa.select(DceStagedObjectRecord)
            .where(
                DceStagedObjectRecord.tenant_id == context.tenant_id,
                DceStagedObjectRecord.id == document.storage_object_id,
            )
            .with_for_update()
        )
        if dce_version is None or dce_version.lifecycle not in {"ADMITTED", "SUPERSEDED"}:
            raise ValueError("DCE_VERSION_NOT_ADMITTED")
        if dce_version.integrity != "VERIFIED":
            raise ValueError("DCE_VERSION_NOT_VERIFIED")
        if (
            staged_object is None
            or staged_object.state != "CONSUMED"
            or staged_object.consumed_by_dce_version_id != dce_version.id
            or staged_object.sha256 is None
            or staged_object.sha256.lower() != document.sha256.lower()
        ):
            raise ValueError("DOCUMENT_STORAGE_NOT_CONSUMED")
        if command.input_sha256.lower() != document.sha256.lower():
            raise ValueError("DOCUMENT_INPUT_HASH_REQUIRED")
        if command.status in {"COMPLETED", "REVIEW_REQUIRED"}:
            _validate_extraction_fragments(command=command)

        extraction = DceDocumentExtractionRecord(
            id=command.extraction_id,
            tenant_id=context.tenant_id,
            dce_version_id=dce_version.id,
            dce_document_id=document.id,
            input_sha256=command.input_sha256.lower(),
            extractor_id=command.extractor_id,
            extractor_version=command.extractor_version,
            status=command.status,
            fragment_count=len(command.fragments),
            extracted_char_count=command.extracted_char_count,
            failure_code=command.failure_code,
        )
        session.add(extraction)
        session.flush()
        for fragment in command.fragments:
            session.add(
                DceDocumentExtractionFragmentRecord(
                    id=uuid4(),
                    tenant_id=context.tenant_id,
                    extraction_id=extraction.id,
                    ordinal=fragment.ordinal,
                    locator_json=fragment.locator_json,
                    text=fragment.text,
                    text_sha256=fragment.text_sha256.lower(),
                )
            )
        event = PendingDomainEvent(
            aggregate_type="DCE_DOCUMENT_EXTRACTION",
            aggregate_id=extraction.id,
            aggregate_revision=0,
            event_type="DCE_DOCUMENT_EXTRACTION_RECORDED",
            payload={
                "extraction_id": str(extraction.id),
                "dce_document_id": str(document.id),
                "status": extraction.status,
                "fragment_count": extraction.fragment_count,
                "extracted_char_count": extraction.extracted_char_count,
            },
        )
        return HandlerOutcome(
            result_code="DCE_DOCUMENT_EXTRACTION_RECORDED",
            aggregate_refs=(
                {
                    "aggregate_type": "DCE_DOCUMENT_EXTRACTION",
                    "aggregate_id": str(extraction.id),
                    "aggregate_revision": 0,
                },
            ),
            events=(event,),
        )


class RecordDceDocumentClassificationRunHandler:
    """Persist deterministic source-bound document families and their current history."""

    def execute(
        self,
        *,
        session: Session,
        command: RecordDceDocumentClassificationRunCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        if context.actor_kind != "SYSTEM":
            raise ValueError("DCE_CLASSIFICATION_SYSTEM_ACTOR_REQUIRED")
        dce_version = session.scalar(
            sa.select(DceVersionRecord)
            .where(
                DceVersionRecord.tenant_id == context.tenant_id,
                DceVersionRecord.id == command.dce_version_id,
            )
            .with_for_update()
        )
        if (
            dce_version is None
            or dce_version.lifecycle not in {"ADMITTED", "SUPERSEDED"}
            or dce_version.integrity != "VERIFIED"
        ):
            raise ValueError("DCE_VERSION_NOT_CLASSIFIABLE")
        documents = list(
            session.scalars(
                sa.select(DceDocumentRecord)
                .where(
                    DceDocumentRecord.tenant_id == context.tenant_id,
                    DceDocumentRecord.dce_version_id == dce_version.id,
                )
                .order_by(DceDocumentRecord.id)
                .with_for_update()
            )
        )
        if not documents:
            raise ValueError("DCE_DOCUMENT_REQUIRED")
        document_ids = [document.id for document in documents]
        if len(documents) != command.document_count:
            raise ValueError("DCE_CLASSIFICATION_DOCUMENT_COUNT_REQUIRED")
        extraction_rows = session.execute(
            sa.select(
                DceDocumentExtractionRecord.dce_document_id,
                DceDocumentExtractionRecord.id,
                DceDocumentExtractionFragmentRecord,
            )
            .join(
                DceDocumentExtractionFragmentRecord,
                sa.and_(
                    DceDocumentExtractionFragmentRecord.tenant_id
                    == DceDocumentExtractionRecord.tenant_id,
                    DceDocumentExtractionFragmentRecord.extraction_id
                    == DceDocumentExtractionRecord.id,
                ),
            )
            .where(
                DceDocumentExtractionRecord.tenant_id == context.tenant_id,
                DceDocumentExtractionRecord.dce_document_id.in_(document_ids),
                DceDocumentExtractionRecord.status == "COMPLETED",
            )
            .order_by(
                DceDocumentExtractionRecord.dce_document_id,
                DceDocumentExtractionRecord.id,
                DceDocumentExtractionFragmentRecord.ordinal,
                DceDocumentExtractionFragmentRecord.id,
            )
            .with_for_update()
        ).all()
        fragments_by_document: dict[UUID, list[ClassificationFragment]] = {
            document_id: [] for document_id in document_ids
        }
        fragment_records: dict[UUID, DceDocumentExtractionFragmentRecord] = {}
        for document_id, extraction_id, fragment in extraction_rows:
            fragment_records[fragment.id] = fragment
            fragments_by_document[document_id].append(
                ClassificationFragment(
                    extraction_id=extraction_id,
                    fragment_id=fragment.id,
                    ordinal=fragment.ordinal,
                    text=fragment.text,
                    text_sha256=fragment.text_sha256,
                )
            )
        classification_documents = tuple(
            ClassificationDocument(
                dce_document_id=document_id,
                fragments=tuple(fragments_by_document[document_id]),
            )
            for document_id in document_ids
        )
        expected_manifest = classification_input_manifest_sha256(documents=classification_documents)
        if command.input_manifest_sha256.lower() != expected_manifest:
            raise ValueError("DCE_CLASSIFICATION_INPUT_MANIFEST_REQUIRED")
        source_fragment_count = sum(
            len(document.fragments) for document in classification_documents
        )
        source_char_count = sum(
            len(fragment.text)
            for document in classification_documents
            for fragment in document.fragments
        )
        if (
            source_fragment_count != command.source_fragment_count
            or source_char_count != command.source_char_count
        ):
            raise ValueError("DCE_CLASSIFICATION_SOURCE_COUNT_REQUIRED")

        existing_run = session.scalar(
            sa.select(DceDocumentClassificationRunRecord).where(
                DceDocumentClassificationRunRecord.tenant_id == context.tenant_id,
                DceDocumentClassificationRunRecord.dce_version_id == dce_version.id,
                DceDocumentClassificationRunRecord.input_manifest_sha256
                == command.input_manifest_sha256.lower(),
                DceDocumentClassificationRunRecord.classifier_id == command.classifier_id,
                DceDocumentClassificationRunRecord.classifier_version == command.classifier_version,
            )
        )
        if existing_run is not None:
            return HandlerOutcome(
                result_code="DCE_DOCUMENT_CLASSIFICATION_ALREADY_RECORDED",
                aggregate_refs=(
                    {
                        "aggregate_type": "DCE_DOCUMENT_CLASSIFICATION_RUN",
                        "aggregate_id": str(existing_run.id),
                        "aggregate_revision": 0,
                    },
                ),
                events=(),
            )

        if dce_version.aggregate_revision != command.expected_dce_version_revision:
            raise ValueError("DCE_VERSION_STALE")

        expected_projection = project_dce_classification(documents=classification_documents)
        _validate_classification_command(
            command=command,
            expected_projection=expected_projection,
            fragment_records=fragment_records,
        )
        classification_run = DceDocumentClassificationRunRecord(
            id=command.classification_run_id,
            tenant_id=context.tenant_id,
            dce_version_id=dce_version.id,
            dce_version_revision_before=command.expected_dce_version_revision,
            input_manifest_sha256=command.input_manifest_sha256.lower(),
            classifier_id=command.classifier_id,
            classifier_version=command.classifier_version,
            status=command.status,
            document_count=command.document_count,
            source_fragment_count=command.source_fragment_count,
            source_char_count=command.source_char_count,
            failure_code=command.failure_code,
        )
        session.add(classification_run)
        session.flush()

        current_by_document = {
            classification.dce_document_id: classification
            for classification in session.scalars(
                sa.select(DceDocumentClassificationRecord)
                .where(
                    DceDocumentClassificationRecord.tenant_id == context.tenant_id,
                    DceDocumentClassificationRecord.dce_document_id.in_(document_ids),
                    DceDocumentClassificationRecord.is_current.is_(True),
                )
                .with_for_update()
            )
        }
        classifications_by_document: dict[UUID, DceDocumentClassificationRecord] = {}
        for result in command.results:
            if result.status != "CLASSIFIED":
                continue
            current = current_by_document.get(result.dce_document_id)
            if current is not None and current.classification == result.classification:
                classifications_by_document[result.dce_document_id] = current
                continue
            if current is not None:
                current.is_current = False
                session.flush()
            classification = DceDocumentClassificationRecord(
                id=uuid4(),
                tenant_id=context.tenant_id,
                dce_document_id=result.dce_document_id,
                classification=result.classification,
                rationale=None,
                source="SYSTEM_DETERMINISTIC_V1",
                previous_classification_id=current.id if current is not None else None,
                is_current=True,
                created_by_actor_id=context.actor_id,
            )
            session.add(classification)
            classifications_by_document[result.dce_document_id] = classification
        session.flush()

        for result in command.results:
            classification_record = classifications_by_document.get(result.dce_document_id)
            result_record = DceDocumentClassificationResultRecord(
                id=uuid4(),
                tenant_id=context.tenant_id,
                classification_run_id=classification_run.id,
                dce_version_id=dce_version.id,
                dce_document_id=result.dce_document_id,
                status=result.status,
                classification=result.classification,
                rule_match_count=result.rule_match_count,
                classification_id=(
                    classification_record.id if classification_record is not None else None
                ),
            )
            session.add(result_record)
            session.flush()
            if result.evidence:
                if classification_record is None:
                    raise ValueError("DCE_CLASSIFICATION_EVIDENCE_WITHOUT_CLASSIFICATION")
                for evidence in result.evidence:
                    session.add(
                        DceDocumentClassificationEvidenceRecord(
                            id=uuid4(),
                            tenant_id=context.tenant_id,
                            classification_result_id=result_record.id,
                            fragment_id=evidence.fragment_id,
                            classification_id=classification_record.id,
                            rule_id=evidence.rule_id,
                            rule_version=evidence.rule_version,
                            start_byte_offset=evidence.start_byte_offset,
                            end_byte_offset=evidence.end_byte_offset,
                            excerpt=evidence.excerpt,
                        )
                    )

        dce_version.classification_readiness = _classification_readiness(command=command)
        dce_version.aggregate_revision += 1
        dce_version.updated_by_actor_id = context.actor_id
        event = PendingDomainEvent(
            aggregate_type="DCE_DOCUMENT_CLASSIFICATION_RUN",
            aggregate_id=classification_run.id,
            aggregate_revision=0,
            event_type="DCE_DOCUMENT_CLASSIFICATION_RECORDED",
            payload={
                "classification_run_id": str(classification_run.id),
                "dce_version_id": str(dce_version.id),
                "classification_readiness": dce_version.classification_readiness,
                "document_count": command.document_count,
                "classified_document_count": sum(
                    result.status == "CLASSIFIED" for result in command.results
                ),
            },
        )
        return HandlerOutcome(
            result_code="DCE_DOCUMENT_CLASSIFICATION_RECORDED",
            aggregate_refs=(
                {
                    "aggregate_type": "DCE_DOCUMENT_CLASSIFICATION_RUN",
                    "aggregate_id": str(classification_run.id),
                    "aggregate_revision": 0,
                },
            ),
            events=(event,),
        )


class RecordDceRcAnalysisHandler:
    """Persist source-bound deterministic RC signals without reading originals or deciding."""

    def execute(
        self,
        *,
        session: Session,
        command: RecordDceRcAnalysisCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        if context.actor_kind != "SYSTEM":
            raise ValueError("DCE_ANALYSIS_SYSTEM_ACTOR_REQUIRED")
        dce_version = session.scalar(
            sa.select(DceVersionRecord)
            .where(
                DceVersionRecord.tenant_id == context.tenant_id,
                DceVersionRecord.id == command.dce_version_id,
            )
            .with_for_update()
        )
        if (
            dce_version is None
            or dce_version.lifecycle not in {"ADMITTED", "SUPERSEDED"}
            or dce_version.integrity != "VERIFIED"
        ):
            raise ValueError("DCE_VERSION_NOT_ANALYSABLE")

        source_rows = session.execute(
            sa.select(
                DceDocumentRecord.id,
                DceDocumentExtractionRecord.id,
                DceDocumentExtractionFragmentRecord,
            )
            .join(
                DceDocumentExtractionRecord,
                sa.and_(
                    DceDocumentExtractionRecord.tenant_id
                    == DceDocumentExtractionFragmentRecord.tenant_id,
                    DceDocumentExtractionRecord.id
                    == DceDocumentExtractionFragmentRecord.extraction_id,
                ),
            )
            .join(
                DceDocumentRecord,
                sa.and_(
                    DceDocumentRecord.tenant_id == DceDocumentExtractionRecord.tenant_id,
                    DceDocumentRecord.id == DceDocumentExtractionRecord.dce_document_id,
                ),
            )
            .where(
                DceDocumentRecord.tenant_id == context.tenant_id,
                DceDocumentRecord.dce_version_id == dce_version.id,
                DceDocumentExtractionRecord.status == "COMPLETED",
            )
            .order_by(
                DceDocumentRecord.id,
                DceDocumentExtractionRecord.id,
                DceDocumentExtractionFragmentRecord.ordinal,
                DceDocumentExtractionFragmentRecord.id,
            )
            .with_for_update()
        ).all()
        if not source_rows:
            raise ValueError("DCE_EXTRACTION_COMPLETED_REQUIRED")
        source_fragment_ids = [fragment.id for _, _, fragment in source_rows]
        if source_fragment_ids != command.source_fragment_ids:
            raise ValueError("DCE_ANALYSIS_SOURCE_FRAGMENT_REQUIRED")
        source_char_count = sum(len(fragment.text) for _, _, fragment in source_rows)
        if (
            len(source_rows) != command.source_fragment_count
            or source_char_count != command.source_char_count
        ):
            raise ValueError("DCE_ANALYSIS_SOURCE_COUNT_REQUIRED")
        expected_manifest = _rc_analysis_input_manifest(source_rows=source_rows)
        if command.input_manifest_sha256.lower() != expected_manifest:
            raise ValueError("DCE_ANALYSIS_INPUT_MANIFEST_REQUIRED")

        existing = session.scalar(
            sa.select(DceRcAnalysisRunRecord).where(
                DceRcAnalysisRunRecord.tenant_id == context.tenant_id,
                DceRcAnalysisRunRecord.dce_version_id == dce_version.id,
                DceRcAnalysisRunRecord.input_manifest_sha256
                == command.input_manifest_sha256.lower(),
                DceRcAnalysisRunRecord.analyzer_id == command.analyzer_id,
                DceRcAnalysisRunRecord.analyzer_version == command.analyzer_version,
            )
        )
        if existing is not None:
            return HandlerOutcome(
                result_code="DCE_RC_ANALYSIS_ALREADY_RECORDED",
                aggregate_refs=(
                    {
                        "aggregate_type": "DCE_RC_ANALYSIS",
                        "aggregate_id": str(existing.id),
                        "aggregate_revision": 0,
                    },
                ),
                events=(),
            )

        fragments_by_id = {fragment.id: fragment for _, _, fragment in source_rows}
        if command.status == "COMPLETED":
            _validate_rc_analysis_observations(
                command=command,
                fragments_by_id=fragments_by_id,
            )
        analysis = DceRcAnalysisRunRecord(
            id=command.analysis_id,
            tenant_id=context.tenant_id,
            dce_version_id=dce_version.id,
            input_manifest_sha256=command.input_manifest_sha256.lower(),
            analyzer_id=command.analyzer_id,
            analyzer_version=command.analyzer_version,
            status=command.status,
            source_fragment_count=command.source_fragment_count,
            source_char_count=command.source_char_count,
            failure_code=command.failure_code,
        )
        session.add(analysis)
        session.flush()
        for observation in command.observations:
            source = observation.sources[0]
            session.add(
                DceRcRequirementObservationRecord(
                    id=observation.observation_id,
                    tenant_id=context.tenant_id,
                    analysis_id=analysis.id,
                    dce_version_id=dce_version.id,
                    requirement_kind=observation.requirement_kind,
                    directive=observation.directive,
                    rule_id=observation.rule_id,
                    rule_version=observation.rule_version,
                    fragment_id=source.fragment_id,
                    start_byte_offset=source.start_byte_offset,
                    end_byte_offset=source.end_byte_offset,
                    excerpt=observation.excerpt,
                )
            )
            session.add(
                DceRcRequirementSourceRecord(
                    id=uuid4(),
                    tenant_id=context.tenant_id,
                    observation_id=observation.observation_id,
                    fragment_id=source.fragment_id,
                    start_byte_offset=source.start_byte_offset,
                    end_byte_offset=source.end_byte_offset,
                )
            )
        event = PendingDomainEvent(
            aggregate_type="DCE_RC_ANALYSIS",
            aggregate_id=analysis.id,
            aggregate_revision=0,
            event_type="DCE_RC_ANALYSIS_RECORDED",
            payload={
                "analysis_id": str(analysis.id),
                "dce_version_id": str(dce_version.id),
                "status": analysis.status,
                "source_fragment_count": analysis.source_fragment_count,
                "observation_count": len(command.observations),
            },
        )
        return HandlerOutcome(
            result_code="DCE_RC_ANALYSIS_RECORDED",
            aggregate_refs=(
                {
                    "aggregate_type": "DCE_RC_ANALYSIS",
                    "aggregate_id": str(analysis.id),
                    "aggregate_revision": 0,
                },
            ),
            events=(event,),
        )


class RegisterDceVersionHandler:
    """Admit a new immutable DCE root and its originals in one dispatcher transaction."""

    def execute(
        self,
        *,
        session: Session,
        command: RegisterDceVersionCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        consultation = session.scalar(
            sa.select(ConsultationRecord).where(
                ConsultationRecord.tenant_id == context.tenant_id,
                ConsultationRecord.id == command.consultation_id,
            )
        )
        if consultation is None or consultation.aggregate_revision != command.consultation_revision:
            raise ValueError("CONSULTATION_REQUIRED_OR_STALE")

        document_ids = [document.document_id for document in command.documents]
        if len(document_ids) != len(set(document_ids)):
            raise ValueError("DCE_DOCUMENT_IDENTIFIER_DUPLICATE")
        storage_object_ids = [document.storage_object_id for document in command.documents]
        if len(storage_object_ids) != len(set(storage_object_ids)):
            raise ValueError("DCE_STAGED_OBJECT_DUPLICATE")
        staged_objects = list(
            session.scalars(
                sa.select(DceStagedObjectRecord)
                .where(
                    DceStagedObjectRecord.tenant_id == context.tenant_id,
                    DceStagedObjectRecord.id.in_(storage_object_ids),
                )
                .with_for_update()
            )
        )
        staged_by_id = {staged_object.id: staged_object for staged_object in staged_objects}
        if len(staged_by_id) != len(storage_object_ids):
            raise ValueError("DCE_STAGED_OBJECT_REQUIRED")
        ordered_staged_objects = [
            staged_by_id[storage_object_id] for storage_object_id in storage_object_ids
        ]
        for staged_object in ordered_staged_objects:
            if staged_object.consultation_id != command.consultation_id:
                raise ValueError("DCE_STAGED_OBJECT_CONSULTATION_REQUIRED")
            if staged_object.state != "CLEAN":
                raise ValueError("DCE_STAGED_OBJECT_NOT_CLEAN")
            if staged_object.expires_at <= context.received_at:
                raise ValueError("DCE_STAGED_OBJECT_EXPIRED")
            if (
                staged_object.sha256 is None
                or staged_object.media_type is None
                or staged_object.actual_byte_size is None
            ):
                raise ValueError("DCE_STAGED_OBJECT_METADATA_REQUIRED")

        document_hashes = [staged_object.sha256 for staged_object in ordered_staged_objects]
        expected_corpus_hash = _corpus_hash(document_hashes)
        if command.corpus_hash.lower() != expected_corpus_hash:
            raise ValueError("DCE_CORPUS_HASH_REQUIRED")

        domain_documents = tuple(
            DceDocument(
                document_id=document.document_id,
                original_filename=staged_object.original_filename,
                sha256=staged_object.sha256,
                media_type=staged_object.media_type,
                size_bytes=staged_object.actual_byte_size,
            )
            for document, staged_object in zip(
                command.documents,
                ordered_staged_objects,
                strict=True,
            )
        )
        version = DceVersion.register(
            dce_version_id=command.dce_version_id,
            tenant_id=UUID(str(context.tenant_id)),
            consultation_id=command.consultation_id,
            corpus_hash=command.corpus_hash,
            documents=domain_documents,
            provenance=command.provenance_reference or command.provenance_channel,
            received_at=command.source_received_at,
        )
        persistence_state = to_dce_version_persistence_state(version)
        session.add(
            DceVersionRecord(
                id=version.id,
                tenant_id=version.tenant_id,
                aggregate_revision=version.aggregate_revision,
                consultation_id=version.consultation_id,
                corpus_hash=version.corpus_hash,
                predecessor_dce_version_id=None,
                provenance_channel=command.provenance_channel,
                provenance_reference=command.provenance_reference,
                provenance_url=command.provenance_url,
                source_received_at=command.source_received_at,
                lifecycle=persistence_state.lifecycle,
                integrity=persistence_state.integrity,
                classification_readiness=persistence_state.classification_readiness,
                analysis_readiness=persistence_state.analysis_readiness,
                withdrawal_source=None,
                withdrawal_reason=None,
                superseded_at=None,
                withdrawn_at=None,
                created_by_actor_id=context.actor_id,
                updated_by_actor_id=context.actor_id,
            )
        )
        session.flush()
        for document, staged_object in zip(command.documents, ordered_staged_objects, strict=True):
            session.add(
                DceDocumentRecord(
                    id=document.document_id,
                    tenant_id=version.tenant_id,
                    dce_version_id=version.id,
                    storage_object_id=staged_object.id,
                    storage_key=staged_object.storage_key,
                    original_filename=staged_object.original_filename,
                    media_type=staged_object.media_type,
                    byte_size=staged_object.actual_byte_size,
                    sha256=staged_object.sha256,
                    received_from=staged_object.source_channel,
                )
            )
            staged_object.state = "CONSUMED"
            staged_object.consumed_by_dce_version_id = version.id
            staged_object.consumed_at = context.received_at
            staged_object.updated_by_actor_id = context.actor_id
        event = PendingDomainEvent(
            aggregate_type="DCE_VERSION",
            aggregate_id=version.id,
            aggregate_revision=version.aggregate_revision,
            event_type="DCE_VERSION_REGISTERED",
            payload={
                "dce_version_id": str(version.id),
                "tenant_id": str(version.tenant_id),
                "consultation_id": str(version.consultation_id),
            },
        )
        return HandlerOutcome(
            result_code="DCE_VERSION_REGISTERED",
            aggregate_refs=(
                {
                    "aggregate_type": "DCE",
                    "aggregate_id": str(version.id),
                    "aggregate_revision": version.aggregate_revision,
                },
            ),
            events=(event,),
        )


def _validate_classification_command(
    *,
    command: RecordDceDocumentClassificationRunCommand,
    expected_projection: ClassificationProjection,
    fragment_records: dict[UUID, DceDocumentExtractionFragmentRecord],
) -> None:
    expected_status = expected_projection.status
    expected_failure_code = expected_projection.failure_code
    expected_results = expected_projection.results
    if command.status != expected_status or command.failure_code != expected_failure_code:
        raise ValueError("DCE_CLASSIFICATION_PROJECTION_REQUIRED")
    if command.status != "COMPLETED":
        return
    if len(command.results) != len(expected_results):
        raise ValueError("DCE_CLASSIFICATION_RESULT_REQUIRED")
    for received, expected in zip(command.results, expected_results, strict=True):
        if (
            received.dce_document_id != expected.dce_document_id
            or received.status != expected.status
            or received.classification != expected.classification
            or received.rule_match_count != expected.rule_match_count
            or len(received.evidence) != len(expected.evidence)
        ):
            raise ValueError("DCE_CLASSIFICATION_RESULT_REQUIRED")
        for received_evidence, expected_evidence in zip(
            received.evidence,
            expected.evidence,
            strict=True,
        ):
            fragment = fragment_records.get(received_evidence.fragment_id)
            if fragment is None:
                raise ValueError("DCE_CLASSIFICATION_SOURCE_FRAGMENT_REQUIRED")
            if (
                received_evidence.fragment_id != expected_evidence.fragment_id
                or received_evidence.rule_id != expected_evidence.rule_id
                or received_evidence.start_byte_offset != expected_evidence.start_byte_offset
                or received_evidence.end_byte_offset != expected_evidence.end_byte_offset
                or received_evidence.excerpt != expected_evidence.excerpt
            ):
                raise ValueError("DCE_CLASSIFICATION_EVIDENCE_REQUIRED")
            source_bytes = fragment.text.encode("utf-8")
            if received_evidence.end_byte_offset > len(source_bytes):
                raise ValueError("DCE_CLASSIFICATION_SOURCE_OFFSET_REQUIRED")
            try:
                sourced_excerpt = source_bytes[
                    received_evidence.start_byte_offset : received_evidence.end_byte_offset
                ].decode("utf-8")
            except UnicodeDecodeError as error:
                raise ValueError("DCE_CLASSIFICATION_SOURCE_OFFSET_REQUIRED") from error
            if sourced_excerpt != received_evidence.excerpt:
                raise ValueError("DCE_CLASSIFICATION_SOURCE_EXCERPT_REQUIRED")


def _classification_readiness(*, command: RecordDceDocumentClassificationRunCommand) -> str:
    classified_count = sum(result.status == "CLASSIFIED" for result in command.results)
    if classified_count == 0:
        return "UNCLASSIFIED"
    if classified_count == len(command.results):
        return "CLASSIFIED"
    return "PARTIALLY_CLASSIFIED"


def _validate_rc_analysis_observations(
    *,
    command: RecordDceRcAnalysisCommand,
    fragments_by_id: dict[UUID, DceDocumentExtractionFragmentRecord],
) -> None:
    for observation in command.observations:
        source = observation.sources[0]
        fragment = fragments_by_id.get(source.fragment_id)
        if fragment is None:
            raise ValueError("DCE_ANALYSIS_SOURCE_FRAGMENT_REQUIRED")
        source_bytes = fragment.text.encode("utf-8")
        if source.end_byte_offset > len(source_bytes):
            raise ValueError("DCE_ANALYSIS_SOURCE_OFFSET_REQUIRED")
        try:
            sourced_excerpt = source_bytes[
                source.start_byte_offset : source.end_byte_offset
            ].decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("DCE_ANALYSIS_SOURCE_OFFSET_REQUIRED") from error
        if sourced_excerpt != observation.excerpt:
            raise ValueError("DCE_ANALYSIS_SOURCE_EXCERPT_REQUIRED")
        if not is_valid_rc_observation(
            requirement_kind=observation.requirement_kind,
            rule_id=observation.rule_id,
            directive=observation.directive,
            excerpt=observation.excerpt,
        ):
            raise ValueError("DCE_ANALYSIS_RULE_REQUIRED")


def _rc_analysis_input_manifest(
    *,
    source_rows: list[tuple[UUID, UUID, DceDocumentExtractionFragmentRecord]],
) -> str:
    canonical_manifest = "\n".join(
        "|".join(
            (
                str(document_id),
                str(extraction_id),
                str(fragment.id),
                str(fragment.ordinal),
                fragment.text_sha256.lower(),
            )
        )
        for document_id, extraction_id, fragment in source_rows
    )
    return sha256(canonical_manifest.encode("utf-8")).hexdigest()


def _validate_extraction_fragments(*, command: RecordDceDocumentExtractionCommand) -> None:
    expected_ordinals = list(range(1, len(command.fragments) + 1))
    if [fragment.ordinal for fragment in command.fragments] != expected_ordinals:
        raise ValueError("DCE_EXTRACTION_FRAGMENT_ORDINAL_REQUIRED")
    for fragment in command.fragments:
        if not isinstance(fragment.locator_json.get("kind"), str):
            raise ValueError("DCE_EXTRACTION_FRAGMENT_LOCATOR_REQUIRED")
        calculated_hash = sha256(fragment.text.encode("utf-8")).hexdigest()
        if fragment.text_sha256.lower() != calculated_hash:
            raise ValueError("DCE_EXTRACTION_FRAGMENT_HASH_REQUIRED")


def _staging_storage_key(*, tenant_id: UUID, storage_object_id: UUID) -> str:
    """Derive a private backend key; a caller never submits or receives this value."""

    return f"dce-staging/{tenant_id}/{storage_object_id}"


def _corpus_hash(document_hashes: list[str]) -> str:
    canonical_manifest = "\n".join(sorted(document_hashes))
    return sha256(canonical_manifest.encode("ascii")).hexdigest()


def _functional_identity_hash(consultation: Consultation) -> str:
    canonical_identity = json.dumps(
        consultation.functional_identity,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return sha256(canonical_identity.encode("utf-8")).hexdigest()


class RecordDceRequirementMaterializationRunHandler:
    """Persist atomic human-pending requirements from one completed RC analysis."""

    def execute(
        self,
        *,
        session: Session,
        command: RecordDceRequirementMaterializationRunCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        if context.actor_kind != "SYSTEM":
            raise ValueError("DCE_REQUIREMENT_SYSTEM_ACTOR_REQUIRED")
        dce_version = session.scalar(
            sa.select(DceVersionRecord)
            .where(
                DceVersionRecord.tenant_id == context.tenant_id,
                DceVersionRecord.id == command.dce_version_id,
            )
            .with_for_update()
        )
        if (
            dce_version is None
            or dce_version.lifecycle not in {"ADMITTED", "SUPERSEDED"}
            or dce_version.integrity != "VERIFIED"
        ):
            raise ValueError("DCE_VERSION_NOT_REQUIREMENTS_READY")
        analysis = session.scalar(
            sa.select(DceRcAnalysisRunRecord)
            .where(
                DceRcAnalysisRunRecord.tenant_id == context.tenant_id,
                DceRcAnalysisRunRecord.id == command.dce_rc_analysis_id,
                DceRcAnalysisRunRecord.dce_version_id == dce_version.id,
            )
            .with_for_update()
        )
        if analysis is None or analysis.status != "COMPLETED":
            raise ValueError("DCE_RC_ANALYSIS_COMPLETED_REQUIRED")
        rows = session.execute(
            sa.select(DceRcRequirementObservationRecord, DceRcRequirementSourceRecord)
            .join(
                DceRcRequirementSourceRecord,
                sa.and_(
                    DceRcRequirementSourceRecord.tenant_id
                    == DceRcRequirementObservationRecord.tenant_id,
                    DceRcRequirementSourceRecord.observation_id
                    == DceRcRequirementObservationRecord.id,
                ),
            )
            .where(
                DceRcRequirementObservationRecord.tenant_id == context.tenant_id,
                DceRcRequirementObservationRecord.analysis_id == analysis.id,
                DceRcRequirementObservationRecord.dce_version_id == dce_version.id,
            )
            .order_by(DceRcRequirementObservationRecord.id)
            .with_for_update()
        ).all()
        signals = tuple(
            RequirementSignal(
                observation_id=observation.id,
                requirement_kind=observation.requirement_kind,
                directive=observation.directive,
                rule_id=observation.rule_id,
                rule_version=observation.rule_version,
                fragment_id=source.fragment_id,
                start_byte_offset=source.start_byte_offset,
                end_byte_offset=source.end_byte_offset,
            )
            for observation, source in rows
        )
        expected_manifest = requirements_manifest_sha256(signals=signals)
        if command.input_manifest_sha256.lower() != expected_manifest:
            raise ValueError("DCE_REQUIREMENT_INPUT_MANIFEST_REQUIRED")
        if command.source_observation_count != len(signals):
            raise ValueError("DCE_REQUIREMENT_SOURCE_COUNT_REQUIRED")
        existing = session.scalar(
            sa.select(DceRequirementMaterializationRunRecord).where(
                DceRequirementMaterializationRunRecord.tenant_id == context.tenant_id,
                DceRequirementMaterializationRunRecord.dce_version_id == dce_version.id,
                DceRequirementMaterializationRunRecord.dce_rc_analysis_id == analysis.id,
                DceRequirementMaterializationRunRecord.input_manifest_sha256
                == command.input_manifest_sha256.lower(),
                DceRequirementMaterializationRunRecord.materializer_id == command.materializer_id,
                DceRequirementMaterializationRunRecord.materializer_version
                == command.materializer_version,
            )
        )
        if existing is not None:
            return HandlerOutcome(
                result_code="DCE_REQUIREMENTS_ALREADY_MATERIALIZED",
                aggregate_refs=(
                    {
                        "aggregate_type": "DCE_REQUIREMENT_MATERIALIZATION_RUN",
                        "aggregate_id": str(existing.id),
                        "aggregate_revision": 0,
                    },
                ),
                events=(),
            )
        projection = project_requirements(signals=signals)
        if command.status != projection.status or command.failure_code != projection.failure_code:
            raise ValueError("DCE_REQUIREMENT_PROJECTION_REQUIRED")
        expected_types = {
            "RC_DOCUMENT_CANDIDATURE": "CANDIDATURE_DOCUMENT",
            "RC_CONTENT_OFFER": "OFFER_DOCUMENT",
            "RC_SUBMISSION_DEADLINE": "SUBMISSION_DEADLINE_SIGNAL",
            "RC_RESPONSE_CHANNEL": "SUBMISSION_CHANNEL",
            "RC_FILE_CONSTRAINT": "FILE_CONSTRAINT",
            "RC_SITE_VISIT": "SITE_VISIT",
            "RC_AWARD_CRITERION": "AWARD_CRITERION_SIGNAL",
            "RC_NEGOTIATION": "NEGOTIATION_SIGNAL",
            "RC_OFFER_VALIDITY": "OFFER_VALIDITY_SIGNAL",
        }
        if command.status == "COMPLETED":
            if len(command.requirements) != len(signals):
                raise ValueError("DCE_REQUIREMENT_COUNT_REQUIRED")
            for received, signal in zip(command.requirements, signals, strict=True):
                if (
                    received.source_observation_id != signal.observation_id
                    or received.requirement_type != expected_types[signal.requirement_kind]
                    or received.directive_signal != signal.directive
                    or received.confirmation_status != "PENDING_HUMAN_CONFIRMATION"
                    or received.uncertainty_status != "SOURCE_SIGNAL_ONLY"
                ):
                    raise ValueError("DCE_REQUIREMENT_MAPPING_REQUIRED")
        requirement_run = DceRequirementMaterializationRunRecord(
            id=command.requirements_run_id,
            tenant_id=context.tenant_id,
            dce_version_id=dce_version.id,
            dce_rc_analysis_id=analysis.id,
            input_manifest_sha256=command.input_manifest_sha256.lower(),
            materializer_id=command.materializer_id,
            materializer_version=command.materializer_version,
            status=command.status,
            source_observation_count=command.source_observation_count,
            failure_code=command.failure_code,
        )
        session.add(requirement_run)
        session.flush()
        source_by_observation = {observation.id: source for observation, source in rows}
        for item in command.requirements:
            source = source_by_observation[item.source_observation_id]
            requirement = DceRequirementRecord(
                id=item.requirement_id,
                tenant_id=context.tenant_id,
                requirements_run_id=requirement_run.id,
                dce_version_id=dce_version.id,
                source_observation_id=item.source_observation_id,
                requirement_type=item.requirement_type,
                directive_signal=item.directive_signal,
                confirmation_status=item.confirmation_status,
                uncertainty_status=item.uncertainty_status,
            )
            session.add(requirement)
            session.flush()
            session.add(
                DceRequirementSourceRecord(
                    id=uuid4(),
                    tenant_id=context.tenant_id,
                    requirement_id=requirement.id,
                    source_observation_id=item.source_observation_id,
                    fragment_id=source.fragment_id,
                    start_byte_offset=source.start_byte_offset,
                    end_byte_offset=source.end_byte_offset,
                )
            )
        event = PendingDomainEvent(
            aggregate_type="DCE_REQUIREMENT_MATERIALIZATION_RUN",
            aggregate_id=requirement_run.id,
            aggregate_revision=0,
            event_type="DCE_REQUIREMENTS_MATERIALIZED",
            payload={
                "requirements_run_id": str(requirement_run.id),
                "dce_version_id": str(dce_version.id),
                "dce_rc_analysis_id": str(analysis.id),
                "status": command.status,
                "source_observation_count": command.source_observation_count,
                "requirement_count": len(command.requirements),
            },
        )
        return HandlerOutcome(
            result_code="DCE_REQUIREMENTS_MATERIALIZED",
            aggregate_refs=(
                {
                    "aggregate_type": "DCE_REQUIREMENT_MATERIALIZATION_RUN",
                    "aggregate_id": str(requirement_run.id),
                    "aggregate_revision": 0,
                },
            ),
            events=(event,),
        )


class RecordCaseDceImpactRunHandler:
    """Persist a conservative, immutable impact ledger for one Case rectification."""

    def execute(
        self,
        *,
        session: Session,
        command: RecordCaseDceImpactRunCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        if context.actor_kind != "SYSTEM":
            raise ValueError("CASE_DCE_IMPACT_SYSTEM_ACTOR_REQUIRED")

        case = session.scalar(
            sa.select(CaseRecord)
            .where(
                CaseRecord.tenant_id == context.tenant_id,
                CaseRecord.id == command.case_id,
            )
            .with_for_update()
        )
        predecessor = session.scalar(
            sa.select(DceVersionRecord)
            .where(
                DceVersionRecord.tenant_id == context.tenant_id,
                DceVersionRecord.id == command.predecessor_dce_version_id,
            )
            .with_for_update()
        )
        successor = session.scalar(
            sa.select(DceVersionRecord)
            .where(
                DceVersionRecord.tenant_id == context.tenant_id,
                DceVersionRecord.id == command.successor_dce_version_id,
            )
            .with_for_update()
        )
        if case is None or case.lifecycle == "ARCHIVED":
            raise ValueError("CASE_NOT_FOUND_OR_FORBIDDEN")
        if (
            predecessor is None
            or successor is None
            or case.applicable_dce_version_id != predecessor.id
            or predecessor.consultation_id != successor.consultation_id
            or successor.predecessor_dce_version_id != predecessor.id
            or predecessor.lifecycle not in {"ADMITTED", "SUPERSEDED"}
            or predecessor.integrity != "VERIFIED"
            or successor.lifecycle != "ADMITTED"
            or successor.integrity != "VERIFIED"
        ):
            raise ValueError("CASE_DCE_PREDECESSOR_MISMATCH")

        previous_requirements = load_impact_requirements(
            session=session,
            tenant_id=UUID(str(context.tenant_id)),
            dce_version_id=predecessor.id,
        )
        successor_requirements = load_impact_requirements(
            session=session,
            tenant_id=UUID(str(context.tenant_id)),
            dce_version_id=successor.id,
        )
        manifest = impact_manifest_sha256(
            case_id=command.case_id,
            predecessor_dce_version_id=predecessor.id,
            successor_dce_version_id=successor.id,
            previous_requirements=previous_requirements,
            successor_requirements=successor_requirements,
        )
        expected_run_id = uuid5(
            command.case_id,
            f"{predecessor.id}:{successor.id}:{manifest}:smart-ao-case-dce-impact:1",
        )
        if command.impact_run_id != expected_run_id or (
            command.input_manifest_sha256.lower() != manifest
        ):
            raise ValueError("CASE_DCE_IMPACT_INPUT_MANIFEST_REQUIRED")
        if command.previous_requirement_count != len(
            previous_requirements
        ) or command.successor_requirement_count != len(successor_requirements):
            raise ValueError("CASE_DCE_IMPACT_SOURCE_COUNT_REQUIRED")
        expected_items = expected_impact_items(
            impact_run_id=command.impact_run_id,
            previous_requirements=previous_requirements,
            successor_requirements=successor_requirements,
        )
        if command.items != list(expected_items):
            raise ValueError("CASE_DCE_IMPACT_PROJECTION_REQUIRED")
        existing = session.scalar(
            sa.select(CaseDceImpactRunRecord).where(
                CaseDceImpactRunRecord.tenant_id == context.tenant_id,
                CaseDceImpactRunRecord.case_id == command.case_id,
                CaseDceImpactRunRecord.predecessor_dce_version_id == predecessor.id,
                CaseDceImpactRunRecord.successor_dce_version_id == successor.id,
                CaseDceImpactRunRecord.input_manifest_sha256 == manifest,
                CaseDceImpactRunRecord.algorithm_id == command.algorithm_id,
                CaseDceImpactRunRecord.algorithm_version == command.algorithm_version,
            )
        )
        if existing is not None:
            return HandlerOutcome(
                result_code="CASE_DCE_IMPACT_ALREADY_RECORDED",
                aggregate_refs=(
                    {
                        "aggregate_type": "CASE_DCE_IMPACT_RUN",
                        "aggregate_id": str(existing.id),
                        "aggregate_revision": 0,
                    },
                ),
                events=(),
            )

        impact_run = CaseDceImpactRunRecord(
            id=command.impact_run_id,
            tenant_id=context.tenant_id,
            case_id=case.id,
            predecessor_dce_version_id=predecessor.id,
            successor_dce_version_id=successor.id,
            input_manifest_sha256=manifest,
            algorithm_id=command.algorithm_id,
            algorithm_version=command.algorithm_version,
            status=command.status,
            previous_requirement_count=command.previous_requirement_count,
            successor_requirement_count=command.successor_requirement_count,
            failure_code=None,
            created_by_actor_id=context.actor_id,
        )
        session.add(impact_run)
        session.flush()
        for item in command.items:
            session.add(
                CaseDceImpactItemRecord(
                    id=item.impact_item_id,
                    tenant_id=context.tenant_id,
                    impact_run_id=impact_run.id,
                    case_id=case.id,
                    impact_kind=item.impact_kind,
                    previous_requirement_id=item.previous_requirement_id,
                    successor_requirement_id=item.successor_requirement_id,
                    review_state=item.review_state,
                    evidence_code=item.evidence_code,
                )
            )
        event = PendingDomainEvent(
            aggregate_type="CASE_DCE_IMPACT_RUN",
            aggregate_id=impact_run.id,
            aggregate_revision=0,
            event_type="CASE_DCE_IMPACT_RECORDED",
            payload={
                "impact_run_id": str(impact_run.id),
                "case_id": str(case.id),
                "predecessor_dce_version_id": str(predecessor.id),
                "successor_dce_version_id": str(successor.id),
                "status": impact_run.status,
                "previous_requirement_count": impact_run.previous_requirement_count,
                "successor_requirement_count": impact_run.successor_requirement_count,
                "item_count": len(command.items),
            },
        )
        return HandlerOutcome(
            result_code="CASE_DCE_IMPACT_RECORDED",
            aggregate_refs=(
                {
                    "aggregate_type": "CASE_DCE_IMPACT_RUN",
                    "aggregate_id": str(impact_run.id),
                    "aggregate_revision": 0,
                },
            ),
            events=(event,),
        )


class RecordDceRequirementConfirmationHandler:
    """Persist a human confirmation as an immutable successor of one requirement."""

    def __init__(self, *, audit_writer: SecurityAuditWriter | None = None) -> None:
        self._audit_writer = audit_writer or SecurityAuditWriter()

    def execute(
        self,
        *,
        session: Session,
        command: RecordDceRequirementConfirmationCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        if context.actor_kind == "SYSTEM":
            raise ValueError("DCE_REQUIREMENT_HUMAN_ACTOR_REQUIRED")
        requirement = session.scalar(
            sa.select(DceRequirementRecord)
            .where(
                DceRequirementRecord.tenant_id == context.tenant_id,
                DceRequirementRecord.id == command.requirement_id,
            )
            .with_for_update()
        )
        if requirement is None:
            raise ValueError("NOT_FOUND_OR_FORBIDDEN")
        current = session.scalar(
            sa.select(DceRequirementConfirmationCurrentRecord)
            .where(
                DceRequirementConfirmationCurrentRecord.tenant_id == context.tenant_id,
                DceRequirementConfirmationCurrentRecord.requirement_id == requirement.id,
            )
            .with_for_update()
        )
        current_revision = current.revision if current is not None else 0
        if current_revision != command.expected_confirmation_revision:
            raise ValueError("DCE_REQUIREMENT_CONFIRMATION_STALE")
        if command.outcome == "NOT_APPLICABLE" and context.actor_kind == "COLLABORATEUR":
            raise ValueError("DCE_REQUIREMENT_PATRON_REQUIRED")
        confirmation = DceRequirementConfirmationRecord(
            id=command.confirmation_id,
            tenant_id=context.tenant_id,
            requirement_id=requirement.id,
            revision=current_revision + 1,
            previous_confirmation_id=current.confirmation_id if current is not None else None,
            outcome=command.outcome,
            reason_code=command.reason_code,
            confirmed_by_actor_id=context.actor_id,
        )
        session.add(confirmation)
        session.flush()
        if current is None:
            session.add(
                DceRequirementConfirmationCurrentRecord(
                    tenant_id=context.tenant_id,
                    requirement_id=requirement.id,
                    confirmation_id=confirmation.id,
                    revision=confirmation.revision,
                    outcome=confirmation.outcome,
                )
            )
        else:
            current.confirmation_id = confirmation.id
            current.revision = confirmation.revision
            current.outcome = confirmation.outcome
        if context.case_id is not None:
            self._audit_writer.record(
                session=session,
                entry=SecurityAuditEntry(
                    occurred_at=context.received_at,
                    tenant_id=UUID(str(context.tenant_id)),
                    actor_id=UUID(str(context.actor_id)),
                    identity_id=(
                        UUID(str(context.identity_id)) if context.identity_id is not None else None
                    ),
                    session_id=(
                        UUID(str(context.session_id)) if context.session_id is not None else None
                    ),
                    actor_kind=context.actor_kind,
                    auth_strength=None,
                    event_type=AuditEventType.AUTHZ_SUCCEEDED,
                    outcome=AuditOutcome.SUCCEEDED,
                    severity=AuditSeverity.INFO,
                    action="dce.requirement.confirm",
                    resource_type="DCE_REQUIREMENT",
                    resource_id=requirement.id,
                    case_id=UUID(str(context.case_id)),
                    correlation_id=command.correlation_id,
                    command_id=command.command_id,
                    request_id=None,
                    source_ip_hash=None,
                    user_agent_family=None,
                    reason_code="DCE_REQUIREMENT_CONFIRMED",
                    metadata={"channel": "command"},
                ),
            )
        event = PendingDomainEvent(
            aggregate_type="DCE_REQUIREMENT_CONFIRMATION",
            aggregate_id=confirmation.id,
            aggregate_revision=confirmation.revision,
            event_type="DCE_REQUIREMENT_CONFIRMED",
            payload={
                "confirmation_id": str(confirmation.id),
                "requirement_id": str(requirement.id),
                "outcome": confirmation.outcome,
                "reason_code": confirmation.reason_code,
                "revision": confirmation.revision,
            },
        )
        return HandlerOutcome(
            result_code="DCE_REQUIREMENT_CONFIRMED",
            aggregate_refs=(
                {
                    "aggregate_type": "DCE_REQUIREMENT_CONFIRMATION",
                    "aggregate_id": str(confirmation.id),
                    "aggregate_revision": confirmation.revision,
                },
            ),
            events=(event,),
        )
