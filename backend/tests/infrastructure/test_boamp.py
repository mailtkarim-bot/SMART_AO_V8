from __future__ import annotations

import pytest
from app.modules.market_watch.infrastructure.boamp import (
    BoampReadOnlySearch,
    BoampRegistryUnavailable,
)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def get(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return self.response


def test_boamp_search_returns_only_allowlisted_public_facts() -> None:
    client = FakeClient(
        FakeResponse(
            200,
            {
                "total_count": 1,
                "results": [
                    {
                        "idweb": "26-10001",
                        "objet": "Travaux de rénovation",
                        "dateparution": "2026-08-22",
                        "datelimitereponse": "2026-09-01T12:00:00+00:00",
                        "code_departement": ["75"],
                        "type_marche": ["TRAVAUX"],
                        "etat": "INITIAL",
                        "donnees": {"montant": "ne doit pas traverser"},
                    }
                ],
            },
        )
    )
    search = BoampReadOnlySearch(client=client)

    notices = search.search(text="  rénovation   école ", limit=10, offset=20)

    assert len(notices) == 1
    notice = notices[0]
    assert notice.notice_id == "26-10001"
    assert notice.title == "Travaux de rénovation"
    assert notice.publication_date is not None
    assert notice.response_deadline is not None
    assert notice.department_codes == ("75",)
    assert notice.market_types == ("TRAVAUX",)
    assert notice.status == "INITIAL"
    assert "donnees" not in notice.__dict__ if hasattr(notice, "__dict__") else True
    request = client.calls[0]
    assert request["url"].startswith("https://www.boamp.fr/")
    params = request["params"]
    assert params["select"] == (
        "idweb,objet,dateparution,datelimitereponse,code_departement,type_marche,etat"
    )
    assert "rénovation" in params["where"]
    assert "école" in params["where"]
    assert params["limit"] == "10"
    assert params["offset"] == "20"


@pytest.mark.parametrize("limit", [0, 101])
def test_boamp_search_bounds_pagination(limit: int) -> None:
    client = FakeClient(FakeResponse(200, {"results": []}))
    search = BoampReadOnlySearch(client=client)

    with pytest.raises(ValueError, match="limit"):
        search.search(text="travaux", limit=limit)
    assert client.calls == []


@pytest.mark.parametrize("status_code", [400, 401, 429, 500, 503])
def test_boamp_search_fails_closed_on_http_errors(status_code: int) -> None:
    search = BoampReadOnlySearch(client=FakeClient(FakeResponse(status_code)))

    with pytest.raises(BoampRegistryUnavailable):
        search.search(text="travaux")


@pytest.mark.parametrize("text", ["", " \n ", "x" * 201])
def test_boamp_search_rejects_unbounded_or_empty_text(text: str) -> None:
    search = BoampReadOnlySearch(client=FakeClient(FakeResponse(200)))

    with pytest.raises(ValueError, match="search text"):
        search.search(text=text)


def test_boamp_search_rejects_invalid_response_and_non_https_endpoint() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        BoampReadOnlySearch(base_url="http://boamp.test", client=FakeClient(FakeResponse(200)))

    search = BoampReadOnlySearch(client=FakeClient(FakeResponse(200, {"results": [{}]})))
    with pytest.raises(BoampRegistryUnavailable):
        search.search(text="travaux")
