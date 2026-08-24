"""Pure domain rules for structured CCAP/CCTP risks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RiskValidationError(ValueError):
    """Raised when a structured risk violates the domain contract."""


class RiskCategory(StrEnum):
    CCAP = "CCAP"
    CCTP = "CCTP"


class RiskSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskLikelihood(StrEnum):
    RARE = "RARE"
    POSSIBLE = "POSSIBLE"
    LIKELY = "LIKELY"
    ALMOST_CERTAIN = "ALMOST_CERTAIN"


class RiskTreatment(StrEnum):
    OPEN = "OPEN"
    ACCEPTED = "ACCEPTED"
    MITIGATED = "MITIGATED"


@dataclass(frozen=True, slots=True)
class StructuredRisk:
    category: RiskCategory
    risk_code: str
    title: str
    statement: str
    severity: RiskSeverity
    likelihood: RiskLikelihood
    treatment: RiskTreatment
    source_excerpt: str
    start_byte_offset: int
    end_byte_offset: int
    source_locator: dict[str, object]

    def validate(self) -> None:
        if not self.risk_code.strip() or len(self.risk_code.strip()) > 100:
            raise RiskValidationError("risk_code must be between 1 and 100 characters")
        if not self.title.strip() or len(self.title.strip()) > 240:
            raise RiskValidationError("title must be between 1 and 240 characters")
        if not self.statement.strip():
            raise RiskValidationError("statement must not be empty")
        if not self.source_excerpt.strip() or len(self.source_excerpt) > 2_000:
            raise RiskValidationError("source_excerpt must be between 1 and 2000 characters")
        if self.start_byte_offset < 0 or self.end_byte_offset <= self.start_byte_offset:
            raise RiskValidationError("source offsets must be ordered and non-negative")
        if not self.source_locator:
            raise RiskValidationError("source_locator must not be empty")
