from dataclasses import fields
from uuid import uuid4

import pytest
from app.modules.dce.domain.consultation import (
    BuyerIdentity,
    Consultation,
    ConsultationClosed,
    ConsultationCreated,
    ConsultationLifecycle,
    ConsultationLotRegistered,
    ConsultationTrancheRegistered,
)
from app.modules.dce.domain.errors import ConsultationIdentityError, ConsultationLifecycleError


def _buyer() -> BuyerIdentity:
    return BuyerIdentity(
        legal_name="Ville de Démonstration",
        normalized_identifier="FR-EXAMPLE-0001",
    )


def test_consultation_created_is_open_tenant_scoped_and_emits_event() -> None:
    tenant_id = uuid4()
    consultation = Consultation.create(
        consultation_id=uuid4(),
        tenant_id=tenant_id,
        buyer=_buyer(),
        external_reference="AO-2026-001",
        subject="Réhabilitation du centre technique municipal",
        initial_source="Plateforme acheteur de démonstration",
    )

    assert consultation.tenant_id == tenant_id
    assert consultation.lifecycle is ConsultationLifecycle.OPEN
    assert consultation.aggregate_revision == 0
    assert consultation.pending_events == (
        ConsultationCreated(consultation_id=consultation.id, tenant_id=tenant_id),
    )


def test_consultation_functional_identity_is_stable_for_same_tenant_buyer_and_reference() -> None:
    tenant_id = uuid4()
    first = Consultation.create(
        consultation_id=uuid4(),
        tenant_id=tenant_id,
        buyer=_buyer(),
        external_reference="AO-2026-001",
        subject="Réhabilitation du centre technique municipal",
        initial_source="Plateforme acheteur de démonstration",
    )
    second = Consultation.create(
        consultation_id=uuid4(),
        tenant_id=tenant_id,
        buyer=_buyer(),
        external_reference="ao-2026-001",
        subject="Objet volontairement différent",
        initial_source="Autre import technique",
    )

    assert first.functional_identity == second.functional_identity


def test_consultation_rejects_missing_buyer_reference_identity_without_fallback_source() -> None:
    with pytest.raises(ConsultationIdentityError):
        Consultation.create(
            consultation_id=uuid4(),
            tenant_id=uuid4(),
            buyer=BuyerIdentity(legal_name="Acheteur sans identifiant"),
            external_reference=None,
            subject="Objet sans source de repli",
            initial_source="",
        )


def test_consultation_registers_source_lot_and_tranche_without_becoming_case_scope() -> None:
    consultation = Consultation.create(
        consultation_id=uuid4(),
        tenant_id=uuid4(),
        buyer=_buyer(),
        external_reference="AO-2026-002",
        subject="Extension groupe scolaire",
        initial_source="Plateforme acheteur de démonstration",
    )

    consultation.register_lot(
        lot_number="01",
        label="Gros œuvre étendu",
        source_reference="RC page 4",
    )
    consultation.register_tranche(
        tranche_reference="TF",
        tranche_kind="FIRM",
        source_reference="RC page 5",
    )

    assert consultation.lots[0].lot_number == "01"
    assert consultation.lots[0].label == "Gros œuvre étendu"
    assert consultation.tranches[0].tranche_reference == "TF"
    assert ConsultationLotRegistered(
        consultation_id=consultation.id,
        lot_number="01",
    ) in consultation.pending_events
    assert ConsultationTrancheRegistered(
        consultation_id=consultation.id,
        tranche_reference="TF",
    ) in consultation.pending_events


def test_closing_consultation_preserves_its_source_entities() -> None:
    consultation = Consultation.create(
        consultation_id=uuid4(),
        tenant_id=uuid4(),
        buyer=_buyer(),
        external_reference="AO-2026-003",
        subject="Réfection gymnase",
        initial_source="Plateforme acheteur de démonstration",
    )
    consultation.register_lot("02", "Électricité", "RC page 6")

    consultation.close(reason="Échéance de réponse dépassée", source="RC mis à jour")

    assert consultation.lifecycle is ConsultationLifecycle.CLOSED
    assert consultation.lots[0].label == "Électricité"
    assert ConsultationClosed(consultation_id=consultation.id) in consultation.pending_events
    with pytest.raises(ConsultationLifecycleError):
        consultation.register_lot("03", "Peinture", "RC page 7")


def test_consultation_does_not_own_case_or_dce_version_aggregates() -> None:
    forbidden_owned_attributes = {"case", "cases", "dce_version", "dce_versions", "decision"}
    consultation_field_names = {field.name for field in fields(Consultation)}

    assert forbidden_owned_attributes.isdisjoint(consultation_field_names)
