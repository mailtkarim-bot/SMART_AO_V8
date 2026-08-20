from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.interfaces.http.routes.consultations import ConsultationSecurityRuntime
from app.interfaces.http.routes.patron_assignment_cockpit import (
    build_patron_assignment_cockpit_router,
)
from app.platform.security.authenticated_context import UnauthenticatedError
from app.platform.security.context import ActorContext, ActorKind, MembershipState
from fastapi import FastAPI
from fastapi.testclient import TestClient

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)


@dataclass
class _Resolver:
    error: Exception | None = None

    def resolve(self, *, access_token: str) -> ActorContext:
        assert access_token == "test-token"
        if self.error is not None:
            raise self.error
        return ActorContext(
            actor_id=uuid4(), identity_id=uuid4(), tenant_id=uuid4(), membership_id=uuid4(),
            actor_kind=ActorKind.PATRON_ADMIN, membership_state=MembershipState.ACTIVE,
            capabilities=frozenset(), assigned_case_ids=frozenset(), session_id=uuid4(),
            authenticated_at=NOW, mfa_verified_at=None, correlation_id=uuid4(),
        )


def _runtime(*, resolver_error=None):
    return ConsultationSecurityRuntime(
        context_resolver=_Resolver(error=resolver_error), policy=SimpleNamespace()
    )


def _client(*, service=None, resolver_error=None):
    app = FastAPI()
    app.include_router(
        build_patron_assignment_cockpit_router(
            service=service or _CockpitService(),
            security_runtime=_runtime(resolver_error=resolver_error),
        )
    )
    return TestClient(app, raise_server_exceptions=False)


@dataclass
class _Assignment:
    assignment_id: object
    case_id: object
    case_title: str
    case_lifecycle: str
    state: str
    aggregate_revision: int
    starts_at: datetime
    ends_at: datetime | None
    ended_at: datetime | None
    scope_actions: list[str]
    scope_classifications: list[str]


@dataclass
class _JournalItem:
    record_id: object
    recorded_at: datetime
    event_type: str
    previous_revision: int | None
    resulting_revision: int
    previous_state: str | None
    resulting_state: str
    reason_code: str | None
    previous_scope_actions: list[str] | None
    previous_scope_classifications: list[str] | None
    resulting_scope_actions: list[str]
    resulting_scope_classifications: list[str]


@dataclass
class _Interaction:
    record_id: object
    kind: str
    recorded_at: datetime
    assignment_revision: int | None
    operational_state: str
    clarification_kind: str | None = None
    priority: str | None = None
    reason_kind: str | None = None
    unavailable_from: datetime | None = None
    unavailable_until: datetime | None = None
    known_deadline_impact: bool | None = None


class _CockpitService:
    def __init__(self, *, list_error=None, journal_error=None, interactions_error=None):
        self.list_error = list_error
        self.journal_error = journal_error
        self.interactions_error = interactions_error
        self.calls = []

    def _assignment(self, assignment_id=None):
        return _Assignment(
            assignment_id or uuid4(), uuid4(), "Réhabilitation école", "ACTIVE", "ACTIVE", 4,
            NOW, None, None, ["case.dce.read", "assignment.history.read"],
            ["INTERNAL_OPERATIONAL"],
        )

    def list(self, **kwargs):
        self.calls.append(("list", kwargs))
        if self.list_error is not None:
            raise self.list_error
        return [self._assignment()]

    def get_journal(self, **kwargs):
        self.calls.append(("journal", kwargs))
        if self.journal_error is not None:
            raise self.journal_error
        assignment = self._assignment(kwargs["assignment_id"])
        item = _JournalItem(
            uuid4(), NOW, "ASSIGNMENT_CREATED", None, 1, None, "ACTIVE", None,
            None, None, assignment.scope_actions, assignment.scope_classifications,
        )
        return SimpleNamespace(assignment=assignment, items=[item])

    def get_interactions(self, **kwargs):
        self.calls.append(("interactions", kwargs))
        if self.interactions_error is not None:
            raise self.interactions_error
        return SimpleNamespace(
            assignment_id=kwargs["assignment_id"], case_id=uuid4(), case_lifecycle="ACTIVE",
            items=[_Interaction(uuid4(), "CLARIFICATION_REQUEST", NOW, 4, "OPEN",
                                clarification_kind="DEADLINE", priority="HIGH")],
        )


