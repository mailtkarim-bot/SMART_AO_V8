"""Pure domain model for the DCE/Consultation aggregate.

Consultation preserves the durable identity and buyer-provided lot/tranche
structure of an invitation to tender. It never owns Case or DceVersion roots.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from .errors import ConsultationIdentityError, ConsultationLifecycleError


class ConsultationLifecycle(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class ConsultationFreshness(StrEnum):
    UNKNOWN = "UNKNOWN"
    CURRENT = "CURRENT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass(frozen=True, slots=True)
class BuyerIdentity:
    legal_name: str
    normalized_identifier: str | None = None

    def normalized_key(self) -> str | None:
        identifier = (
            self.normalized_identifier.strip().upper()
            if self.normalized_identifier
            else ""
        )
        return identifier or None


@dataclass(frozen=True, slots=True)
class ConsultationLot:
    lot_number: str
    label: str
    source_reference: str | None = None

    def __post_init__(self) -> None:
        if not self.lot_number.strip() or not self.label.strip():
            raise ConsultationIdentityError("consultation lot requires source number and label")


@dataclass(frozen=True, slots=True)
class ConsultationTranche:
    tranche_reference: str
    tranche_kind: str
    source_reference: str | None = None

    def __post_init__(self) -> None:
        if not self.tranche_reference.strip() or not self.tranche_kind.strip():
            raise ConsultationIdentityError(
                "consultation tranche requires source reference and kind"
            )


@dataclass(frozen=True, slots=True)
class ConsultationCreated:
    consultation_id: UUID
    tenant_id: UUID


@dataclass(frozen=True, slots=True)
class ConsultationLotRegistered:
    consultation_id: UUID
    lot_number: str


@dataclass(frozen=True, slots=True)
class ConsultationTrancheRegistered:
    consultation_id: UUID
    tranche_reference: str


@dataclass(frozen=True, slots=True)
class ConsultationClosed:
    consultation_id: UUID


@dataclass(slots=True)
class Consultation:
    """DCE aggregate root representing a buyer consultation identity."""

    id: UUID
    tenant_id: UUID
    buyer: BuyerIdentity
    external_reference: str | None
    subject: str
    initial_source: str
    lifecycle: ConsultationLifecycle = ConsultationLifecycle.OPEN
    freshness: ConsultationFreshness = ConsultationFreshness.UNKNOWN
    lots: list[ConsultationLot] = field(default_factory=list)
    tranches: list[ConsultationTranche] = field(default_factory=list)
    aggregate_revision: int = 0
    _pending_events: list[object] = field(default_factory=list, repr=False)

    @classmethod
    def create(
        cls,
        *,
        consultation_id: UUID,
        tenant_id: UUID,
        buyer: BuyerIdentity,
        external_reference: str | None,
        subject: str,
        initial_source: str,
    ) -> Consultation:
        cls._validate_identity(
            buyer=buyer,
            external_reference=external_reference,
            subject=subject,
            initial_source=initial_source,
        )
        consultation = cls(
            id=consultation_id,
            tenant_id=tenant_id,
            buyer=buyer,
            external_reference=external_reference.strip() if external_reference else None,
            subject=subject.strip(),
            initial_source=initial_source.strip(),
        )
        consultation._record(
            ConsultationCreated(
                consultation_id=consultation.id,
                tenant_id=consultation.tenant_id,
            )
        )
        return consultation

    @property
    def functional_identity(self) -> tuple[str, ...]:
        buyer_key = self.buyer.normalized_key()
        external_reference = self._normalize_reference(self.external_reference)
        if buyer_key and external_reference:
            return ("BUYER_REFERENCE", str(self.tenant_id), buyer_key, external_reference)
        return (
            "SOURCE_FALLBACK",
            str(self.tenant_id),
            self._normalize_reference(self.initial_source),
            self._normalize_reference(self.subject),
        )

    @property
    def pending_events(self) -> tuple[object, ...]:
        return tuple(self._pending_events)

    def register_lot(
        self,
        lot_number: str,
        label: str,
        source_reference: str | None = None,
    ) -> None:
        self._ensure_open()
        lot = ConsultationLot(
            lot_number=lot_number.strip(),
            label=label.strip(),
            source_reference=source_reference.strip() if source_reference else None,
        )
        if any(
            existing.lot_number.casefold() == lot.lot_number.casefold()
            for existing in self.lots
        ):
            raise ConsultationIdentityError("consultation lot number is already registered")
        self.lots.append(lot)
        self._increment_revision()
        self._record(
            ConsultationLotRegistered(
                consultation_id=self.id,
                lot_number=lot.lot_number,
            )
        )

    def register_tranche(
        self,
        tranche_reference: str,
        tranche_kind: str,
        source_reference: str | None = None,
    ) -> None:
        self._ensure_open()
        tranche = ConsultationTranche(
            tranche_reference=tranche_reference.strip(),
            tranche_kind=tranche_kind.strip(),
            source_reference=source_reference.strip() if source_reference else None,
        )
        if any(
            existing.tranche_reference.casefold() == tranche.tranche_reference.casefold()
            for existing in self.tranches
        ):
            raise ConsultationIdentityError("consultation tranche reference is already registered")
        self.tranches.append(tranche)
        self._increment_revision()
        self._record(
            ConsultationTrancheRegistered(
                consultation_id=self.id,
                tranche_reference=tranche.tranche_reference,
            )
        )

    def close(self, *, reason: str, source: str) -> None:
        self._ensure_open()
        if not reason.strip() or not source.strip():
            raise ConsultationLifecycleError("consultation closure requires reason and source")
        self.lifecycle = ConsultationLifecycle.CLOSED
        self._increment_revision()
        self._record(ConsultationClosed(consultation_id=self.id))

    def _ensure_open(self) -> None:
        if self.lifecycle is not ConsultationLifecycle.OPEN:
            raise ConsultationLifecycleError("consultation lifecycle forbids this action")

    @staticmethod
    def _validate_identity(
        *,
        buyer: BuyerIdentity,
        external_reference: str | None,
        subject: str,
        initial_source: str,
    ) -> None:
        if not buyer.legal_name.strip():
            raise ConsultationIdentityError("consultation buyer legal name is required")
        if not subject.strip():
            raise ConsultationIdentityError("consultation subject is required")

        has_buyer_reference = bool(
            buyer.normalized_key() and (external_reference or "").strip()
        )
        has_source_fallback = bool(initial_source.strip() and subject.strip())
        if not has_buyer_reference and not has_source_fallback:
            raise ConsultationIdentityError(
                "consultation requires buyer/reference identity or source fallback"
            )

    @staticmethod
    def _normalize_reference(value: str | None) -> str:
        return " ".join((value or "").strip().upper().split())

    def _increment_revision(self) -> None:
        self.aggregate_revision += 1

    def _record(self, event: object) -> None:
        self._pending_events.append(event)
