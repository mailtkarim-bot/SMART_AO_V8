"""Transaction-bound command dispatch, durable idempotence and transactional outbox.

The dispatcher is intentionally generic: it owns technical transaction mechanics
but no BTP transition. Each registered handler can mutate only its own root and
returns typed event facts for the platform to persist atomically.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Any, Protocol
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.platform.persistence.models import (
    CommandReceiptRecord,
    DomainEventRecord,
    OutboxMessageRecord,
)


class CommandExecutionError(RuntimeError):
    """Raised when a command fails before its transaction can be committed."""


class IdempotencyKeyReusedError(CommandExecutionError):
    """Raised when one idempotency key is reused with another request hash."""


class CommandInProgressError(CommandExecutionError):
    """Raised when another execution owns a non-terminal command receipt."""


@dataclass(frozen=True, slots=True)
class CommandContext:
    """Trusted command facts resolved by the server, never by an HTTP body."""

    tenant_id: UUID | str
    actor_id: UUID | str
    actor_kind: str
    received_at: datetime
    identity_id: UUID | str | None = None
    session_id: UUID | str | None = None
    case_id: UUID | str | None = None
    correlation_id: UUID | str | None = None


@dataclass(frozen=True, slots=True)
class PendingDomainEvent:
    """A domain fact ready to become one event and one outbox message."""

    aggregate_type: str
    aggregate_id: UUID
    aggregate_revision: int
    event_type: str
    payload: Mapping[str, object]
    topic: str = "cockpit_projection"
    payload_version: int = 1


@dataclass(frozen=True, slots=True)
class HandlerOutcome:
    """The technical information needed to complete a successful command."""

    result_code: str
    aggregate_refs: tuple[Mapping[str, object], ...]
    events: tuple[PendingDomainEvent, ...]


@dataclass(frozen=True, slots=True)
class DispatchResult:
    """Durable response persisted in the command receipt and replayed verbatim."""

    status: str
    command_id: str
    idempotency_key: str
    result_code: str
    aggregate_refs: tuple[Mapping[str, object], ...]
    event_ids: tuple[str, ...]
    replayed: bool = False

    @classmethod
    def from_receipt(cls, receipt: CommandReceiptRecord, *, replayed: bool) -> DispatchResult:
        response = receipt.response_body_json or {}
        return cls(
            status=str(response["status"]),
            command_id=str(response["command_id"]),
            idempotency_key=str(response["idempotency_key"]),
            result_code=str(response["result_code"]),
            aggregate_refs=tuple(response["aggregate_refs"]),
            event_ids=tuple(response["event_ids"]),
            replayed=replayed,
        )

    def as_receipt_body(self) -> dict[str, object]:
        return {
            "status": self.status,
            "command_id": self.command_id,
            "idempotency_key": self.idempotency_key,
            "result_code": self.result_code,
            "aggregate_refs": list(self.aggregate_refs),
            "event_ids": list(self.event_ids),
        }


class CommandHandler(Protocol):
    """A handler owns one aggregate root and produces serializable facts."""

    def execute(
        self,
        *,
        session: Session,
        command: Any,
        context: CommandContext,
    ) -> HandlerOutcome: ...


class CommandDispatcher:
    """Dispatches registered typed commands with transactional durability."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        handlers: Mapping[str, CommandHandler],
    ) -> None:
        self._session_factory = session_factory
        self._handlers = dict(handlers)

    def dispatch(self, *, command: Any, context: CommandContext) -> DispatchResult:
        command_type = str(command.command_type)
        handler = self._handlers.get(command_type)
        if handler is None:
            raise CommandExecutionError(f"unsupported command type: {command_type}")

        request_hash = canonical_request_hash(command)
        try:
            with self._session_factory.begin() as session:
                receipt = self._find_receipt(
                    session=session,
                    tenant_id=context.tenant_id,
                    actor_id=context.actor_id,
                    command_type=command_type,
                    idempotency_key=command.idempotency_key,
                )
                if receipt is not None:
                    return self._resolve_existing_receipt(receipt, request_hash=request_hash)

                receipt = CommandReceiptRecord(
                    id=uuid4(),
                    tenant_id=context.tenant_id,
                    actor_id=context.actor_id,
                    command_id=command.command_id,
                    command_type=command_type,
                    idempotency_key=command.idempotency_key,
                    request_hash=request_hash,
                    correlation_id=command.correlation_id,
                    status="PROCESSING",
                    lease_expires_at=None,
                    event_ids_json=[],
                )
                session.add(receipt)
                session.flush()

                outcome = handler.execute(session=session, command=command, context=context)
                event_ids = self._persist_events_and_outbox(
                    session=session,
                    context=context,
                    command=command,
                    events=outcome.events,
                )
                result = DispatchResult(
                    status="SUCCEEDED",
                    command_id=str(command.command_id),
                    idempotency_key=str(command.idempotency_key),
                    result_code=outcome.result_code,
                    aggregate_refs=outcome.aggregate_refs,
                    event_ids=event_ids,
                )
                receipt.status = "SUCCEEDED"
                receipt.aggregate_refs_json = {"aggregate_refs": list(outcome.aggregate_refs)}
                receipt.http_status = 201
                receipt.result_code = outcome.result_code
                receipt.response_body_json = result.as_receipt_body()
                receipt.event_ids_json = list(event_ids)
                receipt.completed_at = context.received_at
                return result
        except (IdempotencyKeyReusedError, CommandInProgressError):
            raise
        except IntegrityError as error:
            raise CommandExecutionError("command persistence failed before commit") from error
        except CommandExecutionError:
            raise
        except Exception as error:
            raise CommandExecutionError("command failed before commit") from error

    @staticmethod
    def _find_receipt(
        *,
        session: Session,
        tenant_id: UUID | str,
        actor_id: UUID | str,
        command_type: str,
        idempotency_key: UUID,
    ) -> CommandReceiptRecord | None:
        return session.scalar(
            sa.select(CommandReceiptRecord)
            .where(
                CommandReceiptRecord.tenant_id == tenant_id,
                CommandReceiptRecord.actor_id == actor_id,
                CommandReceiptRecord.command_type == command_type,
                CommandReceiptRecord.idempotency_key == idempotency_key,
            )
            .with_for_update()
        )

    @staticmethod
    def _resolve_existing_receipt(
        receipt: CommandReceiptRecord,
        *,
        request_hash: str,
    ) -> DispatchResult:
        if receipt.request_hash != request_hash:
            raise IdempotencyKeyReusedError("idempotency key was reused with another request")
        if receipt.status == "SUCCEEDED":
            return DispatchResult.from_receipt(receipt, replayed=True)
        raise CommandInProgressError("command receipt is already being processed")

    @staticmethod
    def _persist_events_and_outbox(
        *,
        session: Session,
        context: CommandContext,
        command: Any,
        events: tuple[PendingDomainEvent, ...],
    ) -> tuple[str, ...]:
        event_ids: list[str] = []
        for event in events:
            event_id = uuid4()
            event_payload = {
                "event_id": str(event_id),
                "event_type": event.event_type,
                "aggregate_type": event.aggregate_type,
                "aggregate_id": str(event.aggregate_id),
                "aggregate_revision": event.aggregate_revision,
                "data": dict(event.payload),
            }
            session.add(
                DomainEventRecord(
                    id=event_id,
                    tenant_id=context.tenant_id,
                    aggregate_type=event.aggregate_type,
                    aggregate_id=event.aggregate_id,
                    aggregate_revision=event.aggregate_revision,
                    event_type=event.event_type,
                    payload_version=event.payload_version,
                    payload_json=event_payload,
                    actor_id=context.actor_id,
                    command_id=command.command_id,
                    correlation_id=command.correlation_id,
                    causation_id=command.command_id,
                )
            )
            session.add(
                OutboxMessageRecord(
                    id=uuid4(),
                    tenant_id=context.tenant_id,
                    event_id=event_id,
                    topic=event.topic,
                    payload_version=event.payload_version,
                    payload_json=event_payload,
                    status="PENDING",
                    attempt_count=0,
                    next_attempt_at=None,
                    dedupe_key=f"{event.topic}:{event_id}",
                )
            )
            event_ids.append(str(event_id))
        return tuple(event_ids)


def canonical_request_hash(command: Any) -> str:
    """Hash only the semantic request, excluding correlation and transport IDs."""

    serialized = command.model_dump(mode="json")
    payload = {
        field: value
        for field, value in serialized.items()
        if field not in {"command_id", "idempotency_key", "correlation_id"}
    }
    canonical = json.dumps(
        {"command_type": command.command_type, "payload": payload},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return sha256(canonical.encode("utf-8")).hexdigest()
