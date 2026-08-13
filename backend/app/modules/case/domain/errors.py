"""Erreurs métier du bounded context Case.

Ces erreurs sont indépendantes de FastAPI et de la persistance. Les interfaces
les convertiront plus tard vers les codes APP-01 correspondants.
"""


class CaseDomainError(ValueError):
    """Base class for an invariant violation in the Case aggregate."""

    code = "CASE_DOMAIN_ERROR"


class CaseScopeAmbiguousError(CaseDomainError):
    """Raised when a CaseScope does not identify an explicit business perimeter."""

    code = "CASE_SCOPE_AMBIGUOUS"


class CrossTenantReferenceError(CaseDomainError):
    """Raised when a Case receives a reference owned by another tenant."""

    code = "NOT_FOUND_OR_FORBIDDEN"


class CaseLifecycleForbidsActionError(CaseDomainError):
    """Raised when the Case lifecycle or stage forbids a requested mutation."""

    code = "CASE_LIFECYCLE_FORBIDS_ACTION"
