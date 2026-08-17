# ruff: noqa: F401, F811
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from app.modules.dce.application.handlers import RecordDceRequirementMaterializationRunHandler
from app.modules.dce.application.requirements import DceRequirementsService
from app.modules.dce.infrastructure.models.dce_requirements import (
    DceRequirementMaterializationRunRecord,
    DceRequirementRecord,
)
from app.platform.events.dispatcher import CommandDispatcher

sys.path.append(str(Path(__file__).parent))

from test_dce_rc_analysis import (
    NOW,
    _extract_then_analyze,
    _seed_admitted_document,
    isolate_rc_analysis_records,
)


@pytest.mark.db
@pytest.mark.integration
def test_requirements_are_atomic_sourced_immutable_and_replayed(
    session_factory, tmp_path: Path
) -> None:
    from app.modules.dce.infrastructure.quarantine import LocalQuarantineStorageAdapter

    storage = LocalQuarantineStorageAdapter(root=tmp_path)
    tenant_id, document_id, dce_version_id = _seed_admitted_document(
        session_factory,
        storage=storage,
        source_bytes=(
            "Le DC1 est obligatoire. Le mémoire technique est obligatoire. "
            "Le dépôt électronique se fait sur le profil d'acheteur."
        ).encode(),
    )
    analysis = _extract_then_analyze(
        session_factory=session_factory,
        storage=storage,
        tenant_id=tenant_id,
        document_id=document_id,
        dce_version_id=dce_version_id,
    )
    service = DceRequirementsService(
        session_factory=session_factory,
        dispatcher=CommandDispatcher(
            session_factory=session_factory,
            handlers={
                "RecordDceRequirementMaterializationRun": (
                    RecordDceRequirementMaterializationRunHandler()
                )
            },
        ),
    )

    first = service.materialize(
        tenant_id=tenant_id,
        dce_version_id=dce_version_id,
        dce_rc_analysis_id=analysis.aggregate_refs[0]["aggregate_id"],
        now=NOW,
    )
    replay = service.materialize(
        tenant_id=tenant_id,
        dce_version_id=dce_version_id,
        dce_rc_analysis_id=analysis.aggregate_refs[0]["aggregate_id"],
        now=NOW,
    )

    assert first.result_code == "DCE_REQUIREMENTS_MATERIALIZED"
    assert replay.result_code == "DCE_REQUIREMENTS_MATERIALIZED"
    with session_factory() as session:
        requirements = list(session.scalars(sa.select(DceRequirementRecord)))
        run = session.scalar(sa.select(DceRequirementMaterializationRunRecord))
    assert run is not None
    assert {item.requirement_type for item in requirements} == {
        "CANDIDATURE_DOCUMENT",
        "OFFER_DOCUMENT",
        "SUBMISSION_CHANNEL",
    }
    assert {item.confirmation_status for item in requirements} == {"PENDING_HUMAN_CONFIRMATION"}
    with pytest.raises(sa.exc.DBAPIError), session_factory.begin() as session:
        requirement = session.get(DceRequirementRecord, requirements[0].id)
        assert requirement is not None
        requirement.confirmation_status = "CONFIRMED"
