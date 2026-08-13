"""Erreurs métier du bounded context Decision.

Le domaine utilise ces erreurs sans dépendre de l'autorisation HTTP, de la
persistance ou d'un Process Manager. Les adaptateurs les traduiront ensuite
vers les codes APP-01.
"""


class DecisionDomainError(ValueError):
    """Base class for a Decision invariant violation."""

    code = "DECISION_DOMAIN_ERROR"


class DecisionContextIncompleteError(DecisionDomainError):
    """Raised when a DecisionContext cannot be frozen for patron review."""

    code = "DECISION_CONTEXT_INCOMPLETE"


class StaleDecisionContextError(DecisionDomainError):
    """Raised when the displayed context fingerprint differs from the frozen one."""

    code = "STALE_CONTEXT"


class DecisionAlreadyFinalizedError(DecisionDomainError):
    """Raised when a final Decision would be rewritten instead of superseded."""

    code = "DECISION_ALREADY_FINALIZED"


class DecisionLifecycleError(DecisionDomainError):
    """Raised when a command does not fit the Decision lifecycle."""

    code = "DECISION_LIFECYCLE_FORBIDS_ACTION"


class ConditionOwnerRequiredError(DecisionDomainError):
    """Raised for a conditional Go condition without an accountable owner."""

    code = "CONDITION_OWNER_REQUIRED"


class ConditionConsequenceRequiredError(DecisionDomainError):
    """Raised for a condition without deadline/reason or failure consequence."""

    code = "CONDITION_CONSEQUENCE_REQUIRED"
