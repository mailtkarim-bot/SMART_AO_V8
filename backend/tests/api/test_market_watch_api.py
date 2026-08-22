from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import UUID

from app.interfaces.http.routes import market_watch as market_watch_route
from app.interfaces.http.routes.market_watch import build_market_watch_router
from app.modules.market_watch.application.ports import BoampNotice
from app.modules.market_watch.application.service import PublicNoticeSearchService
from app.modules.market_watch.infrastructure.boamp import BoampRegistryUnavailable
from fastapi import FastAPI
from fastapi.testclient import TestClient

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


class FakeSearchPort:
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.failure = failure
        self.calls: list[dict[str, object]] = []

    def search(self, *, text: str, limit: int, offset: int):
        self.calls.append({"text": text, "limit": limit, "offset": offset})
        if self.failure is not None:
            raise self.failure
        return (
            BoampNotice(
                notice_id="BOAMP-1",
                title="Travaux de rénovation",
                publication_date=date(2026, 8, 22),
                response_deadline=datetime(2026, 9, 12, 12, tzinfo=UTC),
                department_codes=("75",),
                market_types=("TRAVAUX",),
                status="ACTIVE",
            ),
        )


class FakePolicy:
    def __init__(self, *, allowed: bool = True) -> None:
        self.allowed = allowed
        self.requests = []

    def authorize(self, *, context, request):
        self.requests.append(request)
        return SimpleNamespace(
            allowed=self.allowed,
            http_status_code=200 if self.allowed else 403,
        )


def _app(*, port: FakeSearchPort, policy: FakePolicy) -> FastAPI:
    app = FastAPI()
    app.include_router(
        build_market_watch_router(
            service=PublicNoticeSearchService(search_port=port),
            security_runtime=SimpleNamespace(context_resolver=object(), policy=policy),
        )
    )
    return app


def test_boamp_search_is_authenticated_and_source_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        market_watch_route,
        "_resolve_context",
        lambda *, authorization, context_resolver: SimpleNamespace(tenant_id=TENANT_ID),
    )
    port = FakeSearchPort()
    policy = FakePolicy()
    response = TestClient(_app(port=port, policy=policy)).get(
        "/api/v1/market-watch/boamp/search",
        params={"q": "travaux", "limit": 7, "offset": 3},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"] == "PUBLIC_TENDER"
    assert payload["query"] == "travaux"
    assert payload["limit"] == 7
    assert payload["offset"] == 3
    assert payload["results"][0] == {
        "notice_id": "BOAMP-1",
        "title": "Travaux de rénovation",
        "publication_date": "2026-08-22",
        "response_deadline": "2026-09-12T12:00:00Z",
        "department_codes": ["75"],
        "market_types": ["TRAVAUX"],
        "status": "ACTIVE",
    }
    assert "donnees" not in payload
    assert "gestion" not in payload
    assert "financial" not in payload
    assert port.calls == [{"text": "travaux", "limit": 7, "offset": 3}]
    assert policy.requests[0].action == "market.watch.read"
    assert policy.requests[0].resource.classification.value == "PUBLIC_TENDER"
    assert policy.requests[0].resource.tenant_id == TENANT_ID


def test_boamp_search_maps_source_failure_to_503(monkeypatch) -> None:
    monkeypatch.setattr(
        market_watch_route,
        "_resolve_context",
        lambda *, authorization, context_resolver: SimpleNamespace(tenant_id=TENANT_ID),
    )
    response = TestClient(
        _app(
            port=FakeSearchPort(failure=BoampRegistryUnavailable("private details")),
            policy=FakePolicy(),
        )
    ).get("/api/v1/market-watch/boamp/search", params={"q": "travaux"})

    assert response.status_code == 503
    assert response.json() == {"detail": "PUBLIC_NOTICE_SOURCE_UNAVAILABLE"}
    assert "private details" not in response.text


def test_boamp_search_denies_without_capability(monkeypatch) -> None:
    monkeypatch.setattr(
        market_watch_route,
        "_resolve_context",
        lambda *, authorization, context_resolver: SimpleNamespace(tenant_id=TENANT_ID),
    )
    port = FakeSearchPort()
    response = TestClient(_app(port=port, policy=FakePolicy(allowed=False))).get(
        "/api/v1/market-watch/boamp/search", params={"q": "travaux"}
    )

    assert response.status_code == 403
    assert port.calls == []


def test_boamp_search_bounds_pagination(monkeypatch) -> None:
    monkeypatch.setattr(
        market_watch_route,
        "_resolve_context",
        lambda *, authorization, context_resolver: SimpleNamespace(tenant_id=TENANT_ID),
    )
    response = TestClient(_app(port=FakeSearchPort(), policy=FakePolicy())).get(
        "/api/v1/market-watch/boamp/search", params={"q": "travaux", "limit": 51}
    )

    assert response.status_code == 422
