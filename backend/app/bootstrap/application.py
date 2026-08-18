"""FastAPI composition root for SMART_AO V8.

Business rules remain in module handlers. This composition root assembles only
technical adapters and public HTTP routes; it never performs a business
transition or directly queries an ORM record from a route.
"""

from __future__ import annotations

import os
import socket
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, sessionmaker

from app.interfaces.http.routes.assignment_history import build_assignment_history_router
from app.interfaces.http.routes.assignment_interactions import (
    build_assignment_interaction_router,
)
from app.interfaces.http.routes.authentication import (
    AuthenticationHttpRuntime,
    build_authentication_router,
)
from app.interfaces.http.routes.case_assigned import build_assigned_case_router
from app.interfaces.http.routes.case_dce_reading import build_case_dce_reading_router
from app.interfaces.http.routes.collaborator_capabilities import (
    build_collaborator_capability_router,
)
from app.interfaces.http.routes.collaborator_info_blockers import (
    build_collaborator_info_blocker_router,
)
from app.interfaces.http.routes.collaborator_work_tasks import (
    build_collaborator_work_task_router,
)
from app.interfaces.http.routes.consultations import (
    ConsultationSecurityRuntime,
    build_consultation_router,
)
from app.interfaces.http.routes.dce_requirement_confirmations import (
    build_dce_requirement_confirmation_router,
)
from app.interfaces.http.routes.dce_staging import build_dce_staging_router
from app.interfaces.http.routes.dce_versions import build_dce_version_router
from app.interfaces.http.routes.observability import build_observability_router
from app.interfaces.http.routes.patron_actions import build_patron_action_router
from app.interfaces.http.routes.patron_assignment_cockpit import (
    build_patron_assignment_cockpit_router,
)
from app.interfaces.http.routes.patron_assignment_management import (
    build_patron_assignment_management_router,
)
from app.interfaces.http.routes.patron_enterprise_capabilities import (
    build_patron_enterprise_capability_router,
)
from app.interfaces.http.routes.patron_enterprise_library import (
    build_patron_enterprise_library_router,
)
from app.interfaces.http.routes.patron_financial_reports import (
    build_patron_financial_report_router,
)
from app.interfaces.http.routes.patron_submission import build_patron_submission_router
from app.interfaces.http.routes.preparation import (
    build_preparation_review_router,
    build_preparation_router,
)
from app.interfaces.http.routes.preparation_transmission import (
    build_preparation_transmission_router,
)
from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.dce.application.handlers import (
    ClaimDceStagedObjectUploadHandler,
    CreateConsultationHandler,
    ExpireDceStagedObjectHandler,
    PrepareDceStagingHandler,
    RecordCaseDceImpactRunHandler,
    RecordDceDocumentClassificationRunHandler,
    RecordDceDocumentExtractionHandler,
    RecordDceRcAnalysisHandler,
    RecordDceRequirementConfirmationHandler,
    RecordDceRequirementMaterializationRunHandler,
    RecordDceStagedObjectQuarantineHandler,
    RecordDceStagedObjectScanHandler,
    RegisterDceVersionHandler,
    RejectDceStagedObjectUploadHandler,
)
from app.modules.dce.application.impact import CaseDceImpactService
from app.modules.dce.application.queries import ConsultationProjection
from app.modules.dce.application.requirement_confirmation import (
    DceRequirementConfirmationService,
)
from app.modules.dce.application.upload import DceUploadService
from app.modules.dce.infrastructure.case_assigned_reader import SqlAlchemyAssignedCaseReader
from app.modules.dce.infrastructure.case_dce_reading_reader import (
    SqlAlchemyCaseDceReadingReader,
)
from app.modules.dce.infrastructure.consultation_projection_reader import (
    SqlAlchemyConsultationProjectionReader,
)
from app.modules.dce.infrastructure.models.consultation import ConsultationRecord
from app.modules.dce.infrastructure.models.dce_staging import DceStagedObjectRecord
from app.modules.dce.infrastructure.models.dce_version import DceVersionRecord
from app.modules.dce.infrastructure.quarantine import (
    ClamdTcpMalwareScanAdapter,
    LocalQuarantineStorageAdapter,
    PythonMagicContentInspectionAdapter,
)
from app.modules.enterprise.application.enterprise_capability import (
    EnterpriseCapabilityService,
    enterprise_capability_handlers,
)
from app.modules.enterprise.application.enterprise_library import (
    EnterpriseLibraryService,
    enterprise_library_handlers,
)
from app.modules.enterprise.application.enterprise_upload import (
    EnterprisePrivateUploadService,
    enterprise_upload_handlers,
)
from app.modules.membership.application.assignment import (
    AssignmentInteractionService,
    assignment_handlers,
)
from app.modules.membership.application.assignment_history import AssignmentHistoryService
from app.modules.membership.application.collab_capability import (
    CollaboratorCapabilityAssessmentService,
    collaborator_capability_handlers,
)
from app.modules.membership.application.collab_info_blockers import (
    CollaboratorInfoBlockerService,
    collaborator_info_blocker_handlers,
)
from app.modules.membership.application.collab_work_task import (
    CollaboratorWorkTaskService,
    collaborator_work_task_handlers,
)
from app.modules.membership.application.financial_report import PatronFinancialReportService
from app.modules.membership.application.financial_report_draft import (
    CreateFinancialReportDraftHandler,
    PatronFinancialReportDraftCreationService,
)
from app.modules.membership.application.financial_report_lines import (
    PatronFinancialReportLineService,
    financial_report_line_handlers,
)
from app.modules.membership.application.financial_report_publication import (
    PatronFinancialReportPublicationService,
    PublishFinancialReportHandler,
)
from app.modules.membership.application.patron_assignment import (
    PatronAssignmentManagementService,
    patron_assignment_handlers,
)
from app.modules.membership.application.patron_assignment_cockpit import (
    PatronAssignmentCockpitService,
)
from app.modules.patron_action.application.service import (
    PatronActionService,
    PatronActionWriter,
    patron_action_handlers,
)
from app.modules.preparation.application.review import (
    PreparationReviewService,
    preparation_review_handlers,
)
from app.modules.preparation.application.service import PreparationService, preparation_handlers
from app.modules.preparation.application.transmission import (
    PreparationTransmissionService,
    preparation_transmission_handlers,
)
from app.modules.preparation.infrastructure.dce_preparation_reader import (
    SqlAlchemyPreparationDceReader,
)
from app.modules.preparation.infrastructure.document_storage import (
    LocalGeneratedDocumentStorage,
)
from app.modules.submission.application.service import SubmissionPackageService, submission_handlers
from app.platform.events.dispatcher import CommandDispatcher
from app.platform.observability.http import RequestObservabilityMiddleware
from app.platform.security.audit import AuditedAuthorizationPolicy, SecurityAuditWriter
from app.platform.security.authorization import AuthorizationPolicy


