"""Closed server-side capability catalog for SEC-01 role policies."""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from .context import ActorKind


class Capability(StrEnum):
    """Stable action names recognized by the first authorization perimeter."""

    CONSULTATION_CREATE = "consultation.create"
    CASE_CREATE = "case.create"
    CONSULTATION_READ = "consultation.read"
    DCE_PREPARE = "dce.prepare"
    CASE_DCE_READ = "case.dce.read"
    MARKET_WATCH_READ = "market.watch.read"
    OPPORTUNITY_PROFILE_READ = "opportunity.profile.read"
    OPPORTUNITY_PROFILE_WRITE = "opportunity.profile.write"
    OPPORTUNITY_OBSERVATION_READ = "opportunity.observation.read"
    OPPORTUNITY_OBSERVATION_QUALIFY = "opportunity.observation.qualify"
    DCE_REQUIREMENT_CONFIRM = "dce.requirement.confirm"
    ASSIGNMENT_ACKNOWLEDGE = "assignment.acknowledge"
    ASSIGNMENT_CLARIFY = "assignment.clarify"
    ASSIGNMENT_HISTORY_READ = "assignment.history.read"
    ASSIGNMENT_UNAVAILABILITY = "assignment.unavailability"
    WORK_TASK_READ = "work.task.read"
    WORK_TASK_WRITE = "work.task.write"
    ASSIGNMENT_MANAGE = "assignment.manage"
    DOCUMENT_ADMIN_READ = "document.administrative.read"
    PREPARATION_TRANSMIT = "preparation.transmit"
    PREPARATION_READINESS_WRITE = "preparation.readiness.write"
    PREPARATION_DOCUMENT_WRITE = "preparation.document.write"
    PREPARATION_CAPABILITY_PROPOSE = "preparation.capability.propose"
    PREPARATION_CAPABILITY_GAP_REPORT = "preparation.capability.gap.report"
    PREPARATION_REVIEW_REQUEST = "preparation.review.request"
    PREPARATION_REVIEW_DECIDE = "preparation.review.decide"
    MEMBERSHIP_MANAGE = "membership.manage"
    TENANT_MANAGE = "tenant.manage"
    DECISION_MANAGE = "decision.manage"
    DECISION_FINALIZE = "decision.finalize"
    DECISION_RISK_WRITE = "decision.risk.write"
    DECISION_RISK_LINK_WRITE = "decision.risk.link.write"
    DECISION_RISK_READ = "decision.risk.read"
    PRICING_READ = "pricing.read"
    PRICING_WRITE = "pricing.write"
    SUBMISSION_AUTHORIZE = "submission.authorize"
    SUBMISSION_SIGNATURE_READ = "submission.signature.read"
    SUBMISSION_SIGNATURE_WRITE = "submission.signature.write"
    PATRON_ACTION_READ = "patron.action.read"
    PATRON_ACTION_WRITE = "patron.action.write"
    SENSITIVE_EXPORT = "export.sensitive"
    AUDIT_READ = "audit.read"
    FINANCIAL_REPORT_READ = "financial.report.read"
    FINANCIAL_REPORT_CREATE = "financial.report.create"
    FINANCIAL_REPORT_PUBLISH = "financial.report.publish"
    FINANCIAL_REPORT_LINE_WRITE = "financial.report.line.write"
    ENTERPRISE_LIBRARY_READ = "enterprise.library.read"
    ENTERPRISE_REGISTRY_READ = "enterprise.registry.read"
    ENTERPRISE_LIBRARY_WRITE = "enterprise.library.write"
    ENTERPRISE_CAPABILITY_READ = "enterprise.capability.read"
    ENTERPRISE_CAPABILITY_WRITE = "enterprise.capability.write"
    SYSTEM_JOB_EXECUTE = "system.job.execute"


