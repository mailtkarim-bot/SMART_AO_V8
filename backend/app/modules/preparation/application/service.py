from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.modules.dce.infrastructure.models.dce_requirement_confirmations import (
    DceRequirementConfirmationCurrentRecord,
)
from app.modules.dce.infrastructure.models.dce_requirements import DceRequirementRecord
from app.modules.dce.infrastructure.models.dce_version import DceVersionRecord
from app.modules.membership.application.collab_info_blockers_commands import _contains_forbidden
from app.modules.preparation.application.commands import (
    EvaluatePreparationReadinessCommand,
    GenerateTechnicalDocumentCommand,
)
from app.modules.preparation.infrastructure.document_storage import GeneratedDocumentStorage
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
from app.platform.security.models import (
    CaseAssignmentRecord,
    CaseCapabilityGapRecord,
    CaseCapabilityProposalRecord,
    CollaboratorTaskRecord,
    CollaboratorTaskResultRecord,
    EnterpriseCapabilityProofLinkRecord,
    EnterpriseCapabilityRecord,
    EnterpriseCapabilityVersionRecord,
    EnterpriseDocumentRecord,
    GeneratedTechnicalDocumentRecord,
    PreparationPackageRecord,
    PreparationReadinessRecord,
)

_PREPARATION_COMMANDS = frozenset({"EvaluatePreparationReadiness", "GenerateTechnicalDocument"})


