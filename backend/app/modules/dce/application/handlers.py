"""Command handlers owned by the DCE module."""

from __future__ import annotations

import json
from hashlib import sha256

from sqlalchemy.orm import Session

from app.modules.dce.application.commands import CreateConsultationCommand
from app.modules.dce.domain.consultation import BuyerIdentity, Consultation
from app.modules.dce.infrastructure.models.consultation import ConsultationRecord
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


def _functional_identity_hash(consultation: Consultation) -> str:
    canonical_identity = json.dumps(
        consultation.functional_identity,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return sha256(canonical_identity.encode("utf-8")).hexdigest()
