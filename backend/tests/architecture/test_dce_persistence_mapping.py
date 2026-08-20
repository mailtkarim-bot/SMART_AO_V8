from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.modules.dce.domain.dce_version import (
    AnalysisReadiness,
    ClassificationReadiness,
    DceIntegrity,
    DceLifecycle,
    DceVersion,
)
from app.modules.dce.infrastructure.mappings import to_dce_version_persistence_state


@pytest.mark.architecture
def test_dce_domain_enums_have_an_explicit_persistence_mapping() -> None:
    version = DceVersion(
        id=uuid4(),
        tenant_id=uuid4(),
        consultation_id=uuid4(),
        corpus_hash="a" * 64,
        documents=(),
        provenance="test",
        received_at=datetime.now(tz=UTC),
        lifecycle=DceLifecycle.SUPERSEDED,
        integrity=DceIntegrity.VERIFIED,
        classification_readiness=ClassificationReadiness.CLASSIFIED,
        analysis_readiness=AnalysisReadiness.READY_FOR_ANALYSIS,
    )

    state = to_dce_version_persistence_state(version)

    assert state.lifecycle == "SUPERSEDED"
    assert state.integrity == "VERIFIED"
    assert state.classification_readiness == "CLASSIFIED"
    assert state.analysis_readiness == "READY_FOR_ANALYSIS"


@pytest.mark.architecture
def test_dce_persistence_mapping_rejects_non_domain_enum_values() -> None:
    version = DceVersion(
        id=uuid4(),
        tenant_id=uuid4(),
        consultation_id=uuid4(),
        corpus_hash="a" * 64,
        documents=(),
        provenance="test",
        received_at=datetime.now(tz=UTC),
    )
    version.lifecycle = "ADMITTED"  # type: ignore[assignment]

    with pytest.raises(TypeError, match="expected DceLifecycle"):
        to_dce_version_persistence_state(version)
