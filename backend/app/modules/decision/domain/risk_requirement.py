from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class RiskRequirementRelation(StrEnum):
    IMPACTS = "IMPACTS"
    MITIGATES = "MITIGATES"
    CONSTRAINS = "CONSTRAINS"


class RiskRequirementLinkValidationError(ValueError):
    """Raised when a risk–requirement link violates domain invariants."""


@dataclass(frozen=True, slots=True)
class RiskRequirementLink:
    risk_id: UUID
    requirement_id: UUID
    relationship: RiskRequirementRelation
    rationale: str

    def validate(self) -> None:
        if not isinstance(self.risk_id, UUID) or not isinstance(self.requirement_id, UUID):
            raise RiskRequirementLinkValidationError("link identifiers are invalid")
        if not isinstance(self.relationship, RiskRequirementRelation):
            raise RiskRequirementLinkValidationError("relationship is invalid")
        if not self.rationale.strip():
            raise RiskRequirementLinkValidationError("rationale must be non-empty")
        if len(self.rationale) > 4_000:
            raise RiskRequirementLinkValidationError("rationale is too long")
