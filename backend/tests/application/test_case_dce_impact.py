from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.dce.application.handlers import RecordCaseDceImpactRunHandler
from app.modules.dce.application.impact import CaseDceImpactService
from app.modules.dce.infrastructure.models.case_dce_impact import (
    CaseDceImpactItemRecord,
    CaseDceImpactRunRecord,
)
from app.modules.dce.infrastructure.models.consultation import ConsultationRecord
from app.modules.dce.infrastructure.models.dce_rc_analysis import (
    DceRcAnalysisRunRecord,
    DceRcRequirementObservationRecord,
)
from app.modules.dce.infrastructure.models.dce_requirements import (
    DceRequirementMaterializationRunRecord,
    DceRequirementRecord,
)
from app.modules.dce.infrastructure.models.dce_version import DceVersionRecord
from app.platform.events.dispatcher import (
    CommandContext,
    CommandDispatcher,
    CommandExecutionError,
)
from app.platform.persistence.models import DomainEventRecord, OutboxMessageRecord, TenantRecord
from sqlalchemy.orm import sessionmaker

sys.path.append(str(Path(__file__).parent))

from test_dce_rc_analysis import (  # noqa: E402, F401
    NOW,
    database_engine,
    isolate_rc_analysis_records,
)


@pytest.fixture(name="impact_session_factory")
def impact_session_factory_fixture(request):
    engine = request.getfixturevalue("database_engine")
    return sessionmaker(bind=engine, expire_on_commit=False)


