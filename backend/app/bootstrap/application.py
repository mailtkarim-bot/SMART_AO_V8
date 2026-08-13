"""FastAPI composition root for SMART_AO V8.

Business rules remain in module handlers. This composition root assembles only
technical adapters and public HTTP routes; it never performs a business
transition or directly queries an ORM record from a route.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from app.interfaces.http.routes.authentication import (
    AuthenticationHttpRuntime,
    build_authentication_router,
)
from app.interfaces.http.routes.consultations import build_consultation_router
from app.modules.dce.application.handlers import CreateConsultationHandler
from app.modules.dce.application.queries import ConsultationProjection
from app.modules.dce.infrastructure.consultation_projection_reader import (
    SqlAlchemyConsultationProjectionReader,
)
from app.platform.events.dispatcher import CommandContext, CommandDispatcher


@dataclass(frozen=True, slots=True)
class AppRuntime:
    """Technical dependencies shared by HTTP routes in the current slice."""

    session_factory: sessionmaker[Session]
    dispatcher: CommandDispatcher

    @classmethod
    def create(cls, *, session_factory: sessionmaker[Session]) -> AppRuntime:
        return cls(
            session_factory=session_factory,
            dispatcher=CommandDispatcher(
                session_factory=session_factory,
                handlers={"CreateConsultation": CreateConsultationHandler()},
            ),
        )

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


def create_app(
    *,
    runtime: AppRuntime | None = None,
    command_context_resolver: Callable[[], CommandContext] | None = None,
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
    if runtime is not None and command_context_resolver is not None:
        app.include_router(
            build_consultation_router(
                runtime=runtime,
                command_context_resolver=command_context_resolver,
            )
        )
    return app


app = create_app()