@dataclass(frozen=True, slots=True)
class DceStagedObjectUploadTarget:
    """Internal facts required to authorize and stream one staged DCE object."""

    tenant_id: UUID
    consultation_id: UUID
    storage_key: str
    expected_byte_size: int
    state: str


@dataclass(frozen=True, slots=True)
class AppRuntime:
    """Technical dependencies shared by HTTP routes in the current slice."""

    session_factory: sessionmaker[Session]
    dispatcher: CommandDispatcher
    dce_upload_service: DceUploadService
    preparation_storage: LocalGeneratedDocumentStorage

    @classmethod
    def create(
        cls,
        *,
        session_factory: sessionmaker[Session],
        dce_upload_service_factory: Callable[[CommandDispatcher], DceUploadService] | None = None,
    ) -> AppRuntime:
        preparation_storage = LocalGeneratedDocumentStorage(
            root=Path(os.getenv("SMART_AO_DCE_QUARANTINE_ROOT", "/var/lib/smart_ao/dce-quarantine"))
        )
        dispatcher = CommandDispatcher(
            session_factory=session_factory,
            handlers={
                **enterprise_upload_handlers(),
                "ClaimDceStagedObjectUpload": ClaimDceStagedObjectUploadHandler(),
                "CreateConsultation": CreateConsultationHandler(),
                "ExpireDceStagedObject": ExpireDceStagedObjectHandler(),
                "PrepareDceStaging": PrepareDceStagingHandler(),
                "RecordDceStagedObjectQuarantine": RecordDceStagedObjectQuarantineHandler(),
                "RecordDceStagedObjectScan": RecordDceStagedObjectScanHandler(),
                "RecordDceDocumentClassificationRun": RecordDceDocumentClassificationRunHandler(),
                "RecordDceDocumentExtraction": RecordDceDocumentExtractionHandler(),
                "RecordDceRcAnalysis": RecordDceRcAnalysisHandler(),
                "RecordCaseDceImpactRun": RecordCaseDceImpactRunHandler(),
                "RecordDceRequirementMaterializationRun": (
                    RecordDceRequirementMaterializationRunHandler()
                ),
                "RecordDceRequirementConfirmation": RecordDceRequirementConfirmationHandler(),
                "CreateFinancialReportDraft": CreateFinancialReportDraftHandler(),
                "PublishFinancialReport": PublishFinancialReportHandler(),
                **financial_report_line_handlers(),
                **enterprise_capability_handlers(),
                **enterprise_library_handlers(),
                "RejectDceStagedObjectUpload": RejectDceStagedObjectUploadHandler(),
                "RegisterDceVersion": RegisterDceVersionHandler(),
                **assignment_handlers(),
                **collaborator_work_task_handlers(),
                **collaborator_capability_handlers(),
                **collaborator_info_blocker_handlers(),
                **patron_assignment_handlers(),
                **preparation_handlers(
                    storage=preparation_storage,
                    dce_reader=SqlAlchemyPreparationDceReader(),
                ),
                **preparation_transmission_handlers(action_writer=PatronActionWriter()),
                **patron_action_handlers(),
                **preparation_review_handlers(storage=preparation_storage),
                **submission_handlers(),
            },
        )
        upload_service = (
            dce_upload_service_factory(dispatcher)
            if dce_upload_service_factory is not None
            else _default_dce_upload_service(dispatcher=dispatcher)
        )
        return cls(
            session_factory=session_factory,
            dispatcher=dispatcher,
            dce_upload_service=upload_service,
            preparation_storage=preparation_storage,
        )

    def get_dce_staged_object_upload_target(
        self,
        *,
        storage_object_id: UUID,
    ) -> DceStagedObjectUploadTarget | None:
        """Return the private upload facts needed only after bearer resolution."""

        with self.session_factory() as session:
            record = session.scalar(
                sa.select(DceStagedObjectRecord).where(
                    DceStagedObjectRecord.id == storage_object_id
                )
            )
            if record is None:
                return None
            return DceStagedObjectUploadTarget(
                tenant_id=record.tenant_id,
                consultation_id=record.consultation_id,
                storage_key=record.storage_key,
                expected_byte_size=record.expected_byte_size,
                state=record.state,
            )

    def get_case_tenant_id(self, *, case_id: UUID) -> UUID | None:
        """Return only the Case owner tenant required before SEC-01 authorization."""

        with self.session_factory() as session:
            return session.scalar(sa.select(CaseRecord.tenant_id).where(CaseRecord.id == case_id))

    def get_case_dce_reading(self, *, tenant_id: UUID, case_id: UUID):
        """Return the closed B projection scoped to one trusted tenant and Case."""

        with self.session_factory() as session:
            return SqlAlchemyCaseDceReadingReader(session).get(
                tenant_id=tenant_id,
                case_id=case_id,
            )

    def get_assigned_case_candidates(self, *, tenant_id: UUID):
        """Return closed same-tenant candidates for the audited ReBAC route."""

        with self.session_factory() as session:
            return SqlAlchemyAssignedCaseReader(session).list(tenant_id=tenant_id)

    def run_case_dce_impact(
        self,
        *,
        tenant_id: UUID,
        case_id: UUID,
        predecessor_dce_version_id: UUID,
        successor_dce_version_id: UUID,
    ):
        """Run the internal SYSTEM impact preparation for one Case rectification."""

        return CaseDceImpactService(
            session_factory=self.session_factory,
            dispatcher=self.dispatcher,
        ).run(
            tenant_id=tenant_id,
            case_id=case_id,
            predecessor_dce_version_id=predecessor_dce_version_id,
            successor_dce_version_id=successor_dce_version_id,
        )

    def get_dce_version_tenant_id(self, *, dce_version_id: UUID) -> UUID | None:
        """Return only the owning tenant needed to authorize a DceVersion read."""

        with self.session_factory() as session:
            statement = sa.select(DceVersionRecord.tenant_id).where(
                DceVersionRecord.id == dce_version_id
            )
            return session.scalar(statement)

    def get_dce_version_metadata(
        self,
        *,
        tenant_id: UUID,
        dce_version_id: UUID,
    ) -> DceVersionRecord | None:
        """Return the tenant-filtered root whose approved fields form DCE-READ-01."""

        with self.session_factory() as session:
            statement = sa.select(DceVersionRecord).where(
                DceVersionRecord.tenant_id == tenant_id,
                DceVersionRecord.id == dce_version_id,
            )
            return session.scalar(statement)

    def get_consultation_tenant_id(self, *, consultation_id: UUID) -> UUID | None:
        """Return only the owner tenant needed to authorize a requested Consultation."""

        with self.session_factory() as session:
            statement = sa.select(ConsultationRecord.tenant_id).where(
                ConsultationRecord.id == consultation_id
            )
            return session.scalar(statement)

    def get_consultation_projection(
        self,
        *,
        tenant_id: UUID | str,
        consultation_id: UUID | str,
    ) -> ConsultationProjection | None:
        with self.session_factory() as session:
            return SqlAlchemyConsultationProjectionReader(session).get(
                tenant_id=tenant_id,
                consultation_id=consultation_id,
            )