def _seed_rectification_case(factory):
    tenant_id = uuid4()
    consultation_id = uuid4()
    predecessor_id = uuid4()
    successor_id = uuid4()
    case_id = uuid4()
    predecessor_analysis_id = uuid4()
    successor_analysis_id = uuid4()
    predecessor_run_id = uuid4()
    successor_run_id = uuid4()
    predecessor_observation_id = uuid4()
    successor_observation_id = uuid4()
    predecessor_requirement_id = uuid4()
    successor_requirement_id = uuid4()
    with factory.begin() as session:
        session.add(
            TenantRecord(
                id=tenant_id,
                slug=f"tenant-{tenant_id.hex[:12]}",
                lifecycle="ACTIVE",
            )
        )
        session.flush()
        session.add(
            ConsultationRecord(
                id=consultation_id,
                tenant_id=tenant_id,
                aggregate_revision=1,
                functional_identity_hash="a" * 64,
                buyer_legal_name="Ville de test",
                buyer_normalized_id="VILLE-TEST",
                external_reference="RECT-2026",
                object_label="Rectification de test",
                location_label="Lyon",
                source_channel="RECTIFICATION",
                source_reference="Fixture impact",
                source_received_at=NOW,
                lifecycle="OPEN",
                freshness="CURRENT",
                metadata_history_json=[],
                created_by_actor_id=None,
                updated_by_actor_id=None,
            )
        )
        session.add_all(
            [
                DceVersionRecord(
                    id=predecessor_id,
                    tenant_id=tenant_id,
                    aggregate_revision=1,
                    consultation_id=consultation_id,
                    corpus_hash="b" * 64,
                    predecessor_dce_version_id=None,
                    provenance_channel="MANUAL_UPLOAD",
                    provenance_reference="old",
                    provenance_url=None,
                    source_received_at=NOW,
                    lifecycle="SUPERSEDED",
                    integrity="VERIFIED",
                    classification_readiness="CLASSIFIED",
                    analysis_readiness="READY_FOR_ANALYSIS",
                    withdrawal_source=None,
                    withdrawal_reason=None,
                    superseded_at=NOW,
                    withdrawn_at=None,
                    created_by_actor_id=None,
                    updated_by_actor_id=None,
                ),
                DceVersionRecord(
                    id=successor_id,
                    tenant_id=tenant_id,
                    aggregate_revision=1,
                    consultation_id=consultation_id,
                    corpus_hash="c" * 64,
                    predecessor_dce_version_id=predecessor_id,
                    provenance_channel="RECTIFICATION",
                    provenance_reference="new",
                    provenance_url=None,
                    source_received_at=NOW,
                    lifecycle="ADMITTED",
                    integrity="VERIFIED",
                    classification_readiness="CLASSIFIED",
                    analysis_readiness="READY_FOR_ANALYSIS",
                    withdrawal_source=None,
                    withdrawal_reason=None,
                    superseded_at=None,
                    withdrawn_at=None,
                    created_by_actor_id=None,
                    updated_by_actor_id=None,
                ),
            ]
        )
        session.flush()
        session.add(
            CaseRecord(
                id=case_id,
                tenant_id=tenant_id,
                aggregate_revision=1,
                functional_identity_hash="d" * 64,
                title="Case rectificatif",
                object_description=None,
                business_origin="OPPORTUNITY",
                origin_reference_id=None,
                origin_rationale=None,
                consultation_id=consultation_id,
                scope_kind="CUSTOM",
                scope_json={},
                scope_fingerprint="e" * 64,
                applicable_dce_version_id=predecessor_id,
                lifecycle="ACTIVE",
                commercial_stage="ANALYSIS",
                decision_readiness="NOT_ASSESSED",
                dce_freshness="REVIEW_REQUIRED",
                responsibility_status="UNASSIGNED",
                stopped_reason=None,
                stopped_at=None,
                archived_reason=None,
                archived_at=None,
                created_by_actor_id=None,
                updated_by_actor_id=None,
            )
        )
        session.add_all(
            [
                DceRcAnalysisRunRecord(
                    id=predecessor_analysis_id,
                    tenant_id=tenant_id,
                    dce_version_id=predecessor_id,
                    input_manifest_sha256="1" * 64,
                    analyzer_id="TEST_ANALYZER",
                    analyzer_version="1",
                    status="COMPLETED",
                    source_fragment_count=1,
                    source_char_count=10,
                    failure_code=None,
                ),
                DceRcAnalysisRunRecord(
                    id=successor_analysis_id,
                    tenant_id=tenant_id,
                    dce_version_id=successor_id,
                    input_manifest_sha256="2" * 64,
                    analyzer_id="TEST_ANALYZER",
                    analyzer_version="1",
                    status="COMPLETED",
                    source_fragment_count=1,
                    source_char_count=10,
                    failure_code=None,
                ),
            ]
        )
        session.add_all(
            [
                DceRcRequirementObservationRecord(
                    id=predecessor_observation_id,
                    tenant_id=tenant_id,
                    analysis_id=predecessor_analysis_id,
                    dce_version_id=predecessor_id,
                    requirement_kind="RC_DOCUMENT_CANDIDATURE",
                    directive="REQUIRED_SIGNAL",
                    rule_id="RC_DOCUMENT_V1",
                    rule_version="1",
                    fragment_id=uuid4(),
                    start_byte_offset=0,
                    end_byte_offset=5,
                    excerpt="DC1",
                ),
                DceRcRequirementObservationRecord(
                    id=successor_observation_id,
                    tenant_id=tenant_id,
                    analysis_id=successor_analysis_id,
                    dce_version_id=successor_id,
                    requirement_kind="RC_FILE_CONSTRAINT",
                    directive="REQUIRED_SIGNAL",
                    rule_id="RC_FILE_V1",
                    rule_version="1",
                    fragment_id=uuid4(),
                    start_byte_offset=0,
                    end_byte_offset=8,
                    excerpt="format",
                ),
            ]
        )
        session.add_all(
            [
                DceRequirementMaterializationRunRecord(
                    id=predecessor_run_id,
                    tenant_id=tenant_id,
                    dce_version_id=predecessor_id,
                    dce_rc_analysis_id=predecessor_analysis_id,
                    input_manifest_sha256="3" * 64,
                    materializer_id="TEST_MATERIALIZER",
                    materializer_version="1",
                    status="COMPLETED",
                    source_observation_count=1,
                    failure_code=None,
                ),
                DceRequirementMaterializationRunRecord(
                    id=successor_run_id,
                    tenant_id=tenant_id,
                    dce_version_id=successor_id,
                    dce_rc_analysis_id=successor_analysis_id,
                    input_manifest_sha256="4" * 64,
                    materializer_id="TEST_MATERIALIZER",
                    materializer_version="1",
                    status="COMPLETED",
                    source_observation_count=1,
                    failure_code=None,
                ),
            ]
        )
        session.add_all(
            [
                DceRequirementRecord(
                    id=predecessor_requirement_id,
                    tenant_id=tenant_id,
                    requirements_run_id=predecessor_run_id,
                    dce_version_id=predecessor_id,
                    source_observation_id=predecessor_observation_id,
                    requirement_type="CANDIDATURE_DOCUMENT",
                    directive_signal="REQUIRED_SIGNAL",
                    confirmation_status="PENDING_HUMAN_CONFIRMATION",
                    uncertainty_status="SOURCE_SIGNAL_ONLY",
                ),
                DceRequirementRecord(
                    id=successor_requirement_id,
                    tenant_id=tenant_id,
                    requirements_run_id=successor_run_id,
                    dce_version_id=successor_id,
                    source_observation_id=successor_observation_id,
                    requirement_type="FILE_CONSTRAINT",
                    directive_signal="REQUIRED_SIGNAL",
                    confirmation_status="PENDING_HUMAN_CONFIRMATION",
                    uncertainty_status="SOURCE_SIGNAL_ONLY",
                ),
            ]
        )
    return tenant_id, case_id, predecessor_id, successor_id


