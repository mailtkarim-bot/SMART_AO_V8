from uuid import uuid4

import pytest
from app.modules.dce.application.analysis import (
    RcAnalysisSourceFragment,
    _project_rc_requirements,
    is_valid_rc_observation,
)
from app.modules.dce.application.commands import DceRequirementInput


@pytest.mark.domain
@pytest.mark.parametrize(
    ("document_family", "text", "requirement_kind", "rule_id"),
    [
        (
            "CCAP",
            "Les pénalités de retard sont applicables au titulaire.",
            "CCAP_PENALTIES",
            "CCAP_DELAY_PENALTIES_V1",
        ),
        (
            "CCAP",
            "Une retenue de garantie sera prélevée sur les acomptes.",
            "CCAP_RETENTION_GUARANTEE",
            "CCAP_RETENUE_GARANTIE_V1",
        ),
        (
            "CCAP",
            "Le cautionnement est exigé avant le démarrage.",
            "CCAP_GUARANTEE",
            "CCAP_CAUTIONNEMENT_V1",
        ),
        (
            "CCAP",
            "Une attestation d'assurance décennale est demandée.",
            "CCAP_INSURANCE",
            "CCAP_ASSURANCE_V1",
        ),
        (
            "CCTP",
            "Les variantes et options sont décrites dans le présent CCTP.",
            "CCTP_VARIANTS",
            "CCTP_VARIANTES_OPTIONS_V1",
        ),
        (
            "CCAP",
            "La sous-traitance doit être déclarée par DC4.",
            "CCAP_SUBCONTRACTING",
            "CCAP_SOUS_TRAITANCE_V1",
        ),
        (
            "CCTP",
            "La qualification professionnelle Qualibat est requise.",
            "CCAP_QUALIFICATIONS",
            "CCAP_QUALIFICATIONS_V1",
        ),
    ],
)
def test_contract_risk_rule_is_detected_only_in_ccap_or_cctp(
    document_family: str,
    text: str,
    requirement_kind: str,
    rule_id: str,
) -> None:
    source = RcAnalysisSourceFragment(
        dce_document_id=uuid4(),
        extraction_id=uuid4(),
        fragment_id=uuid4(),
        ordinal=1,
        text=text,
        text_sha256="a" * 64,
        document_family=document_family,
    )

    projection = _project_rc_requirements(sources=(source,))

    matching = [
        observation
        for observation in projection.observations
        if observation.requirement_kind == requirement_kind
    ]
    assert len(matching) == 1
    observation = matching[0]
    assert observation.rule_id == rule_id
    assert is_valid_rc_observation(
        requirement_kind=observation.requirement_kind,
        rule_id=observation.rule_id,
        directive=observation.directive,
        excerpt=observation.excerpt,
    )
    assert (
        text.encode("utf-8")[observation.start_byte_offset : observation.end_byte_offset].decode(
            "utf-8"
        )
        == observation.excerpt
    )


@pytest.mark.domain
def test_contract_risk_signal_is_accepted_by_materialized_requirement_contract() -> None:
    requirement = DceRequirementInput(
        requirement_id=uuid4(),
        source_observation_id=uuid4(),
        requirement_type="CONTRACT_RISK_SIGNAL",
        directive_signal="REQUIRED_SIGNAL",
        confirmation_status="PENDING_HUMAN_CONFIRMATION",
        uncertainty_status="SOURCE_SIGNAL_ONLY",
    )

    assert requirement.requirement_type == "CONTRACT_RISK_SIGNAL"


@pytest.mark.domain
def test_contract_risk_rules_do_not_run_on_unclassified_or_rc_documents() -> None:
    text = "Les pénalités de retard et les variantes sont interdites."
    sources = tuple(
        RcAnalysisSourceFragment(
            dce_document_id=uuid4(),
            extraction_id=uuid4(),
            fragment_id=uuid4(),
            ordinal=index,
            text=text,
            text_sha256="b" * 64,
            document_family=document_family,
        )
        for index, document_family in enumerate((None, "RC"), start=1)
    )

    projection = _project_rc_requirements(sources=sources)

    assert not any(
        observation.requirement_kind.startswith(("CCAP_", "CCTP_"))
        for observation in projection.observations
    )