_ALLOWED_DCE_MEDIA_TYPES = frozenset(
    {
        "application/pdf",
        "application/msword",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.oasis.opendocument.text",
        "application/vnd.oasis.opendocument.spreadsheet",
        "application/zip",
        "image/jpeg",
        "image/png",
        "image/tiff",
    }
)


def _default_dce_upload_service(*, dispatcher: CommandDispatcher) -> DceUploadService:
    storage = LocalQuarantineStorageAdapter(
        root=Path(os.getenv("SMART_AO_DCE_QUARANTINE_ROOT", "/var/lib/smart_ao/dce-quarantine"))
    )
    return DceUploadService(
        dispatcher=dispatcher,
        storage=storage,
        inspector=PythonMagicContentInspectionAdapter(storage=storage),
        scanner=ClamdTcpMalwareScanAdapter(
            storage=storage,
            host=os.getenv("SMART_AO_CLAMD_HOST", "clamav"),
            port=int(os.getenv("SMART_AO_CLAMD_PORT", "3310")),
            timeout_seconds=float(os.getenv("SMART_AO_CLAMD_TIMEOUT_SECONDS", "30")),
        ),
        allowed_media_types=_ALLOWED_DCE_MEDIA_TYPES,
    )


def _default_enterprise_private_upload_service(
    *, session_factory: sessionmaker[Session], dispatcher: CommandDispatcher, policy
) -> EnterprisePrivateUploadService:
    storage = LocalQuarantineStorageAdapter(
        root=Path(os.getenv("SMART_AO_DCE_QUARANTINE_ROOT", "/var/lib/smart_ao/dce-quarantine"))
    )
    return EnterprisePrivateUploadService(
        session_factory=session_factory,
        dispatcher=dispatcher,
        policy=policy,
        storage=storage,
        inspector=PythonMagicContentInspectionAdapter(storage=storage),
        scanner=ClamdTcpMalwareScanAdapter(
            storage=storage,
            host=os.getenv("SMART_AO_CLAMD_HOST", "clamav"),
            port=int(os.getenv("SMART_AO_CLAMD_PORT", "3310")),
            timeout_seconds=float(os.getenv("SMART_AO_CLAMD_TIMEOUT_SECONDS", "30")),
        ),
        allowed_media_types=_ALLOWED_DCE_MEDIA_TYPES,
    )


