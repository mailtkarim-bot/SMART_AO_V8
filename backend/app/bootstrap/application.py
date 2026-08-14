"""FastAPI composition root for SMART_AO V8.

Business rules remain in module handlers. This composition root assembles only
technical adapters and public HTTP routes; it never performs a business
transition or directly queries an ORM record from a route.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import sqlalchemy as sa
from fastapi import FastAPI
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
from app.interfaces.http.routes.consultations import (
    ConsultationSecurityRuntime,
    build_consultation_router,
)
from app.interfaces.http.routes.dce_requirement_confirmations import (
    build_dce_requirement_confirmation_router,
)
from app.interfaces.http.routes.dce_staging import build_dce_staging_router
from app.interfaces.http.routes.dce_versions import build_dce_version_router
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
from app.modules.membership.application.assignment import (
    AssignmentInteractionService,
    assignment_handlers,
)
from app.modules.membership.application.assignment_history import AssignmentHistoryService
from app.modules.membership.application.patron_assignment import patron_assignment_handlers
from app.platform.events.dispatcher import CommandDispatcher
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

    @classmethod
    def create(
        cls,
        *,
        session_factory: sessionmaker[Session],
        dce_upload_service_factory: Callable[[CommandDispatcher], DceUploadService] | None = None,
    ) -> AppRuntime:
        dispatcher = CommandDispatcher(
            session_factory=session_factory,
            handlers={
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
                "RejectDceStagedObjectUpload": RejectDceStagedObjectUploadHandler(),
                "RegisterDceVersion": RegisterDceVersionHandler(),
                **assignment_handlers(),
                **patron_assignment_handlers(),
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

    @app.get("/healthz", tags=["system"])
    def healthcheck() -> dict[str, str]:
        return {"status": "ok", "service": "smart-ao-v8"}

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
        assignment_history_service = AssignmentHistoryService(
            session_factory=runtime.session_factory,
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
            build_assignment_history_router(
                service=assignment_history_service,
                security_runtime=security_runtime,
            )
        )
    return app


app = create_app()