def _service(factory) -> CaseDceImpactService:
    return CaseDceImpactService(
        session_factory=factory,
        dispatcher=CommandDispatcher(
            session_factory=factory,
            handlers={"RecordCaseDceImpactRun": RecordCaseDceImpactRunHandler()},
        ),
    )


@pytest.mark.db
@pytest.mark.integration
def test_case_dce_impact_is_conservative_replayed_and_append_only(
    impact_session_factory,
) -> None:
    tenant_id, case_id, predecessor_id, successor_id = _seed_rectification_case(
        impact_session_factory
    )

    service = _service(impact_session_factory)
    first = service.run(
        tenant_id=tenant_id,
        case_id=case_id,
        predecessor_dce_version_id=predecessor_id,
        successor_dce_version_id=successor_id,
        now=NOW,
    )
    replay = service.run(
        tenant_id=tenant_id,
        case_id=case_id,
        predecessor_dce_version_id=predecessor_id,
        successor_dce_version_id=successor_id,
        now=NOW,
    )

    assert first.result_code == "CASE_DCE_IMPACT_RECORDED"
    assert replay.result_code == first.result_code
    with impact_session_factory() as session:
        runs = list(
            session.scalars(
                sa.select(CaseDceImpactRunRecord).where(
                    CaseDceImpactRunRecord.tenant_id == tenant_id
                )
            )
        )
        items = list(
            session.scalars(
                sa.select(CaseDceImpactItemRecord).where(
                    CaseDceImpactItemRecord.tenant_id == tenant_id
                )
            )
        )
        events = list(session.scalars(sa.select(DomainEventRecord)))
        outbox = list(session.scalars(sa.select(OutboxMessageRecord)))

    assert len(runs) == 1
    assert len(items) == 3
    assert {item.impact_kind for item in items} == {
        "DCE_VERSION_REPLACED",
        "PREVIOUS_REQUIREMENT_REQUIRES_REVIEW",
        "SUCCESSOR_REQUIREMENT_CANDIDATE",
    }
    assert all(item.review_state in {"REVIEW_REQUIRED", "PENDING_HUMAN_REVIEW"} for item in items)
    assert len(events) == 1
    assert len(outbox) == 1
    with pytest.raises(sa.exc.DBAPIError), impact_session_factory.begin() as session:
        run = session.get(CaseDceImpactRunRecord, runs[0].id)
        assert run is not None
        run.status = "NO_SIGNAL"


@pytest.mark.db
@pytest.mark.integration
def test_case_dce_impact_rejects_human_actor_without_durable_rows(
    impact_session_factory,
) -> None:
    command = {
        "command_id": uuid4(),
        "idempotency_key": uuid4(),
        "correlation_id": uuid4(),
        "impact_run_id": uuid4(),
        "case_id": uuid4(),
        "predecessor_dce_version_id": uuid4(),
        "successor_dce_version_id": uuid4(),
        "input_manifest_sha256": "a" * 64,
        "algorithm_id": "smart-ao-case-dce-impact",
        "algorithm_version": "1",
        "status": "NO_SIGNAL",
        "previous_requirement_count": 0,
        "successor_requirement_count": 0,
        "items": [],
    }
    from app.modules.dce.application.commands import RecordCaseDceImpactRunCommand

    with pytest.raises(CommandExecutionError):
        CommandDispatcher(
            session_factory=impact_session_factory,
            handlers={"RecordCaseDceImpactRun": RecordCaseDceImpactRunHandler()},
        ).dispatch(
            command=RecordCaseDceImpactRunCommand(**command),
            context=CommandContext(
                tenant_id=uuid4(),
                actor_id=uuid4(),
                actor_kind="PATRON_ADMIN",
                received_at=datetime.now(tz=UTC),
            ),
        )

    with impact_session_factory() as session:
        assert session.scalar(sa.select(CaseDceImpactRunRecord)) is None
