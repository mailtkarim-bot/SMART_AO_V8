"""Closed server-side capability catalog for SEC-01 role policies."""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from .context import ActorKind


class Capability(StrEnum):
    """Stable action names recognized by the first authorization perimeter."""

    CONSULTATION_CREATE = "consultation.create"
    CONSULTATION_READ = "consultation.read"
    DCE_PREPARE = "dce.prepare"
    CASE_DCE_READ = "case.dce.read"
    DCE_REQUIREMENT_CONFIRM = "dce.requirement.confirm"
    ASSIGNMENT_ACKNOWLEDGE = "assignment.acknowledge"
    ASSIGNMENT_CLARIFY = "assignment.clarify"
    ASSIGNMENT_HISTORY_READ = "assignment.history.read"
    ASSIGNMENT_UNAVAILABILITY = "assignment.unavailability"
    ASSIGNMENT_MANAGE = "assignment.manage"
    DOCUMENT_ADMIN_READ = "document.administrative.read"
    PREPARATION_TRANSMIT = "preparation.transmit"
    MEMBERSHIP_MANAGE = "membership.manage"
    TENANT_MANAGE = "tenant.manage"
    DECISION_FINALIZE = "decision.finalize"
    PRICING_READ = "pricing.read"
    PRICING_WRITE = "pricing.write"
    SUBMISSION_AUTHORIZE = "submission.authorize"
    SENSITIVE_EXPORT = "export.sensitive"
    AUDIT_READ = "audit.read"
    FINANCIAL_REPORT_READ = "financial.report.read"
    SYSTEM_JOB_EXECUTE = "system.job.execute"


_PATRON_ADMIN_CAPABILITIES = frozenset(
    {
        Capability.CONSULTATION_CREATE,
        Capability.CONSULTATION_READ,
        Capability.DCE_PREPARE,
        Capability.CASE_DCE_READ,
        Capability.DCE_REQUIREMENT_CONFIRM,
        Capability.DOCUMENT_ADMIN_READ,
        Capability.PREPARATION_TRANSMIT,
        Capability.ASSIGNMENT_MANAGE,
        Capability.MEMBERSHIP_MANAGE,
        Capability.TENANT_MANAGE,
        Capability.DECISION_FINALIZE,
        Capability.PRICING_READ,
        Capability.PRICING_WRITE,
        Capability.SUBMISSION_AUTHORIZE,
        Capability.SENSITIVE_EXPORT,
        Capability.AUDIT_READ,
        Capability.FINANCIAL_REPORT_READ,
    }
)
_COLLABORATOR_CAPABILITIES = frozenset(
    {
        Capability.CONSULTATION_READ,
        Capability.DCE_PREPARE,
        Capability.CASE_DCE_READ,
        Capability.DCE_REQUIREMENT_CONFIRM,
        Capability.ASSIGNMENT_ACKNOWLEDGE,
        Capability.ASSIGNMENT_CLARIFY,
        Capability.ASSIGNMENT_HISTORY_READ,
        Capability.ASSIGNMENT_UNAVAILABILITY,
        Capability.DOCUMENT_ADMIN_READ,
        Capability.PREPARATION_TRANSMIT,
    }
)
_DELEGABLE_CAPABILITIES = frozenset(
    {
        Capability.CONSULTATION_READ,
        Capability.DCE_PREPARE,
        Capability.CASE_DCE_READ,
        Capability.DCE_REQUIREMENT_CONFIRM,
        Capability.DOCUMENT_ADMIN_READ,
        Capability.PREPARATION_TRANSMIT,
        Capability.DECISION_FINALIZE,
        Capability.SUBMISSION_AUTHORIZE,
        Capability.SENSITIVE_EXPORT,
    }
)


def capabilities_for(
    actor_kind: ActorKind,
    *,
    delegated_capabilities: Iterable[str] = (),
) -> frozenset[str]:
    """Calculate capabilities from trusted role and persisted future grants only.

    Caller-provided roles, JWT claims and request payloads must never reach this
    function as authority. Delegated capabilities are therefore intersected with
    the closed allow-list before being returned.
    """
    if actor_kind is ActorKind.PATRON_ADMIN:
        return frozenset(_PATRON_ADMIN_CAPABILITIES)
    if actor_kind is ActorKind.COLLABORATEUR:
        return frozenset(_COLLABORATOR_CAPABILITIES)
    if actor_kind is ActorKind.PATRON_DELEGATE:
        return frozenset(set(delegated_capabilities) & _DELEGABLE_CAPABILITIES)
    if actor_kind is ActorKind.SYSTEM:
        return frozenset({Capability.SYSTEM_JOB_EXECUTE})
    return frozenset()
