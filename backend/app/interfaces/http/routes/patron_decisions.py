from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status

from app.interfaces.http.dependencies.auth import resolve_bearer_context as _resolve_context
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.modules.decision.application.patron_dossier import PatronDecisionDossierService
from app.modules.decision.public.patron_contracts import PatronDecisionDossierResponse


def build_patron_decision_router(
    *, service: PatronDecisionDossierService, security_runtime: ConsultationSecurityRuntime
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/patron", tags=["patron-decisions"])

    @router.get("/cases/{case_id}/decision-dossier", response_model=PatronDecisionDossierResponse)
    def read_dossier(case_id: UUID, authorization: str | None = Header(default=None)):
        actor = _resolve_context(
            authorization=authorization,
            context_resolver=security_runtime.context_resolver,
        )
        try:
            dossier = service.read(actor=actor, case_id=case_id, now=datetime.now(tz=UTC))
        except PermissionError as error:
            if str(error) == "NOT_FOUND_OR_FORBIDDEN":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="NOT_FOUND_OR_FORBIDDEN"
                ) from error
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN"
            ) from error
        payload = asdict(dossier)
        payload["conditions"] = list(payload["conditions"])
        payload["sources"] = list(payload["sources"])
        return PatronDecisionDossierResponse(**payload)

    return router