def _headers():
    return {"Authorization": "Bearer test-token"}


@pytest.mark.parametrize("authorization", [None, "Basic test-token", "Bearer"])
def test_assignment_cockpit_rejects_missing_or_malformed_bearer(authorization):
    client = _client()
    headers = {} if authorization is None else {"Authorization": authorization}
    response = client.get("/api/v1/patron/assignments", headers=headers)
    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_assignment_cockpit_maps_invalid_context_to_401():
    response = _client(resolver_error=UnauthenticatedError()).get(
        "/api/v1/patron/assignments", headers=_headers()
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "UNAUTHENTICATED"}


def test_list_assignments_returns_closed_projection_and_forwards_filters():
    service = _CockpitService()
    case_id = uuid4()
    response = _client(service=service).get(
        f"/api/v1/patron/assignments?case_id={case_id}&state=SUSPENDED&limit=20",
        headers=_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["case_title"] == "Réhabilitation école"
    assert body["items"][0]["scope_classifications"] == ["INTERNAL_OPERATIONAL"]
    assert "gross_margin_minor" not in body
    _, kwargs = service.calls[0]
    assert kwargs["case_id"] == case_id
    assert kwargs["state"] == "SUSPENDED"
    assert kwargs["limit"] == 20


def test_list_assignments_maps_permission_error_to_403():
    response = _client(service=_CockpitService(list_error=PermissionError("FORBIDDEN"))).get(
        "/api/v1/patron/assignments", headers=_headers()
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "FORBIDDEN"}


def test_journal_returns_assignment_and_append_only_items():
    assignment_id = uuid4()
    response = _client().get(
        f"/api/v1/patron/assignments/{assignment_id}/journal?limit=10", headers=_headers()
    )
    assert response.status_code == 200
    body = response.json()
    assert body["assignment"]["assignment_id"] == str(assignment_id)
    assert body["items"][0]["event_type"] == "ASSIGNMENT_CREATED"
    assert body["items"][0]["resulting_revision"] == 1


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [(PermissionError("NOT_FOUND_OR_FORBIDDEN"), 404, "NOT_FOUND_OR_FORBIDDEN"),
     (PermissionError("FORBIDDEN"), 403, "FORBIDDEN")],
)
def test_journal_maps_neutral_not_found_and_forbidden(error, status_code, detail):
    response = _client(service=_CockpitService(journal_error=error)).get(
        f"/api/v1/patron/assignments/{uuid4()}/journal", headers=_headers()
    )
    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_interactions_returns_kind_and_operational_state():
    service = _CockpitService()
    assignment_id = uuid4()
    response = _client(service=service).get(
        f"/api/v1/patron/assignments/{assignment_id}/interactions"
        "?kind=CLARIFICATION_REQUEST&limit=5",
        headers=_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["assignment_id"] == str(assignment_id)
    assert body["items"][0]["kind"] == "CLARIFICATION_REQUEST"
    assert body["items"][0]["operational_state"] == "OPEN"
    _, kwargs = service.calls[0]
    assert kwargs["kind"] == "CLARIFICATION_REQUEST"
    assert kwargs["limit"] == 5


@pytest.mark.parametrize(
    ("path", "error", "detail"),
    [("journal", PermissionError("NOT_FOUND_OR_FORBIDDEN"), "NOT_FOUND_OR_FORBIDDEN"),
     ("interactions", PermissionError("FORBIDDEN"), "FORBIDDEN")],
)
def test_interactions_and_journal_map_errors(path, error, detail):
    service = _CockpitService(journal_error=error, interactions_error=error)
    response = _client(service=service).get(
        f"/api/v1/patron/assignments/{uuid4()}/{path}", headers=_headers()
    )
    assert response.status_code == (404 if detail == "NOT_FOUND_OR_FORBIDDEN" else 403)
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize(
    "query", ["limit=0", "limit=201", "state=UNKNOWN", "kind=UNKNOWN"]
)
def test_assignment_cockpit_rejects_invalid_query_bounds_and_enums(query):
    path = "/api/v1/patron/assignments" if "state" in query or "limit" in query else (
        f"/api/v1/patron/assignments/{uuid4()}/interactions"
    )
    response = _client().get(f"{path}?{query}", headers=_headers())
    assert response.status_code == 422
