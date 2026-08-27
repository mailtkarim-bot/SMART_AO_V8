from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.modules.submission.application.signature_commands import (
    RecordSubmissionSignatureCommand,
    RequestSubmissionSignatureCommand,
)
from app.modules.submission.application.signature_service import (
    SubmissionSignatureReadService,
    SubmissionSignatureService,
)
from app.platform.events.dispatcher import CommandExecutionError
from app.platform.security.context import ActorContext, ActorKind, MembershipState

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)
PROVIDER = "TEST_PROVIDER"


def _actor(*, kind=ActorKind.PATRON_ADMIN, state=MembershipState.ACTIVE):
    return ActorContext(
        actor_id=uuid4(),
        identity_id=uuid4(),
        tenant_id=uuid4(),
        membership_id=uuid4(),
        actor_kind=kind,
        membership_state=state,
        capabilities=frozenset(),
        assigned_case_ids=frozenset(),
        session_id=uuid4(),
        authenticated_at=NOW,
        mfa_verified_at=None,
        correlation_id=uuid4(),
    )


def _request_command():
    return RequestSubmissionSignatureCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        signature_id=uuid4(),
        submission_package_id=uuid4(),
        expected_package_version=2,
        signer_membership_id=uuid4(),
        provider=PROVIDER,
    )


def _callback_command():
    return RecordSubmissionSignatureCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        signature_id=uuid4(),
        submission_package_id=uuid4(),
        provider=PROVIDER,
        provider_reference_hash="a" * 64,
        signature_sha256="b" * 64,
        outcome="SIGNED",
    )


class _Policy:
    def __init__(self, *, allowed=True):
        self.allowed = allowed
        self.calls = []

    def authorize(self, *, context, request):
        self.calls.append((context, request))
        return SimpleNamespace(allowed=self.allowed, code="AUTHORIZATION_DENIED")


class _Dispatcher:
    def __init__(self):
        self.calls = []

    def dispatch(self, *, command, context):
        self.calls.append((command, context))
        return SimpleNamespace(result_code="ok")


class _Reader:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def get(self, **kwargs):
        self.calls.append(kwargs)
        return self.value


def test_signature_service_rejects_invalid_provider_configuration():
    with pytest.raises(ValueError, match="uppercase closed identifier"):
        SubmissionSignatureService(
            dispatcher=_Dispatcher(), policy=_Policy(), provider="arbitrary provider"
        )


def test_signature_service_authorizes_and_dispatches_with_server_actor_scope():
    policy = _Policy()
    dispatcher = _Dispatcher()
    actor = _actor()
    command = _request_command()

    result = SubmissionSignatureService(
        dispatcher=dispatcher,
        policy=policy,
        provider=PROVIDER,
    ).execute(actor=actor, command=command, now=NOW)

    assert result.result_code == "ok"
    assert dispatcher.calls[0][1].tenant_id == actor.tenant_id
    assert dispatcher.calls[0][1].actor_id == actor.actor_id
    assert policy.calls[0][1].action.value == "submission.signature.write"
    assert policy.calls[0][1].mfa_required is True


def test_signature_service_rejects_non_patron_or_inactive_actor():
    service = SubmissionSignatureService(
        dispatcher=_Dispatcher(), policy=_Policy(), provider=PROVIDER
    )
    command = _request_command()

    with pytest.raises(PermissionError, match="PATRON_REQUIRED"):
        service.execute(actor=_actor(kind=ActorKind.COLLABORATEUR), command=command, now=NOW)
    with pytest.raises(PermissionError, match="PATRON_REQUIRED"):
        service.execute(actor=_actor(state=MembershipState.SUSPENDED), command=command, now=NOW)


def test_signature_service_rejects_provider_not_configured_on_server():
    command = _callback_command()

    with pytest.raises(CommandExecutionError, match="INVALID_PROVIDER"):
        SubmissionSignatureService(
            dispatcher=_Dispatcher(), policy=_Policy(), provider=PROVIDER
        ).execute(
            actor=_actor(),
            command=command.model_copy(update={"provider": "OTHER_PROVIDER"}),
            now=NOW,
        )


def test_signature_service_rejects_denied_policy():
    with pytest.raises(PermissionError, match="AUTHORIZATION_DENIED"):
        SubmissionSignatureService(
            dispatcher=_Dispatcher(), policy=_Policy(allowed=False), provider=PROVIDER
        ).execute(actor=_actor(), command=_request_command(), now=NOW)


def test_signature_read_service_authorizes_tenant_scoped_minimal_projection():
    actor = _actor()
    signature_id = uuid4()
    projection = SimpleNamespace(
        signature_id=signature_id,
        submission_package_id=uuid4(),
        case_id=uuid4(),
        provider=PROVIDER,
        status="REQUESTED",
        expected_package_version=2,
        revision=1,
    )
    reader = _Reader(projection)

    result = SubmissionSignatureReadService(
        reader=reader, policy=_Policy()
    ).read(actor=actor, signature_id=signature_id, now=NOW)

    assert result is projection
    assert reader.calls == [{"tenant_id": actor.tenant_id, "signature_id": signature_id}]
