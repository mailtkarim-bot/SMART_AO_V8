from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.pricing.application.import_commands import (
    CreatePricingImportPreviewCommand,
    CreatePricingImportRowCommand,
)
from app.modules.pricing.application.ports import CaseExistenceReader
from app.modules.pricing.infrastructure.models import (
    PricingImportBatchRecord,
    PricingImportRowRecord,
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


class PricingImportCreationService:
    """Authorize and persist one server-normalized pricing preview."""

    def __init__(
        self,
        *,
        case_reader: CaseExistenceReader,
        dispatcher: CommandDispatcher,
        policy: AuthorizationPolicyPort,
    ) -> None:
        self._case_reader = case_reader
        self._dispatcher = dispatcher
        self._policy = policy

    def create(
        self,
        *,
        actor: ActorContext,
        command: CreatePricingImportPreviewCommand,
        now: datetime,
    ) -> DispatchResult:
        """Resolve tenant and Case server-side before dispatching financial data."""
        if actor.actor_kind is not ActorKind.PATRON_ADMIN or actor.membership_id is None:
            raise PermissionError("PRICING_IMPORT_PATRON_REQUIRED")
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=Capability.FINANCIAL_REPORT_LINE_WRITE,
                resource=AuthorizationResource(
                    resource_type="PRICING_IMPORT",
                    resource_id=command.case_id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.FINANCIAL_PRIVATE,
                    case_id=command.case_id,
                ),
                evaluated_at=now,
            ),
        )
        if not decision.allowed:
            raise PermissionError(decision.code)
        if not self._case_reader.exists(
            tenant_id=actor.tenant_id,
            case_id=command.case_id,
        ):
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
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
                case_id=command.case_id,
                correlation_id=actor.correlation_id,
            ),
        )


class CreatePricingImportPreviewHandler:
    """Persist a validated PREVIEWED batch and normalized rows in one transaction."""

    def execute(
        self,
        *,
        session: Session,
        command: CreatePricingImportPreviewCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        if context.actor_kind != ActorKind.PATRON_ADMIN.value or context.membership_id is None:
            raise CommandExecutionError("PRICING_IMPORT_PATRON_REQUIRED")
        case = session.scalar(
            sa.select(CaseRecord)
            .where(
                CaseRecord.tenant_id == context.tenant_id,
                CaseRecord.id == command.case_id,
            )
            .with_for_update()
        )
        if case is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")

        rows = _validate_rows(command.rows)
        batch_id = uuid4()
        valid_row_count = sum(not row.errors for row in rows)
        error_count = sum(len(row.errors) for row in rows)
        total_minor = sum(
            row.total_minor or 0 for row in rows if not row.errors and row.total_minor is not None
        )
        batch = PricingImportBatchRecord(
            id=batch_id,
            tenant_id=context.tenant_id,
            case_id=command.case_id,
            document_kind=command.document_kind,
            source_sha256=command.source_sha256,
            state="PREVIEWED",
            aggregate_revision=1,
            row_count=len(rows),
            valid_row_count=valid_row_count,
            error_count=error_count,
            total_minor=total_minor,
            actor_id=context.actor_id,
            membership_id=context.membership_id,
            command_id=command.command_id,
            idempotency_key=command.idempotency_key,
            correlation_id=command.correlation_id,
        )
        session.add(batch)
        session.add_all(
            PricingImportRowRecord(
                id=uuid4(),
                tenant_id=context.tenant_id,
                batch_id=batch_id,
                row_number=row.row_number,
                code=row.code,
                designation=row.designation,
                unit=row.unit,
                quantity_decimal=row.quantity_decimal,
                unit_price_minor=row.unit_price_minor,
                total_minor=row.total_minor,
                error_codes_json=list(row.errors),
            )
            for row in rows
        )
        return HandlerOutcome(
            result_code="PRICING_IMPORT_PREVIEWED",
            aggregate_refs=(
                {
                    "aggregate_type": "PricingImportBatch",
                    "aggregate_id": str(batch_id),
                    "aggregate_revision": 1,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="PricingImportBatch",
                    aggregate_id=batch_id,
                    aggregate_revision=1,
                    event_type="PricingImportPreviewed",
                    payload={
                        "case_id": str(command.case_id),
                        "batch_id": str(batch_id),
                        "document_kind": command.document_kind,
                        "row_count": len(rows),
                        "valid_row_count": valid_row_count,
                        "error_count": error_count,
                    },
                ),
            ),
        )


def _validate_rows(rows: list[CreatePricingImportRowCommand]) -> tuple[
    CreatePricingImportRowCommand, ...
]:
    if not rows:
        raise CommandExecutionError("IMPORT_ROWS_REQUIRED")
    row_numbers = [row.row_number for row in rows]
    if len(row_numbers) != len(set(row_numbers)):
        raise CommandExecutionError("IMPORT_ROW_NUMBER_DUPLICATE")
    for row in rows:
        if row.errors:
            continue
        if (
            not row.designation
            or not row.designation.strip()
            or not row.quantity_decimal
            or not row.quantity_decimal.strip()
            or row.total_minor is None
        ):
            raise CommandExecutionError("IMPORT_ROWS_INVALID")
    return tuple(rows)


def pricing_import_creation_handlers() -> dict[str, CreatePricingImportPreviewHandler]:
    """Return the closed dispatcher registry for PREVIEWED batch creation."""
    return {"CreatePricingImportPreview": CreatePricingImportPreviewHandler()}
