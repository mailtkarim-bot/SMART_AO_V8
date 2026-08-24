from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.modules.decision.domain.submission_gate import DecisionSubmissionGateSnapshot


class SubmissionDecisionGateReader(Protocol):
    """Reads only non-financial Decision facts inside the caller transaction."""

    def read(
        self, *, session: object, tenant_id: UUID, case_id: UUID
    ) -> DecisionSubmissionGateSnapshot | None: ...
