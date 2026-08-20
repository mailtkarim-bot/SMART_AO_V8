from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.platform.observability.http import HTTP_METRICS


def build_observability_router() -> APIRouter:
    router = APIRouter(tags=["system"])

    @router.get("/metrics", response_class=PlainTextResponse)
    def metrics() -> PlainTextResponse:
        return PlainTextResponse(
            HTTP_METRICS.render_prometheus(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    return router
