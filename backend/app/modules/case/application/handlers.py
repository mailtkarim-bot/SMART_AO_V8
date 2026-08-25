"""Application handlers for the Case bounded context."""

from __future__ import annotations

import json
from collections.abc import Callable
from hashlib import sha256
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.case.application.commands import CreateCaseCommand
from app.modules.case.application.ports import (
    CaseRepository,
    ConsultationReferenceReader,
)
from app.modules.case.domain.case import (
    AggregateReference,
    Case,
    CaseOrigin,
    CaseOriginKind,
    CaseScope,
    CaseScopeKind,
)
from app.platform.events.dispatcher import CommandContext, HandlerOutcome, PendingDomainEvent

_SCOPE_KIND_MAP = {
    "SINGLE_LOT": CaseScopeKind.SINGLE_LOT,
    "MULTI_LOT": CaseScopeKind.MULTI_LOT,
    "TRANCHE": CaseScopeKind.TRANCHE,
    "VARIANT": CaseScopeKind.VARIANT,
    "CUSTOM": CaseScopeKind.CUSTOM_SOURCED_SCOPE,
}
_ORIGIN_KIND_MAP = {
    "MANUAL": CaseOriginKind.MANUAL,
    "OPPORTUNITY": CaseOriginKind.OPPORTUNITY,
    "IMPORT": CaseOriginKind.IMPORT,
    "CLIENT_REQUEST": CaseOriginKind.CUSTOMER_REQUEST,
}


class CreateCaseHandler:
    """Create an AFF root and emit only a sparse, non-financial event."""

    def __init__(
        self,
        repository_factory: Callable[[Session], CaseRepository],
        consultation_reader_factory: Callable[[Session], ConsultationReferenceReader] | None = None,
    ) -> None:
        self._repository_factory = repository_factory
        self._consultation_reader_factory = consultation_reader_factory

    def execute(
        self,
        *,
        session: Session,
        command: CreateCaseCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        scope_kind = _SCOPE_KIND_MAP[command.scope_kind]
        scope = CaseScope(
            kind=scope_kind,
            lot_numbers=command.lot_numbers,
            tranche_reference=command.tranche_reference,
            variant_reference=command.variant_reference,
            source_justification=command.scope_justification,
        )
        origin = CaseOrigin(
            kind=_ORIGIN_KIND_MAP[command.origin_kind],
            rationale=command.origin_rationale,
            origin_reference_id=command.origin_reference_id,
        )
        if command.origin_kind == "MANUAL" and command.origin_reference_id is not None:
            raise ValueError("MANUAL_ORIGIN_MUST_NOT_HAVE_REFERENCE")
        if command.origin_kind != "MANUAL" and command.origin_reference_id is None:
            raise ValueError("NON_MANUAL_ORIGIN_REQUIRES_REFERENCE")
        if command.consultation_id is None and command.consultation_revision is not None:
            raise ValueError("CONSULTATION_REQUIRED_OR_STALE")
        if command.consultation_id is None and command.origin_kind not in {"MANUAL", "OPPORTUNITY"}:
            raise ValueError("CONSULTATION_REQUIRED_OR_STALE")
        consultation_revision: int | None = None
        if command.consultation_id is not None:
            if command.consultation_revision is None or self._consultation_reader_factory is None:
                raise ValueError("CONSULTATION_REQUIRED_OR_STALE")
            consultation_revision = self._consultation_reader_factory(session).get_revision(
                tenant_id=context.tenant_id,
                consultation_id=command.consultation_id,
            )
            if (
                consultation_revision is None
                or consultation_revision != command.consultation_revision
            ):
                raise ValueError("CONSULTATION_REQUIRED_OR_STALE")
        consultation_reference = None

        if command.consultation_id is not None:
            assert consultation_revision is not None
            consultation_reference = AggregateReference(
                aggregate_id=command.consultation_id,
                aggregate_type="CONSULTATION",
                tenant_id=UUID(str(context.tenant_id)),
                aggregate_revision=consultation_revision,
            )
        case = Case.create(
            case_id=command.case_id,
            tenant_id=UUID(str(context.tenant_id)),
            title=command.title,
            object_description=command.object_description,
            scope=scope,
            origin=origin,
            consultation_reference=consultation_reference,
        )
        scope_json = _scope_json(scope)
        scope_fingerprint = _sha256_json(scope_json)
        functional_identity_hash = _sha256_json(
            {
                "consultation_id": (
                    str(command.consultation_id) if command.consultation_id else None
                ),
                "origin_kind": command.origin_kind,
                "origin_reference_id": (
                    str(command.origin_reference_id) if command.origin_reference_id else None
                ),
                "scope": scope_json,
            }
        )
        repository = self._repository_factory(session)
        if repository.has_active_functional_identity(
            tenant_id=context.tenant_id,
            functional_identity_hash=functional_identity_hash,
        ):
            raise ValueError("DUPLICATE_FUNCTIONAL_IDENTITY")
        repository.create(
            aggregate_id=case.id,
            tenant_id=case.tenant_id,
            aggregate_revision=case.aggregate_revision,
            functional_identity_hash=functional_identity_hash,
            title=case.title,
            object_description=case.object_description,
            business_origin=command.origin_kind,
            origin_reference_id=command.origin_reference_id,
            origin_rationale=command.origin_rationale,
            consultation_id=command.consultation_id,
            consultation_scope_snapshot_json=scope_json if command.consultation_id else None,
            consultation_rationale=command.scope_justification,
            scope_kind="CUSTOM" if command.scope_kind == "CUSTOM" else command.scope_kind,
            scope_json=scope_json,
            scope_fingerprint=scope_fingerprint,
            actor_id=context.actor_id,
        )
        event = PendingDomainEvent(
            aggregate_type="CASE",
            aggregate_id=case.id,
            aggregate_revision=case.aggregate_revision,
            event_type="CASE_CREATED",
            payload={"case_id": str(case.id), "tenant_id": str(case.tenant_id)},
        )
        return HandlerOutcome(
            result_code="CASE_CREATED",
            aggregate_refs=(
                {
                    "aggregate_type": "AFF",
                    "aggregate_id": str(case.id),
                    "aggregate_revision": case.aggregate_revision,
                },
            ),
            events=(event,),
        )


def _scope_json(scope: CaseScope) -> dict[str, object]:
    return {
        "kind": scope.kind.value,
        "lot_numbers": list(scope.lot_numbers),
        "tranche_reference": scope.tranche_reference,
        "variant_reference": scope.variant_reference,
        "source_justification": scope.source_justification,
    }


def _sha256_json(value: dict[str, object]) -> str:
    canonical = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()
