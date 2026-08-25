from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.membership.infrastructure.records import CaseAssignmentRecord
from app.modules.membership.public.text_safety import contains_forbidden_text
from app.modules.preparation.application.review_commands import (
    AddPreparationCorrectionCommand,
    CreateTechnicalResponseDraftCommand,
    DecidePreparationReviewCommand,
    RequestPreparationReviewCommand,
)
from app.modules.preparation.infrastructure.models import (
    GeneratedTechnicalDocumentRecord,
    PreparationPackageRecord,
    PreparationReviewCorrectionRecord,
    PreparationReviewRecord,
    TechnicalResponseDraftRecord,
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
from app.platform.storage.ports import GeneratedDocumentStorage

_REVIEW_COMMANDS = frozenset(
    {
        "RequestPreparationReview",
        "DecidePreparationReview",
        "AddPreparationCorrection",
        "CreateTechnicalResponseDraft",
    }
)
_ALLOWED_SECTION_CODES = frozenset(
    {"COVER", "UNDERSTANDING", "METHOD", "RESOURCES", "SCHEDULE", "RISKS", "SOURCES"}
)


class PreparationReviewService:
    """Facade that separates collaborator requests from patron review authority."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        dispatcher: CommandDispatcher,
        policy: AuthorizationPolicyPort,
        storage: GeneratedDocumentStorage,
    ) -> None:
        self._session_factory = session_factory
        self._dispatcher = dispatcher
        self._policy = policy
        self._storage = storage

    def execute(self, *, actor: ActorContext, command, now: datetime) -> DispatchResult:
        is_collaborator_write = command.command_type in {
            "RequestPreparationReview",
            "CreateTechnicalResponseDraft",
        }
        is_patron_review = command.command_type in {
            "DecidePreparationReview",
            "AddPreparationCorrection",
        }
        if is_collaborator_write and actor.actor_kind is not ActorKind.COLLABORATEUR:
            raise PermissionError("COLLABORATOR_REQUIRED")
        if is_patron_review and actor.actor_kind is not ActorKind.PATRON_ADMIN:
            raise PermissionError("PATRON_REQUIRED")
        package = self._resolve_package(actor=actor, command=command)
        if package is None:
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        capability = (
            Capability.PREPARATION_REVIEW_REQUEST
            if command.command_type == "RequestPreparationReview"
            else Capability.PREPARATION_DOCUMENT_WRITE
            if command.command_type == "CreateTechnicalResponseDraft"
            else Capability.PREPARATION_REVIEW_DECIDE
        )
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=capability,
                resource=AuthorizationResource(
                    resource_type="PREPARATION_PACKAGE",
                    resource_id=package.id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                    case_id=package.case_id,
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
                case_id=package.case_id,
                correlation_id=actor.correlation_id,
            ),
        )

    def _resolve_package(self, *, actor: ActorContext, command) -> PreparationPackageRecord | None:
        with self._session_factory() as session:
            package = session.scalar(
                sa.select(PreparationPackageRecord).where(
                    PreparationPackageRecord.tenant_id == actor.tenant_id,
                    PreparationPackageRecord.id == command.package_id,
                )
            )
            if package is None:
                return None
            if actor.actor_kind is ActorKind.PATRON_ADMIN:
                return package
            assignment = session.scalar(
                sa.select(CaseAssignmentRecord).where(
                    CaseAssignmentRecord.tenant_id == actor.tenant_id,
                    CaseAssignmentRecord.id == package.assignment_id,
                    CaseAssignmentRecord.case_id == package.case_id,
                    CaseAssignmentRecord.membership_id == actor.membership_id,
                    CaseAssignmentRecord.state == "ACTIVE",
                )
            )
            if (
                assignment is None
                or Capability.WORK_TASK_WRITE.value not in assignment.scope_actions_json
            ):
                return None
            return package


class PreparationReviewHandler:
    """Own immutable review transitions, corrections and draft versions."""

    def __init__(self, *, storage: GeneratedDocumentStorage) -> None:
        self._storage = storage

    def execute(self, *, session: Session, command, context: CommandContext) -> HandlerOutcome:
        if command.command_type == "RequestPreparationReview":
            return self._request(session=session, command=command, context=context)
        if command.command_type == "DecidePreparationReview":
            return self._decide(session=session, command=command, context=context)
        if command.command_type == "AddPreparationCorrection":
            return self._correction(session=session, command=command, context=context)
        if command.command_type == "CreateTechnicalResponseDraft":
            return self._draft(session=session, command=command, context=context)
        raise CommandExecutionError(
            f"unsupported preparation review command: {command.command_type}"
        )

    def _package(
        self, *, session: Session, context: CommandContext, package_id: UUID
    ) -> PreparationPackageRecord:
        package = session.scalar(
            sa.select(PreparationPackageRecord)
            .where(
                PreparationPackageRecord.tenant_id == context.tenant_id,
                PreparationPackageRecord.id == package_id,
            )
            .with_for_update()
        )
        if package is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        return package

    def _document(
        self,
        *,
        session: Session,
        context: CommandContext,
        package: PreparationPackageRecord,
        document_id: UUID,
        version: int,
    ) -> GeneratedTechnicalDocumentRecord:
        document = session.scalar(
            sa.select(GeneratedTechnicalDocumentRecord).where(
                GeneratedTechnicalDocumentRecord.tenant_id == context.tenant_id,
                GeneratedTechnicalDocumentRecord.id == document_id,
                GeneratedTechnicalDocumentRecord.package_id == package.id,
                GeneratedTechnicalDocumentRecord.version == version,
            )
        )
        if document is None:
            raise CommandExecutionError("TARGET_VERSION_NOT_FOUND")
        return document

    def _latest_review(
        self, *, session: Session, context: CommandContext, review_id: UUID
    ) -> PreparationReviewRecord | None:
        return session.scalar(
            sa.select(PreparationReviewRecord)
            .where(
                PreparationReviewRecord.tenant_id == context.tenant_id,
                PreparationReviewRecord.review_id == review_id,
            )
            .order_by(PreparationReviewRecord.revision.desc())
            .limit(1)
            .with_for_update()
        )

    def _request(
        self, *, session: Session, command: RequestPreparationReviewCommand, context: CommandContext
    ) -> HandlerOutcome:
        if context.actor_kind != ActorKind.COLLABORATEUR.value:
            raise CommandExecutionError("COLLABORATOR_REQUIRED")
        package = self._package(session=session, context=context, package_id=command.package_id)
        if package.aggregate_revision != command.expected_package_revision:
            raise CommandExecutionError("VERSION_CONFLICT")
        self._document(
            session=session,
            context=context,
            package=package,
            document_id=command.target_document_id,
            version=command.target_version,
        )
        if (
            self._latest_review(session=session, context=context, review_id=command.review_id)
            is not None
        ):
            raise CommandExecutionError("REVIEW_ALREADY_EXISTS")
        review = PreparationReviewRecord(
            id=command.command_id,
            tenant_id=context.tenant_id,
            review_id=command.review_id,
            package_id=package.id,
            target_document_id=command.target_document_id,
            target_version=command.target_version,
            revision=1,
            state="REQUESTED",
            decision_code=None,
            decision_note=None,
            actor_id=context.actor_id,
            membership_id=context.membership_id,
            command_id=command.command_id,
            idempotency_key=command.idempotency_key,
            correlation_id=command.correlation_id,
        )
        session.add(review)
        package.aggregate_revision += 1
        package.state = "A_REVIEW"
        return self._outcome(
            aggregate_type="PreparationReview",
            aggregate_id=command.review_id,
            revision=1,
            event_type="PreparationReviewRequested",
            payload={
                "review_id": str(command.review_id),
                "target_document_id": str(command.target_document_id),
                "target_version": command.target_version,
                "state": "REQUESTED",
            },
            result_code="PREPARATION_REVIEW_REQUESTED",
        )

    def _decide(
        self, *, session: Session, command: DecidePreparationReviewCommand, context: CommandContext
    ) -> HandlerOutcome:
        if context.actor_kind != ActorKind.PATRON_ADMIN.value:
            raise CommandExecutionError("PATRON_REQUIRED")
        package = self._package(session=session, context=context, package_id=command.package_id)
        latest = self._latest_review(session=session, context=context, review_id=command.review_id)
        if (
            latest is None
            or latest.package_id != package.id
            or latest.target_document_id != command.target_document_id
        ):
            raise CommandExecutionError("REVIEW_NOT_FOUND")
        if latest.revision != command.expected_review_revision:
            raise CommandExecutionError("VERSION_CONFLICT")
        if latest.state not in {"REQUESTED", "RETURNED_WITH_CORRECTIONS"}:
            raise CommandExecutionError("REVIEW_STATE_INVALID")
        state = {
            "ACCEPTED": "ACCEPTED",
            "CORRECTIONS_REQUIRED": "RETURNED_WITH_CORRECTIONS",
            "REJECTED": "REJECTED",
        }[command.decision_code]
        revision = latest.revision + 1
        session.add(
            PreparationReviewRecord(
                id=command.command_id,
                tenant_id=context.tenant_id,
                review_id=latest.review_id,
                package_id=package.id,
                target_document_id=latest.target_document_id,
                target_version=latest.target_version,
                revision=revision,
                state=state,
                decision_code=command.decision_code,
                decision_note=command.decision_note,
                actor_id=context.actor_id,
                membership_id=context.membership_id,
                command_id=command.command_id,
                idempotency_key=command.idempotency_key,
                correlation_id=command.correlation_id,
            )
        )
        package.aggregate_revision += 1
        package.state = (
            "READY"
            if state == "ACCEPTED"
            else "A_REVIEW"
            if state == "RETURNED_WITH_CORRECTIONS"
            else "BLOCKED"
        )
        return self._outcome(
            aggregate_type="PreparationReview",
            aggregate_id=latest.review_id,
            revision=revision,
            event_type="PreparationReviewDecided",
            payload={
                "review_id": str(latest.review_id),
                "revision": revision,
                "decision_code": command.decision_code,
                "state": state,
            },
            result_code="PREPARATION_REVIEW_DECIDED",
        )

    def _correction(
        self, *, session: Session, command: AddPreparationCorrectionCommand, context: CommandContext
    ) -> HandlerOutcome:
        if context.actor_kind != ActorKind.PATRON_ADMIN.value:
            raise CommandExecutionError("PATRON_REQUIRED")
        package = self._package(session=session, context=context, package_id=command.package_id)
        latest = self._latest_review(session=session, context=context, review_id=command.review_id)
        if (
            latest is None
            or latest.package_id != package.id
            or latest.target_document_id != command.target_document_id
        ):
            raise CommandExecutionError("REVIEW_NOT_FOUND")
        if latest.state != "RETURNED_WITH_CORRECTIONS":
            raise CommandExecutionError("CORRECTIONS_NOT_REQUESTED")
        revision = (
            session.scalar(
                sa.select(
                    sa.func.coalesce(sa.func.max(PreparationReviewCorrectionRecord.revision), 0)
                ).where(
                    PreparationReviewCorrectionRecord.tenant_id == context.tenant_id,
                    PreparationReviewCorrectionRecord.review_id == latest.review_id,
                )
            )
            + 1
        )
        session.add(
            PreparationReviewCorrectionRecord(
                id=command.command_id,
                tenant_id=context.tenant_id,
                review_id=latest.review_id,
                review_revision=latest.revision,
                target_document_id=latest.target_document_id,
                revision=revision,
                correction_code=command.correction_code,
                instruction=command.instruction,
                source_locator=command.source_locator,
                actor_id=context.actor_id,
                membership_id=context.membership_id,
                command_id=command.command_id,
                idempotency_key=command.idempotency_key,
                correlation_id=command.correlation_id,
            )
        )
        package.aggregate_revision += 1
        return self._outcome(
            aggregate_type="PreparationReview",
            aggregate_id=latest.review_id,
            revision=revision,
            event_type="PreparationCorrectionAdded",
            payload={
                "review_id": str(latest.review_id),
                "correction_revision": revision,
                "correction_code": command.correction_code,
            },
            result_code="PREPARATION_CORRECTION_ADDED",
        )

    def _draft(
        self,
        *,
        session: Session,
        command: CreateTechnicalResponseDraftCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        if context.actor_kind != ActorKind.COLLABORATEUR.value:
            raise CommandExecutionError("COLLABORATOR_REQUIRED")
        package = self._package(session=session, context=context, package_id=command.package_id)
        if package.aggregate_revision != command.expected_package_revision:
            raise CommandExecutionError("VERSION_CONFLICT")
        if any(code not in _ALLOWED_SECTION_CODES for code in command.section_codes):
            raise CommandExecutionError("SECTION_CODE_INVALID")
        document = session.scalar(
            sa.select(GeneratedTechnicalDocumentRecord).where(
                GeneratedTechnicalDocumentRecord.tenant_id == context.tenant_id,
                GeneratedTechnicalDocumentRecord.id == command.source_document_id,
                GeneratedTechnicalDocumentRecord.package_id == package.id,
            )
        )
        if document is None:
            raise CommandExecutionError("SOURCE_DOCUMENT_NOT_FOUND")
        version = (
            session.scalar(
                sa.select(
                    sa.func.coalesce(sa.func.max(TechnicalResponseDraftRecord.version), 0)
                ).where(
                    TechnicalResponseDraftRecord.tenant_id == context.tenant_id,
                    TechnicalResponseDraftRecord.draft_id == command.draft_id,
                )
            )
            + 1
        )
        refs = sorted({str(ref) for ref in command.source_refs})
        sections = sorted(set(command.section_codes))
        content = (
            "# Brouillon de réponse technique\n\n"
            "Ce brouillon est un candidat soumis à revue humaine.\n"
            f"Sections: {', '.join(sections)}\n"
            f"Sources internes: {', '.join(refs)}\n"
        ).encode()
        if contains_forbidden_text(content.decode("utf-8")):
            raise CommandExecutionError("FINANCIAL_DATA_FORBIDDEN")
        storage_key = (
            f"technical-response-drafts/{context.tenant_id}/{package.id}/"
            f"{command.draft_id}/{version}.md"
        )
        content_sha256 = self._storage.write(storage_key=storage_key, content=content)
        session.add(
            TechnicalResponseDraftRecord(
                id=command.command_id,
                tenant_id=context.tenant_id,
                draft_id=command.draft_id,
                package_id=package.id,
                source_document_id=document.id,
                version=version,
                state="DRAFT",
                section_codes_json=sections,
                source_refs_json=refs,
                responsible_role=command.responsible_role,
                content_sha256=content_sha256,
                storage_key=storage_key,
                actor_id=context.actor_id,
                membership_id=context.membership_id,
                command_id=command.command_id,
                idempotency_key=command.idempotency_key,
                correlation_id=command.correlation_id,
            )
        )
        package.aggregate_revision += 1
        package.state = "IN_PREPARATION"
        return self._outcome(
            aggregate_type="TechnicalResponseDraft",
            aggregate_id=command.draft_id,
            revision=version,
            event_type="TechnicalResponseDraftCreated",
            payload={
                "draft_id": str(command.draft_id),
                "version": version,
                "package_id": str(package.id),
                "state": "DRAFT",
            },
            result_code="TECHNICAL_RESPONSE_DRAFT_CREATED",
        )

    @staticmethod
    def _outcome(
        *,
        aggregate_type: str,
        aggregate_id: UUID,
        revision: int,
        event_type: str,
        payload: dict[str, object],
        result_code: str,
    ) -> HandlerOutcome:
        return HandlerOutcome(
            result_code=result_code,
            aggregate_refs=(
                {
                    "aggregate_type": aggregate_type,
                    "aggregate_id": str(aggregate_id),
                    "aggregate_revision": revision,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type=aggregate_type,
                    aggregate_id=aggregate_id,
                    aggregate_revision=revision,
                    event_type=event_type,
                    payload=payload,
                ),
            ),
        )


def preparation_review_handlers(
    *, storage: GeneratedDocumentStorage
) -> dict[str, PreparationReviewHandler]:
    handler = PreparationReviewHandler(storage=storage)
    return {command_type: handler for command_type in _REVIEW_COMMANDS}