class PreparationService:
    """Facade for server-resolved preparation readiness and document generation."""

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
        if actor.actor_kind is not ActorKind.COLLABORATEUR or actor.membership_id is None:
            raise PermissionError("COLLABORATOR_REQUIRED")
        assignment = self._resolve_assignment(actor=actor, command=command)
        if assignment is None:
            raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
        capability = (
            Capability.PREPARATION_READINESS_WRITE
            if command.command_type == "EvaluatePreparationReadiness"
            else Capability.PREPARATION_DOCUMENT_WRITE
        )
        decision = self._policy.authorize(
            context=actor,
            request=AuthorizationRequest(
                action=capability,
                resource=AuthorizationResource(
                    resource_type="PREPARATION_PACKAGE",
                    resource_id=command.package_id,
                    tenant_id=actor.tenant_id,
                    classification=DataClassification.INTERNAL_OPERATIONAL,
                    case_id=assignment.case_id,
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
                case_id=assignment.case_id,
                correlation_id=actor.correlation_id,
            ),
        )

    def read_package(
        self, *, actor: ActorContext, package_id: UUID, now: datetime
    ) -> tuple[
        PreparationPackageRecord,
        PreparationReadinessRecord | None,
        tuple[GeneratedTechnicalDocumentRecord, ...],
    ]:
        if actor.actor_kind is not ActorKind.COLLABORATEUR or actor.membership_id is None:
            raise PermissionError("COLLABORATOR_REQUIRED")
        with self._session_factory() as session:
            package = session.scalar(
                sa.select(PreparationPackageRecord).where(
                    PreparationPackageRecord.tenant_id == actor.tenant_id,
                    PreparationPackageRecord.id == package_id,
                )
            )
            if package is None:
                raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
            assignment = session.scalar(
                sa.select(CaseAssignmentRecord).where(
                    CaseAssignmentRecord.tenant_id == actor.tenant_id,
                    CaseAssignmentRecord.id == package.assignment_id,
                    CaseAssignmentRecord.case_id == package.case_id,
                    CaseAssignmentRecord.membership_id == actor.membership_id,
                    CaseAssignmentRecord.state == "ACTIVE",
                )
            )
            if assignment is None:
                raise PermissionError("NOT_FOUND_OR_FORBIDDEN")
            decision = self._policy.authorize(
                context=actor,
                request=AuthorizationRequest(
                    action=Capability.PREPARATION_READINESS_WRITE,
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
            readiness = session.scalar(
                sa.select(PreparationReadinessRecord)
                .where(
                    PreparationReadinessRecord.tenant_id == actor.tenant_id,
                    PreparationReadinessRecord.package_id == package.id,
                )
                .order_by(PreparationReadinessRecord.revision.desc())
                .limit(1)
            )
            documents = tuple(
                session.scalars(
                    sa.select(GeneratedTechnicalDocumentRecord)
                    .where(
                        GeneratedTechnicalDocumentRecord.tenant_id == actor.tenant_id,
                        GeneratedTechnicalDocumentRecord.package_id == package.id,
                    )
                    .order_by(
                        GeneratedTechnicalDocumentRecord.version,
                        GeneratedTechnicalDocumentRecord.id,
                    )
                ).all()
            )
            return package, readiness, documents

    def _resolve_assignment(self, *, actor: ActorContext, command) -> CaseAssignmentRecord | None:
        with self._session_factory() as session:
            if command.command_type == "GenerateTechnicalDocument":
                package = session.scalar(
                    sa.select(PreparationPackageRecord).where(
                        PreparationPackageRecord.tenant_id == actor.tenant_id,
                        PreparationPackageRecord.id == command.package_id,
                    )
                )
                if package is None:
                    return None
                assignment_id = package.assignment_id
                case_id = package.case_id
            else:
                assignment_id = command.assignment_id
                case_id = command.case_id
            assignment = session.scalar(
                sa.select(CaseAssignmentRecord).where(
                    CaseAssignmentRecord.tenant_id == actor.tenant_id,
                    CaseAssignmentRecord.id == assignment_id,
                    CaseAssignmentRecord.case_id == case_id,
                    CaseAssignmentRecord.membership_id == actor.membership_id,
                    CaseAssignmentRecord.state == "ACTIVE",
                )
            )
            if assignment is None:
                return None
            if assignment.starts_at > datetime.now(tz=assignment.starts_at.tzinfo):
                return None
            if assignment.ends_at is not None and assignment.ends_at <= datetime.now(
                tz=assignment.ends_at.tzinfo
            ):
                return None
            if Capability.WORK_TASK_WRITE.value not in assignment.scope_actions_json:
                return None
            return assignment


class PreparationHandler:
    """Own preparation package revisions, readiness history and document versions."""

    def __init__(self, *, storage: GeneratedDocumentStorage) -> None:
        self._storage = storage

    def execute(self, *, session: Session, command, context: CommandContext) -> HandlerOutcome:
        if context.actor_kind != ActorKind.COLLABORATEUR.value or context.membership_id is None:
            raise CommandExecutionError("COLLABORATOR_REQUIRED")
        if command.command_type == "EvaluatePreparationReadiness":
            return self._evaluate(session=session, command=command, context=context)
        if command.command_type == "GenerateTechnicalDocument":
            return self._generate(session=session, command=command, context=context)
        raise CommandExecutionError(f"unsupported preparation command: {command.command_type}")

    def _ensure_assignment(
        self, *, session: Session, package: PreparationPackageRecord, context: CommandContext
    ) -> None:
        assignment = session.scalar(
            sa.select(CaseAssignmentRecord).where(
                CaseAssignmentRecord.tenant_id == context.tenant_id,
                CaseAssignmentRecord.id == package.assignment_id,
                CaseAssignmentRecord.case_id == package.case_id,
                CaseAssignmentRecord.membership_id == context.membership_id,
            )
        )
        if assignment is None or assignment.state != "ACTIVE":
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        if Capability.WORK_TASK_WRITE.value not in assignment.scope_actions_json:
            raise CommandExecutionError("ASSIGNMENT_SCOPE_FORBIDDEN")

    def _evaluate(
        self,
        *,
        session: Session,
        command: EvaluatePreparationReadinessCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        package = session.scalar(
            sa.select(PreparationPackageRecord)
            .where(
                PreparationPackageRecord.tenant_id == context.tenant_id,
                PreparationPackageRecord.id == command.package_id,
            )
            .with_for_update()
        )
        if package is None:
            if command.expected_revision != 0:
                raise CommandExecutionError("VERSION_CONFLICT")
            package = PreparationPackageRecord(
                id=command.package_id,
                tenant_id=context.tenant_id,
                case_id=command.case_id,
                assignment_id=command.assignment_id,
                dce_version_id=command.dce_version_id,
                state="IN_PREPARATION",
                aggregate_revision=0,
                created_by_actor_id=context.actor_id,
                membership_id=context.membership_id,
            )
            session.add(package)
            session.flush()
        else:
            if (
                package.case_id != command.case_id
                or package.assignment_id != command.assignment_id
                or package.dce_version_id != command.dce_version_id
            ):
                raise CommandExecutionError("PREPARATION_CONTEXT_MISMATCH")
            self._ensure_assignment(session=session, package=package, context=context)
            if package.aggregate_revision != command.expected_revision:
                raise CommandExecutionError("VERSION_CONFLICT")
        dce = session.scalar(
            sa.select(DceVersionRecord).where(
                DceVersionRecord.tenant_id == context.tenant_id,
                DceVersionRecord.id == package.dce_version_id,
            )
        )
        if dce is None:
            raise CommandExecutionError("DCE_NOT_FOUND_OR_FORBIDDEN")
        blocker_codes: set[str] = set()
        warning_codes: set[str] = set()
        if dce.analysis_readiness != "READY_FOR_ANALYSIS":
            blocker_codes.add("DCE_NOT_READY")
        requirements = list(
            session.scalars(
                sa.select(DceRequirementRecord).where(
                    DceRequirementRecord.tenant_id == context.tenant_id,
                    DceRequirementRecord.dce_version_id == package.dce_version_id,
                )
            ).all()
        )
        for requirement in requirements:
            confirmation = session.scalar(
                sa.select(DceRequirementConfirmationCurrentRecord).where(
                    DceRequirementConfirmationCurrentRecord.tenant_id == context.tenant_id,
                    DceRequirementConfirmationCurrentRecord.requirement_id == requirement.id,
                )
            )
            if confirmation is None or confirmation.outcome == "REVIEW_REQUIRED":
                blocker_codes.add("REQUIREMENT_UNCONFIRMED")
        tasks = list(
            session.scalars(
                sa.select(CollaboratorTaskRecord).where(
                    CollaboratorTaskRecord.tenant_id == context.tenant_id,
                    CollaboratorTaskRecord.case_id == package.case_id,
                    CollaboratorTaskRecord.assignment_id == package.assignment_id,
                )
            ).all()
        )
        for task in tasks:
            if task.state == "BLOCKED":
                blocker_codes.add("TASK_BLOCKED")
            elif task.state in {"READY", "IN_PROGRESS"}:
                has_result = session.scalar(
                    sa.select(sa.literal(True))
                    .where(
                        CollaboratorTaskResultRecord.tenant_id == context.tenant_id,
                        CollaboratorTaskResultRecord.task_id == task.id,
                    )
                    .limit(1)
                )
                if not has_result:
                    warning_codes.add("TASK_RESULT_MISSING")

        proposals = list(
            session.scalars(
                sa.select(CaseCapabilityProposalRecord).where(
                    CaseCapabilityProposalRecord.tenant_id == context.tenant_id,
                    CaseCapabilityProposalRecord.case_id == package.case_id,
                    CaseCapabilityProposalRecord.assignment_id == package.assignment_id,
                )
            ).all()
        )
        proposal_proof_manifest: list[dict[str, object]] = []
        for proposal in proposals:
            capability = session.scalar(
                sa.select(EnterpriseCapabilityRecord).where(
                    EnterpriseCapabilityRecord.tenant_id == context.tenant_id,
                    EnterpriseCapabilityRecord.id == proposal.capability_id,
                )
            )
            version = session.scalar(
                sa.select(EnterpriseCapabilityVersionRecord).where(
                    EnterpriseCapabilityVersionRecord.tenant_id == context.tenant_id,
                    EnterpriseCapabilityVersionRecord.id == proposal.capability_version_id,
                    EnterpriseCapabilityVersionRecord.capability_id == proposal.capability_id,
                )
            )
            links = list(
                session.scalars(
                    sa.select(EnterpriseCapabilityProofLinkRecord).where(
                        EnterpriseCapabilityProofLinkRecord.tenant_id == context.tenant_id,
                        EnterpriseCapabilityProofLinkRecord.capability_version_id
                        == proposal.capability_version_id,
                    )
                ).all()
            )
            proof_states: list[str] = []
            eligible_proof = False
            for link in links:
                document = session.scalar(
                    sa.select(EnterpriseDocumentRecord).where(
                        EnterpriseDocumentRecord.tenant_id == context.tenant_id,
                        EnterpriseDocumentRecord.id == link.document_id,
                    )
                )
                if (
                    document is None
                    or capability is None
                    or document.company_id != capability.company_id
                ):
                    proof_states.append("UNAUTHORIZED")
                    continue
                if document.verification_status != "VALIDATED":
                    proof_states.append("UNAUTHORIZED")
                    continue
                if document.expires_at is not None and document.expires_at <= context.received_at:
                    proof_states.append("EXPIRED")
                    continue
                eligible_proof = True
                proof_states.append("CURRENT")
            if capability is None or version is None or capability.state != "ACTIVE":
                blocker_codes.add("CAPABILITY_PROOF_UNAUTHORIZED")
            elif version.valid_from > context.received_at or (
                version.valid_until is not None and version.valid_until <= context.received_at
            ) or proposal.validity_state == "EXPIRED":
                blocker_codes.add("CAPABILITY_PROOF_EXPIRED")
            elif not links:
                blocker_codes.add("CAPABILITY_PROOF_MISSING")
            elif not eligible_proof:
                if "EXPIRED" in proof_states:
                    blocker_codes.add("CAPABILITY_PROOF_EXPIRED")
                else:
                    blocker_codes.add("CAPABILITY_PROOF_UNAUTHORIZED")
            proposal_proof_manifest.append(
                {
                    "proposal_id": str(proposal.id),
                    "capability_version_id": str(proposal.capability_version_id),
                    "proof_states": sorted(proof_states),
                }
            )

        gaps = list(
            session.scalars(
                sa.select(CaseCapabilityGapRecord).where(
                    CaseCapabilityGapRecord.tenant_id == context.tenant_id,
                    CaseCapabilityGapRecord.case_id == package.case_id,
                    CaseCapabilityGapRecord.assignment_id == package.assignment_id,
                )
            ).all()
        )
        if any(gap.severity == "BLOCKING" for gap in gaps):
            blocker_codes.add("CAPABILITY_GAP_BLOCKING")
        elif any(gap.severity == "IMPORTANT" for gap in gaps):
            warning_codes.add("CAPABILITY_GAP_IMPORTANT")

        state = "BLOCKED" if blocker_codes else "READY_WITH_WARNINGS" if warning_codes else "READY"
        revision = package.aggregate_revision + 1
        manifest = {
            "case_id": str(package.case_id),
            "assignment_id": str(package.assignment_id),
            "dce_version_id": str(package.dce_version_id),
            "requirements": sorted(str(item.id) for item in requirements),
            "tasks": sorted(str(item.id) for item in tasks),
            "capability_assessments": proposal_proof_manifest,
            "gaps": sorted(
                {
                    "gap_id": str(gap.id),
                    "gap_kind": gap.gap_kind,
                    "severity": gap.severity,
                }
                for gap in gaps
            ),
            "blockers": sorted(blocker_codes),
            "warnings": sorted(warning_codes),
        }
        manifest_hash = hashlib.sha256(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        readiness = PreparationReadinessRecord(
            id=command.command_id,
            tenant_id=context.tenant_id,
            package_id=package.id,
            revision=revision,
            state=state,
            blocker_codes_json=sorted(blocker_codes),
            warning_codes_json=sorted(warning_codes),
            checked_requirement_count=len(requirements),
            checked_task_count=len(tasks),
            input_manifest_sha256=manifest_hash,
            evaluator_id="deterministic-preparation-readiness",
            evaluator_version="1",
            actor_id=context.actor_id,
            membership_id=context.membership_id,
            command_id=command.command_id,
            correlation_id=command.correlation_id,
        )
        session.add(readiness)
        package.aggregate_revision = revision
        package.state = "BLOCKED" if state == "BLOCKED" else "READY"
        return HandlerOutcome(
            result_code="PREPARATION_READINESS_EVALUATED",
            aggregate_refs=(
                {
                    "aggregate_type": "PreparationPackage",
                    "aggregate_id": str(package.id),
                    "aggregate_revision": revision,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="PreparationPackage",
                    aggregate_id=package.id,
                    aggregate_revision=revision,
                    event_type="PreparationReadinessEvaluated",
                    payload={
                        "package_id": str(package.id),
                        "readiness_id": str(readiness.id),
                        "state": state,
                        "blocker_codes": sorted(blocker_codes),
                        "warning_codes": sorted(warning_codes),
                    },
                ),
            ),
        )

    def _generate(
        self,
        *,
        session: Session,
        command: GenerateTechnicalDocumentCommand,
        context: CommandContext,
    ) -> HandlerOutcome:
        package = session.scalar(
            sa.select(PreparationPackageRecord)
            .where(
                PreparationPackageRecord.tenant_id == context.tenant_id,
                PreparationPackageRecord.id == command.package_id,
            )
            .with_for_update()
        )
        if package is None:
            raise CommandExecutionError("NOT_FOUND_OR_FORBIDDEN")
        self._ensure_assignment(session=session, package=package, context=context)
        if package.aggregate_revision != command.expected_revision:
            raise CommandExecutionError("VERSION_CONFLICT")
        readiness = session.scalar(
            sa.select(PreparationReadinessRecord).where(
                PreparationReadinessRecord.tenant_id == context.tenant_id,
                PreparationReadinessRecord.package_id == package.id,
                PreparationReadinessRecord.revision == command.readiness_revision,
            )
        )
        if readiness is None:
            raise CommandExecutionError("READINESS_NOT_FOUND")
        if readiness.state == "BLOCKED":
            raise CommandExecutionError("PREPARATION_BLOCKED")
        version = (
            session.scalar(
                sa.select(
                    sa.func.coalesce(sa.func.max(GeneratedTechnicalDocumentRecord.version), 0)
                ).where(
                    GeneratedTechnicalDocumentRecord.tenant_id == context.tenant_id,
                    GeneratedTechnicalDocumentRecord.package_id == package.id,
                )
            )
            + 1
        )
        lines = [
            "# Réponse technique — préparation contrôlée",
            f"Affaire: {package.case_id}",
            f"Version DCE: {package.dce_version_id}",
            f"Readiness: {readiness.state}",
            f"Version du document: {version}",
            "",
            "## Contrôle de complétude",
            "Blockers: " + (", ".join(readiness.blocker_codes_json) or "aucun"),
            "Warnings: " + (", ".join(readiness.warning_codes_json) or "aucun"),
            "",
            "Ce document est un brouillon technique versionné, réservé au contrôle opérationnel.",
        ]
        content = "\n".join(lines).encode("utf-8")
        if _contains_forbidden(content.decode("utf-8")):
            raise CommandExecutionError("FINANCIAL_DATA_FORBIDDEN")
        storage_key = (
            f"generated-documents/{context.tenant_id}/{package.id}/{command.document_id}.md"
        )
        content_sha256 = self._storage.write(storage_key=storage_key, content=content)
        document = GeneratedTechnicalDocumentRecord(
            id=command.document_id,
            tenant_id=context.tenant_id,
            package_id=package.id,
            readiness_id=readiness.id,
            version=version,
            document_kind=command.document_kind,
            state="GENERATED",
            content_sha256=content_sha256,
            storage_key=storage_key,
            actor_id=context.actor_id,
            membership_id=context.membership_id,
            command_id=command.command_id,
            correlation_id=command.correlation_id,
        )
        session.add(document)
        package.aggregate_revision += 1
        package.state = "GENERATED"
        return HandlerOutcome(
            result_code="TECHNICAL_DOCUMENT_GENERATED",
            aggregate_refs=(
                {
                    "aggregate_type": "GeneratedTechnicalDocument",
                    "aggregate_id": str(document.id),
                    "aggregate_revision": document.version,
                },
            ),
            events=(
                PendingDomainEvent(
                    aggregate_type="GeneratedTechnicalDocument",
                    aggregate_id=document.id,
                    aggregate_revision=document.version,
                    event_type="TechnicalDocumentGenerated",
                    payload={
                        "document_id": str(document.id),
                        "package_id": str(package.id),
                        "version": version,
                        "document_kind": document.document_kind,
                        "state": document.state,
                    },
                ),
            ),
        )


def preparation_handlers(*, storage: GeneratedDocumentStorage) -> dict[str, PreparationHandler]:
    handler = PreparationHandler(storage=storage)
    return {command_type: handler for command_type in _PREPARATION_COMMANDS}
