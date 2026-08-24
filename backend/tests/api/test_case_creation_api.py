from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import app.interfaces.http.routes.case_creation as route_module
import pytest
from app.interfaces.http.routes.case_creation import build_case_creation_router
from app.platform.events.dispatcher import (
    CommandExecutionError,
    DispatchResult,
    IdempotencyKeyReusedError,
)
from app.platform.security.authorization import AuthorizationPolicy
from app.platform.security.capabilities import Capability, capabilities_for
from app.platform.security.context import ActorContext, ActorKind, MembershipState
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _actor() -> ActorContext:
    actor_id = uuid4()
    return ActorContext(
        actor_id=actor_id,
        identity_id=actor_id,
        tenant_id=uuid4(),
        membership_id=uuid4(),
        actor_kind=ActorKind.PATRON_ADMIN,
        membership_state=MembershipState.ACTIVE,
        capabilities=capabilities_for(ActorKind.PATRON_ADMIN),
        assigned_case_ids=frozenset(),
        session_id=uuid4(),
        authenticated_at=datetime.now(tz=UTC),
        mfa_verified_at=None,
        correlation_id=uuid4(),
    )


def _client(*, dispatcher, actor: ActorContext, monkeypatch) -> TestClient:
    security_runtime = SimpleNamespace(
        context_resolver=object(),
        policy=AuthorizationPolicy(),
    )
    monkeypatch.setattr(route_module, "_resolve_context", lambda **_kwargs: actor)
    app = FastAPI()
    app.include_router(
        build_case_creation_router(
            dispatcher=dispatcher,
            security_runtime=security_runtime,
        )
    )
    return TestClient(app)


def _payload() -> dict[str, object]:
    return {
        "command_id": "11111111-1111-1111-1111-111111111111",
        "idempotency_key": "22222222-2222-2222-2222-222222222222",
        "title": "Réhabilitation d’un groupe scolaire",
        "object_description": "Travaux de rénovation énergétique.",
        "scope_kind": "SINGLE_LOT",
        "lot_numbers": ["01"],
        "origin_kind": "MANUAL",
        "origin_rationale": "Saisie patronale.",
    }


def _dispatch_result(*, replayed: bool = False) -> DispatchResult:
    return DispatchResult(
        status="SUCCEEDED",
        command_id="11111111-1111-1111-1111-111111111111",
        idempotency_key="22222222-2222-2222-2222-222222222222",
        result_code="CASE_CREATED",
        aggregate_refs=(
            {
                "aggregate_type": "AFF",
                "aggregate_id": "33333333-3333-3333-3333-333333333333",
                "aggregate_revision": 0,
            },
        ),
        event_ids=("44444444-4444-4444-4444-444444444444",),
        replayed=replayed,
    )


def test_create_case_http_uses_server_actor_and_returns_case_reference(monkeypatch) -> None:
    actor = _actor()
    dispatcher = SimpleNamespace(dispatch=lambda **_kwargs: _dispatch_result())

    response = _client(dispatcher=dispatcher, actor=actor, monkeypatch=monkeypatch).post(
        "/api/v1/cases",
        json=_payload(),
    )

    assert response.status_code == 201
    assert response.json() == {
        "status": "SUCCEEDED",
        "command_id": "11111111-1111-1111-1111-111111111111",
        "idempotency_key": "22222222-2222-2222-2222-222222222222",
        "result_code": "CASE_CREATED",
        "case_id": "33333333-3333-3333-3333-333333333333",
        "version": 0,
        "event_ids": ["44444444-4444-4444-4444-444444444444"],
        "navigation": "CASE_OVERVIEW",
        "replayed": False,
    }
    assert Capability.CASE_CREATE in actor.capabilities


def test_create_case_http_returns_200_on_idempotent_replay(monkeypatch) -> None:
    response = _client(
        dispatcher=SimpleNamespace(dispatch=lambda **_kwargs: _dispatch_result(replayed=True)),
        actor=_actor(),
        monkeypatch=monkeypatch,
    ).post("/api/v1/cases", json=_payload())

    assert response.status_code == 200
    assert response.json()["replayed"] is True


def test_create_case_http_denies_non_patron(monkeypatch) -> None:
    actor = replace(
        _actor(),
        actor_kind=ActorKind.COLLABORATEUR,
        capabilities=frozenset(),
    )
    dispatcher = SimpleNamespace(dispatch=lambda **_kwargs: pytest.fail("must not dispatch"))

    response = _client(dispatcher=dispatcher, actor=actor, monkeypatch=monkeypatch).post(
        "/api/v1/cases",
        json=_payload(),
    )

    assert response.status_code == 403


def test_create_case_http_maps_idempotency_reuse_to_409(monkeypatch) -> None:
    dispatcher = SimpleNamespace(
        dispatch=lambda **_kwargs: (_ for _ in ()).throw(
            IdempotencyKeyReusedError("idempotency key reused")
        )
    )

    response = _client(dispatcher=dispatcher, actor=_actor(), monkeypatch=monkeypatch).post(
        "/api/v1/cases",
        json=_payload(),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "IDEMPOTENCY_CONFLICT"}


def test_create_case_http_maps_invalid_scope_to_422(monkeypatch) -> None:
    def dispatch(**_kwargs):
        try:
            raise ValueError("CASE_SCOPE_AMBIGUOUS")
        except ValueError as error:
            raise CommandExecutionError("command failed") from error

    response = _client(
        dispatcher=SimpleNamespace(dispatch=dispatch),
        actor=_actor(),
        monkeypatch=monkeypatch,
    ).post("/api/v1/cases", json=_payload())

    assert response.status_code == 422
    assert response.json() == {"detail": "CASE_SCOPE_AMBIGUOUS"}