def create_app(
    *,
    runtime: AppRuntime | None = None,
    authentication_runtime: AuthenticationHttpRuntime | None = None,
) -> FastAPI:
    app = FastAPI(
        title="SMART_AO V8",
        version="0.1.0",
        description="SaaS BTP d'analyse DCE et de décision d'appel d'offres.",
    )
    app.add_middleware(RequestObservabilityMiddleware)
    app.include_router(build_observability_router())

    @app.get("/healthz", tags=["system"])
    def healthcheck() -> dict[str, str]:
        return {"status": "ok", "service": "smart-ao-v8"}

    @app.get("/healthz/live", tags=["system"])
    def liveness() -> dict[str, object]:
        return {"status": "ok", "service": "smart-ao-v8", "checks": {"process": "ok"}}

    @app.get("/healthz/ready", tags=["system"])
    def readiness() -> JSONResponse:
        checks: dict[str, str] = {"database": "unknown", "clamav": "unknown"}
        if runtime is None:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "service": "smart-ao-v8", "checks": checks},
            )
        try:
            with runtime.session_factory() as session:
                session.execute(sa.text("SELECT 1"))
            checks["database"] = "ok"
        except sa.exc.SQLAlchemyError:
            checks["database"] = "failed"
        try:
            with socket.create_connection(
                (
                    os.getenv("SMART_AO_CLAMD_HOST", "clamav"),
                    int(os.getenv("SMART_AO_CLAMD_PORT", "3310")),
                ),
                timeout=float(os.getenv("SMART_AO_CLAMD_TIMEOUT_SECONDS", "3")),
            ):
                pass
            checks["clamav"] = "ok"
        except (OSError, ValueError):
            checks["clamav"] = "failed"
        ready = all(value == "ok" for value in checks.values())
        return JSONResponse(
            status_code=200 if ready else 503,
            content={
                "status": "ok" if ready else "not_ready",
                "service": "smart-ao-v8",
                "checks": checks,
            },
        )

    if authentication_runtime is not None:
        app.include_router(build_authentication_router(runtime=authentication_runtime))
    if runtime is not None and authentication_runtime is not None:
        security_policy = AuditedAuthorizationPolicy(
            policy=AuthorizationPolicy(),
            session_factory=runtime.session_factory,
            writer=SecurityAuditWriter(),
        )
        security_runtime = ConsultationSecurityRuntime(
            context_resolver=authentication_runtime.context_resolver,
            policy=security_policy,
        )
        requirement_confirmation_service = DceRequirementConfirmationService(
            session_factory=runtime.session_factory,
            dispatcher=runtime.dispatcher,
            policy=security_policy,
        )
        assignment_interaction_service = AssignmentInteractionService(
            session_factory=runtime.session_factory,
            dispatcher=runtime.dispatcher,
            policy=security_policy,
        )
        collaborator_work_task_service = CollaboratorWorkTaskService(
            session_factory=runtime.session_factory,
            dispatcher=runtime.dispatcher,
            policy=security_policy,
        )
        collaborator_info_blocker_service = CollaboratorInfoBlockerService(
            session_factory=runtime.session_factory,
            dispatcher=runtime.dispatcher,
            policy=security_policy,
        )
        collaborator_capability_service = CollaboratorCapabilityAssessmentService(
            session_factory=runtime.session_factory,
            dispatcher=runtime.dispatcher,
            policy=security_policy,
        )
        preparation_service = PreparationService(
            session_factory=runtime.session_factory,
            dispatcher=runtime.dispatcher,
            policy=security_policy,
            storage=runtime.preparation_storage,
        )
        preparation_review_service = PreparationReviewService(
            session_factory=runtime.session_factory,
            dispatcher=runtime.dispatcher,
            policy=security_policy,
            storage=runtime.preparation_storage,
        )
        preparation_transmission_service = PreparationTransmissionService(
            session_factory=runtime.session_factory,
            dispatcher=runtime.dispatcher,
            policy=security_policy,
        )
        patron_action_service = PatronActionService(
            session_factory=runtime.session_factory,
            dispatcher=runtime.dispatcher,
            policy=security_policy,
        )
        assignment_history_service = AssignmentHistoryService(
            session_factory=runtime.session_factory,
            policy=security_policy,
        )
        patron_assignment_management_service = PatronAssignmentManagementService(
            session_factory=runtime.session_factory,
            dispatcher=runtime.dispatcher,
            policy=security_policy,
        )
        patron_assignment_cockpit_service = PatronAssignmentCockpitService(
            session_factory=runtime.session_factory,
            policy=security_policy,
        )
        patron_financial_report_service = PatronFinancialReportService(
            session_factory=runtime.session_factory,
            policy=security_policy,
        )
        patron_financial_report_line_service = PatronFinancialReportLineService(
            session_factory=runtime.session_factory,
            dispatcher=runtime.dispatcher,
            policy=security_policy,
        )
        patron_financial_report_draft_creation_service = PatronFinancialReportDraftCreationService(
            session_factory=runtime.session_factory,
            dispatcher=runtime.dispatcher,
            policy=security_policy,
        )
        patron_financial_report_publication_service = PatronFinancialReportPublicationService(
            session_factory=runtime.session_factory,
            dispatcher=runtime.dispatcher,
            policy=security_policy,
        )
        enterprise_library_service = EnterpriseLibraryService(
            session_factory=runtime.session_factory,
            dispatcher=runtime.dispatcher,
            policy=security_policy,
        )
        enterprise_capability_service = EnterpriseCapabilityService(
            session_factory=runtime.session_factory,
            dispatcher=runtime.dispatcher,
            policy=security_policy,
        )
        enterprise_upload_service = _default_enterprise_private_upload_service(
            session_factory=runtime.session_factory,
            dispatcher=runtime.dispatcher,
            policy=security_policy,
        )
        submission_package_service = SubmissionPackageService(
            session_factory=runtime.session_factory,
            dispatcher=runtime.dispatcher,
            policy=security_policy,
        )
        app.include_router(
            build_case_dce_reading_router(
                runtime=runtime,
                security_runtime=security_runtime,
            )
        )
        app.include_router(
            build_assigned_case_router(
                runtime=runtime,
                security_runtime=security_runtime,
            )
        )
        app.include_router(
            build_consultation_router(
                runtime=runtime,
                security_runtime=security_runtime,
            )
        )
        app.include_router(
            build_dce_staging_router(
                runtime=runtime,
                security_runtime=security_runtime,
            )
        )
        app.include_router(
            build_dce_version_router(
                runtime=runtime,
                security_runtime=security_runtime,
            )
        )
        app.include_router(
            build_dce_requirement_confirmation_router(
                service=requirement_confirmation_service,
                security_runtime=security_runtime,
            )
        )
        app.include_router(
            build_assignment_interaction_router(
                service=assignment_interaction_service,
                security_runtime=security_runtime,
            )
        )
        app.include_router(
            build_collaborator_work_task_router(
                service=collaborator_work_task_service,
                security_runtime=security_runtime,
            )
        )
        app.include_router(
            build_collaborator_info_blocker_router(
                service=collaborator_info_blocker_service,
                security_runtime=security_runtime,
            )
        )
        app.include_router(
            build_collaborator_capability_router(
                service=collaborator_capability_service,
                security_runtime=security_runtime,
            )
        )
        app.include_router(
            build_preparation_router(
                service=preparation_service,
                security_runtime=security_runtime,
            )
        )
        app.include_router(
            build_preparation_review_router(
                service=preparation_review_service,
                security_runtime=security_runtime,
            )
        )
        app.include_router(
            build_preparation_transmission_router(
                service=preparation_transmission_service,
                security_runtime=security_runtime,
            )
        )
        app.include_router(
            build_patron_action_router(
                service=patron_action_service,
                security_runtime=security_runtime,
            )
        )
        app.include_router(
            build_assignment_history_router(
                service=assignment_history_service,
                security_runtime=security_runtime,
            )
        )
        app.include_router(
            build_patron_assignment_management_router(
                service=patron_assignment_management_service,
                security_runtime=security_runtime,
            )
        )
        app.include_router(
            build_patron_assignment_cockpit_router(
                service=patron_assignment_cockpit_service,
                security_runtime=security_runtime,
            )
        )
        app.include_router(
            build_patron_financial_report_router(
                service=patron_financial_report_service,
                line_service=patron_financial_report_line_service,
                draft_creation_service=patron_financial_report_draft_creation_service,
                publication_service=patron_financial_report_publication_service,
                security_runtime=security_runtime,
            )
        )
        app.include_router(
            build_patron_submission_router(
                service=submission_package_service,
                security_runtime=security_runtime,
            )
        )
        app.include_router(
            build_patron_enterprise_library_router(
                service=enterprise_library_service,
                upload_service=enterprise_upload_service,
                security_runtime=security_runtime,
            )
        )
        app.include_router(
            build_patron_enterprise_capability_router(
                service=enterprise_capability_service,
                security_runtime=security_runtime,
            )
        )
    return app


app = create_app()
