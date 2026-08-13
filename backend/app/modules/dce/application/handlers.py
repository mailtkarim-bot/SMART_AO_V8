"""Command handlers owned by the DCE module."""

from __future__ import annotations

import json
from hashlib import sha256
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.dce.application.commands import (
    ClaimDceStagedObjectUploadCommand,
    CreateConsultationCommand,
    ExpireDceStagedObjectCommand,
    PrepareDceStagingCommand,
    RecordDceStagedObjectQuarantineCommand,
    RecordDceStagedObjectScanCommand,
    RegisterDceVersionCommand,
    RejectDceStagedObjectUploadCommand,
)
from app.modules.dce.domain.consultation import BuyerIdentity, Consultation
from app.modules.dce.domain.dce_version import DceDocument, DceVersion
from app.modules.dce.infrastructure.models.consultation import ConsultationRecord
from app.modules.dce.infrastructure.models.dce_staging import DceStagedObjectRecord
from app.modules.dce.infrastructure.models.dce_version import DceDocumentRecord, DceVersionRecord
from app.platform.events.dispatcher import CommandContext, HandlerOutcome, PendingDomainEvent


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
            tenant_id=context.tenant_id,
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
        if (
            consultation is None
            or consultation.aggregate_revision != command.consultation_revision
        ):
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
        if (
            consultation is None
            or consultation.aggregate_revision != command.consultation_revision
        ):
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
            tenant_id=UUID(context.tenant_id),
            consultation_id=command.consultation_id,
            corpus_hash=command.corpus_hash,
            documents=domain_documents,
            provenance=command.provenance_reference or command.provenance_channel,
            received_at=command.source_received_at,
        )
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
                lifecycle=version.lifecycle.value,
                integrity=version.integrity.value,
                classification_readiness=version.classification_readiness.value,
                analysis_readiness=version.analysis_readiness.value,
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