_PATRON_ADMIN_CAPABILITIES = frozenset(
    {
        Capability.CONSULTATION_CREATE,
        Capability.CASE_CREATE,
        Capability.CONSULTATION_READ,
        Capability.DCE_PREPARE,
        Capability.CASE_DCE_READ,
        Capability.MARKET_WATCH_READ,
        Capability.OPPORTUNITY_PROFILE_READ,
        Capability.OPPORTUNITY_PROFILE_WRITE,
        Capability.OPPORTUNITY_OBSERVATION_READ,
        Capability.OPPORTUNITY_OBSERVATION_QUALIFY,
        Capability.DCE_REQUIREMENT_CONFIRM,
        Capability.ASSIGNMENT_MANAGE,
        Capability.DOCUMENT_ADMIN_READ,
        Capability.PREPARATION_TRANSMIT,
        Capability.PREPARATION_READINESS_WRITE,
        Capability.PREPARATION_DOCUMENT_WRITE,
        Capability.MEMBERSHIP_MANAGE,
        Capability.TENANT_MANAGE,
        Capability.DECISION_MANAGE,
        Capability.DECISION_FINALIZE,
        Capability.DECISION_RISK_WRITE,
        Capability.DECISION_RISK_LINK_WRITE,
        Capability.DECISION_RISK_READ,
        Capability.PRICING_READ,
        Capability.PRICING_WRITE,
        Capability.SUBMISSION_AUTHORIZE,
        Capability.SUBMISSION_SIGNATURE_READ,
        Capability.SUBMISSION_SIGNATURE_WRITE,
        Capability.PATRON_ACTION_READ,
        Capability.PATRON_ACTION_WRITE,
        Capability.SENSITIVE_EXPORT,
        Capability.AUDIT_READ,
        Capability.FINANCIAL_REPORT_READ,
        Capability.FINANCIAL_REPORT_CREATE,
        Capability.FINANCIAL_REPORT_PUBLISH,
        Capability.FINANCIAL_REPORT_LINE_WRITE,
        Capability.ENTERPRISE_LIBRARY_READ,
        Capability.ENTERPRISE_REGISTRY_READ,
        Capability.ENTERPRISE_LIBRARY_WRITE,
        Capability.ENTERPRISE_CAPABILITY_READ,
        Capability.ENTERPRISE_CAPABILITY_WRITE,
        Capability.PREPARATION_REVIEW_DECIDE,
    }
)
_COLLABORATOR_CAPABILITIES = frozenset(
    {
        Capability.CONSULTATION_READ,
        Capability.DCE_PREPARE,
        Capability.CASE_DCE_READ,
        Capability.MARKET_WATCH_READ,
        Capability.DCE_REQUIREMENT_CONFIRM,
        Capability.ASSIGNMENT_ACKNOWLEDGE,
        Capability.ASSIGNMENT_CLARIFY,
        Capability.ASSIGNMENT_UNAVAILABILITY,
        Capability.ASSIGNMENT_HISTORY_READ,
        Capability.WORK_TASK_READ,
        Capability.WORK_TASK_WRITE,
        Capability.DOCUMENT_ADMIN_READ,
        Capability.PREPARATION_TRANSMIT,
        Capability.PREPARATION_READINESS_WRITE,
        Capability.PREPARATION_DOCUMENT_WRITE,
        Capability.PREPARATION_CAPABILITY_PROPOSE,
        Capability.PREPARATION_CAPABILITY_GAP_REPORT,
        Capability.PREPARATION_REVIEW_REQUEST,
    }
)
_DELEGABLE_CAPABILITIES = frozenset(
    {
        Capability.CONSULTATION_READ,
        Capability.DCE_PREPARE,
        Capability.CASE_DCE_READ,
        Capability.MARKET_WATCH_READ,
        Capability.DCE_REQUIREMENT_CONFIRM,
        Capability.DOCUMENT_ADMIN_READ,
        Capability.WORK_TASK_READ,
        Capability.WORK_TASK_WRITE,
        Capability.PREPARATION_TRANSMIT,
        Capability.PREPARATION_READINESS_WRITE,
        Capability.PREPARATION_DOCUMENT_WRITE,
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
