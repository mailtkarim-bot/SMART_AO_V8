from uuid import UUID

import sqlalchemy as sa
from app.modules.enterprise.application.enterprise_library import (
    EnterpriseCompanyProjection,
    EnterpriseDocumentProjection,
)
from app.modules.enterprise.infrastructure.models import (
    EnterpriseCompanyRecord,
    EnterpriseDocumentRecord,
    EnterpriseDocumentVerificationRecord,
)
from sqlalchemy.orm import Session, sessionmaker


class SqlAlchemyEnterpriseLibraryReader:
    """Infrastructure adapter for the tenant-scoped enterprise library projection."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def read_company(self, *, tenant_id: UUID) -> EnterpriseCompanyProjection | None:
        with self._session_factory() as session:
            company = session.scalar(
                sa.select(EnterpriseCompanyRecord).where(
                    EnterpriseCompanyRecord.tenant_id == tenant_id,
                )
            )
            if company is None:
                return None
            rows = session.execute(
                sa.select(
                    EnterpriseDocumentRecord.id,
                    EnterpriseDocumentRecord.document_kind,
                    EnterpriseDocumentRecord.document_label,
                    EnterpriseDocumentRecord.issued_at,
                    EnterpriseDocumentRecord.expires_at,
                    EnterpriseDocumentRecord.verification_status,
                    sa.select(EnterpriseDocumentVerificationRecord.outcome)
                    .where(
                        EnterpriseDocumentVerificationRecord.tenant_id
                        == EnterpriseDocumentRecord.tenant_id,
                        EnterpriseDocumentVerificationRecord.document_id
                        == EnterpriseDocumentRecord.id,
                    )
                    .order_by(EnterpriseDocumentVerificationRecord.revision.desc())
                    .limit(1)
                    .scalar_subquery()
                    .label("latest_verification"),
                    sa.func.coalesce(
                        sa.select(sa.func.max(EnterpriseDocumentVerificationRecord.revision))
                        .where(
                            EnterpriseDocumentVerificationRecord.tenant_id
                            == EnterpriseDocumentRecord.tenant_id,
                            EnterpriseDocumentVerificationRecord.document_id
                            == EnterpriseDocumentRecord.id,
                        )
                        .scalar_subquery(),
                        0,
                    ).label("verification_revision"),
                )
                .where(
                    EnterpriseDocumentRecord.tenant_id == tenant_id,
                    EnterpriseDocumentRecord.company_id == company.id,
                )
                .order_by(EnterpriseDocumentRecord.created_at, EnterpriseDocumentRecord.id)
            ).all()
        return EnterpriseCompanyProjection(
            company_id=company.id,
            aggregate_revision=company.aggregate_revision,
            legal_name=company.legal_name,
            trade_name=company.trade_name,
            siren=company.siren,
            siret=company.siret,
            vat_number=company.vat_number,
            address_line1=company.address_line1,
            postal_code=company.postal_code,
            city=company.city,
            country_code=company.country_code,
            documents=tuple(
                EnterpriseDocumentProjection(
                    document_id=row.id,
                    document_kind=row.document_kind,
                    document_label=row.document_label,
                    issued_at=row.issued_at,
                    expires_at=row.expires_at,
                    verification_status=row.latest_verification or row.verification_status,
                    verification_revision=row.verification_revision,
                )
                for row in rows
            ),
        )
