from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from app.modules.submission.application.signature_reader import SubmissionSignatureReader
from app.modules.submission.public.signature_contracts import SubmissionSignatureProjection
from app.platform.security.models import SubmissionSignatureRecord
from sqlalchemy.orm import Session, sessionmaker


class SqlAlchemySubmissionSignatureReader(SubmissionSignatureReader):
    """Tenant-scoped projection reader with no cryptographic fields in output."""

    def __init__(self, *, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get(
        self, *, tenant_id: UUID, signature_id: UUID
    ) -> SubmissionSignatureProjection | None:
        with self._session_factory() as session:
            record = session.scalar(
                sa.select(SubmissionSignatureRecord).where(
                    SubmissionSignatureRecord.tenant_id == tenant_id,
                    SubmissionSignatureRecord.id == signature_id,
                )
            )
        if record is None:
            return None
        return SubmissionSignatureProjection(
            signature_id=record.id,
            submission_package_id=record.submission_package_id,
            case_id=record.case_id,
            provider=record.provider,
            status=record.status,
            expected_package_version=record.expected_package_version,
            revision=1 if record.status == "REQUESTED" else 2,
        )
