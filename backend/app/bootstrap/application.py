"""FastAPI composition root for SMART_AO V8.

Business rules never live here. This module only assembles the application and
will register HTTP routes from module public contracts as slices are implemented.
"""

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(
        title="SMART_AO V8",
        version="0.1.0",
        description="SaaS BTP d'analyse DCE et de décision d'appel d'offres.",
    )

    @app.get("/healthz", tags=["system"])
    def healthcheck() -> dict[str, str]:
        return {"status": "ok", "service": "smart-ao-v8"}

    return app


app = create_app()
