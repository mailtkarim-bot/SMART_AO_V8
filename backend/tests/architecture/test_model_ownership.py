from __future__ import annotations

from pathlib import Path

from app.modules.enterprise.infrastructure.models import (
    CaseCapabilityGapRecord,
    CaseCapabilityProposalRecord,
    EnterpriseCapabilityProofLinkRecord,
    EnterpriseCapabilityRecord,
    EnterpriseCapabilityVersionRecord,
)
from app.modules.patron_action.infrastructure.models import (
    PatronActionRecord,
    PatronActionTransitionRecord,
)
from app.modules.preparation.infrastructure.models import (
    GeneratedTechnicalDocumentRecord,
    PreparationPackageRecord,
    PreparationReadinessRecord,
    PreparationReviewCorrectionRecord,
    PreparationReviewRecord,
    PreparationSnapshotRecord,
    PreparationTransmissionRecord,
    TechnicalResponseDraftRecord,
)
from app.modules.pricing.infrastructure.models import (
    FinancialReportLineRecord,
    FinancialReportPublicationRecord,
    FinancialReportSnapshotRecord,
    PricingImportBatchRecord,
    PricingImportRowRecord,
    PricingImportTransitionRecord,
    PricingScenarioRecord,
    PricingScenarioTransitionRecord,
)
from app.modules.submission.infrastructure.models import (
    SubmissionEvidenceRecord,
    SubmissionPackageRecord,
    SubmissionSignatureRecord,
)

OWNERS = {
    **{
        model: "app.modules.pricing.infrastructure.models.financial"
        for model in (
            FinancialReportLineRecord,
            FinancialReportPublicationRecord,
            FinancialReportSnapshotRecord,
            PricingImportBatchRecord,
            PricingImportRowRecord,
            PricingImportTransitionRecord,
            PricingScenarioRecord,
            PricingScenarioTransitionRecord,
        )
    },
    **{
        model: "app.modules.preparation.infrastructure.models.preparation"
        for model in (
            GeneratedTechnicalDocumentRecord,
            PreparationPackageRecord,
            PreparationReadinessRecord,
            PreparationReviewCorrectionRecord,
            PreparationReviewRecord,
            PreparationSnapshotRecord,
            PreparationTransmissionRecord,
            TechnicalResponseDraftRecord,
        )
    },
    **{
        model: "app.modules.submission.infrastructure.models.submission"
        for model in (
            SubmissionEvidenceRecord,
            SubmissionPackageRecord,
            SubmissionSignatureRecord,
        )
    },
    **{
        model: "app.modules.patron_action.infrastructure.models.patron_action"
        for model in (PatronActionRecord, PatronActionTransitionRecord)
    },
    **{
        model: "app.modules.enterprise.infrastructure.models.enterprise"
        for model in (
            CaseCapabilityGapRecord,
            CaseCapabilityProposalRecord,
            EnterpriseCapabilityProofLinkRecord,
            EnterpriseCapabilityRecord,
            EnterpriseCapabilityVersionRecord,
        )
    },
}


def test_business_orm_models_are_declared_by_their_bounded_context() -> None:
    assert {model.__module__ for model in OWNERS} == set(OWNERS.values())


def test_security_model_module_keeps_no_moved_business_class_declaration() -> None:
    source = Path("backend/app/platform/security/models.py").read_text(encoding="utf-8")
    for model in OWNERS:
        assert f"class {model.__name__}" not in source
