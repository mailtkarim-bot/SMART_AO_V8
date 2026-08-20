from uuid import uuid4

from app.modules.preparation.application.document_content import (
    TechnicalDocumentFacts,
    build_technical_document,
)
from app.modules.preparation.application.ports import PreparationRequirementInput


def test_technical_document_is_canonical_structured_and_non_financial() -> None:
    facts = TechnicalDocumentFacts(
        case_id=uuid4(),
        dce_version_id=uuid4(),
        readiness_state="READY_WITH_WARNINGS",
        readiness_revision=3,
        document_version=2,
        requirements=(
            PreparationRequirementInput(
                requirement_id=uuid4(),
                requirement_type="SITE_VISIT",
                directive_signal="REQUIRED_SIGNAL",
                confirmation_outcome="CONFIRMED",
            ),
            PreparationRequirementInput(
                requirement_id=uuid4(),
                requirement_type="OFFER_DOCUMENT",
                directive_signal="OPTIONAL_SIGNAL",
                confirmation_outcome=None,
            ),
        ),
        blocker_codes=(),
        warning_codes=("TASK_RESULT_MISSING",),
    )

    content = build_technical_document(facts)
    repeated = build_technical_document(facts)

    assert content == repeated
    assert "## Exigences DCE confirmées" in content
    assert "SITE_VISIT" in content
    assert "PENDING_HUMAN_CONFIRMATION" in content
    assert "TASK_RESULT_MISSING" in content
    forbidden = {"prix", "marge", "trésorerie", "chiffrage", "go/no-go"}
    assert not forbidden.intersection(content.casefold())
