"""Command handlers owned by the DCE module."""

from __future__ import annotations

import json
from hashlib import sha256
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.dce.application.commands import (
    CreateConsultationCommand,
    RegisterDceVersionCommand,
)
from app.modules.dce.domain.consultation import BuyerIdentity, Consultation
from app.modules.dce.domain.dce_version import DceDocument, DceVersion
from app.modules.dce.infrastructure.models.consultation import ConsultationRecord
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

        document_hashes = [document.sha256.lower() for document in command.documents]
        if len(document_hashes) != len(set(document_hashes)):
            raise ValueError("DCE_DOCUMENT_HASH_DUPLICATE")
        document_ids = [document.document_id for document in command.documents]
        if len(document_ids) != len(set(document_ids)):
            raise ValueError("DCE_DOCUMENT_IDENTIFIER_DUPLICATE")
        expected_corpus_hash = _corpus_hash(document_hashes)
        if command.corpus_hash.lower() != expected_corpus_hash:
            raise ValueError("DCE_CORPUS_HASH_REQUIRED")

        domain_documents = tuple(
            DceDocument(
                document_id=document.document_id,
                original_filename=document.original_filename,
                sha256=document.sha256.lower(),
                media_type=document.media_type,
                size_bytes=document.byte_size,
            )
            for document in command.documents
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
        for document in command.documents:
            session.add(
                DceDocumentRecord(
                    id=document.document_id,
                    tenant_id=version.tenant_id,
                    dce_version_id=version.id,
                    storage_object_id=document.storage_object_id,
                    storage_key=document.storage_key,
                    original_filename=document.original_filename,
                    media_type=document.media_type,
                    byte_size=document.byte_size,
                    sha256=document.sha256.lower(),
                    received_from=document.received_from,
                )
            )
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
