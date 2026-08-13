"""Erreurs métier du bounded context DCE/Consultation.

Elles restent indépendantes des modèles HTTP, ORM, stockage objet ou moteur
extracteur. Les adaptateurs traduiront ultérieurement ces erreurs vers APP-01.
"""


class DceDomainError(ValueError):
    """Base class for a DCE/Consultation domain invariant violation."""

    code = "DCE_DOMAIN_ERROR"


class ConsultationIdentityError(DceDomainError):
    """Raised when the durable consultation identity cannot be established."""

    code = "CONSULTATION_IDENTITY_INVALID"


class ConsultationLifecycleError(DceDomainError):
    """Raised when an operation is incompatible with Consultation lifecycle."""

    code = "CONSULTATION_LIFECYCLE_FORBIDS_ACTION"


class DocumentOriginalImmutableError(DceDomainError):
    """Raised when code attempts to replace an admitted corpus or original."""

    code = "DOCUMENT_ORIGINAL_IMMUTABLE"


class DceVersionUnusableError(DceDomainError):
    """Raised when a withdrawn or unusable DCE cannot support an operation."""

    code = "DCE_VERSION_UNUSABLE"


class SourceLocationRequiredError(DceDomainError):
    """Raised when a source-derived fact lacks a source or a locator."""

    code = "SOURCE_LOCATION_REQUIRED"
