from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.modules.submission.public.signature_contracts import SubmissionSignatureProjection


class SubmissionSignatureReader(Protocol):
    def get(
        self, *, tenant_id: UUID, signature_id: UUID
    ) -> SubmissionSignatureProjection | None: ...
