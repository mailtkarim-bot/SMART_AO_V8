from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from app.modules.enterprise.application.enterprise_capability import EnterpriseCapabilityService
from app.modules.enterprise.application.enterprise_capability_commands import (
    AddEnterpriseCapabilityVersionCommand,
)
from app.platform.security.capabilities import Capability
from app.platform.security.context import ActorKind

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)


def test_add_version_resolves_company_through_application_port() -> None:
    capability_id = uuid4()
    company_id = uuid4()
    tenant_id = uuid4()
    reader = Mock()
    reader.company_id_for_capability.return_value = company_id
    policy = Mock()
    policy.authorize.return_value = SimpleNamespace(allowed=True, code="ALLOWED")
    dispatcher = Mock()
    actor = SimpleNamespace(
        actor_kind=ActorKind.PATRON_ADMIN,
        membership_id=uuid4(),
        tenant_id=tenant_id,
        actor_id=uuid4(),
        identity_id=uuid4(),
        session_id=uuid4(),
        correlation_id=uuid4(),
    )
    command = AddEnterpriseCapabilityVersionCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        capability_id=capability_id,
        version_id=uuid4(),
        expected_revision=1,
        title="Méthode de pose",
        description="Équipe qualifiée et processus documenté.",
        valid_from=NOW,
        usage_scope="Marchés de travaux publics",
    )

    EnterpriseCapabilityService(
        session_factory=Mock(),
        capability_context_reader=reader,
        dispatcher=dispatcher,
        policy=policy,
    ).add_version(actor=actor, command=command, now=NOW)

    reader.company_id_for_capability.assert_called_once_with(
        tenant_id=tenant_id, capability_id=capability_id
    )
    authorization_request = policy.authorize.call_args.kwargs["request"]
    assert authorization_request.action is Capability.ENTERPRISE_CAPABILITY_WRITE
    assert authorization_request.resource.resource_id == company_id
    dispatcher.dispatch.assert_called_once()
