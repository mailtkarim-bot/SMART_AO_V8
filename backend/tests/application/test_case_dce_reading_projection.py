# ruff: noqa: F401, F811
from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from app.modules.case.infrastructure.models.case import CaseRecord
from app.modules.dce.application.commands import RecordDceRequirementConfirmationCommand
from app.modules.dce.application.handlers import (
    RecordDceRequirementConfirmationHandler,
    RecordDceRequirementMaterializationRunHandler,
)
from app.modules.dce.application.queries import CaseDceReadingAvailability
from app.modules.dce.application.requirements import DceRequirementsService
from app.modules.dce.infrastructure.case_dce_reading_reader import (
    SqlAlchemyCaseDceReadingReader,
)
from app.modules.dce.infrastructure.models.dce_requirements import DceRequirementRecord
from app.modules.dce.infrastructure.models.dce_version import (
    DceDocumentClassificationRecord,
    DceVersionRecord,
)
from app.platform.events.dispatcher import CommandContext, CommandDispatcher

sys.path.append(str(Path(__file__).parent))

from test_dce_rc_analysis import (  # noqa: E402
    NOW,
    _extract_then_analyze,
    _seed_admitted_document,
    isolate_rc_analysis_records,
)

_FORBIDDEN_KEYS = frozenset(
    {
        "storage_key",
        "storage_object_id",
        "original_filename",
        "media_type",
        "byte_size",
        "sha256",
        "corpus_hash",
        "input_sha256",
        "text_sha256",
        "provenance_channel",
        "provenance_reference",
        "provenance_url",
        "withdrawal_source",
        "withdrawal_reason",
        "text",
        "excerpt",
        "locator_json",
        "confirmed_by_actor_id",
    }
)


@pytest.mark.db
@pytest.mark.integration
def test_case_dce_reading_projection_is_tenant_scoped_closed_and_deterministic(
    session_factory, tmp_path: Path
) -> None:
    from app.modules.dce.infrastructure.quarantine import LocalQuarantineStorageAdapter

    storage = LocalQuarantineStorageAdapter(root=tmp_path)
    source_bytes = b"Le DC1 est obligatoire.\nLa visite est obligatoire."
    tenant_id, document_id, dce_version_id = _seed_admitted_document(
        session_factory,
        storage=storage,
        source_bytes=source_bytes,
    )
    analysis = _extract_then_analyze(
        session_factory=session_factory,
        storage=storage,
        tenant_id=tenant_id,
        document_id=document_id,
        dce_version_id=dce_version_id,
    )
    materializer = DceRequirementsService(
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
    materializer.materialize(
        tenant_id=tenant_id,
        dce_version_id=dce_version_id,
        dce_rc_analysis_id=UUID(analysis.aggregate_refs[0]["aggregate_id"]),
        now=NOW,
    )

    with session_factory.begin() as session:
        dce = session.get(DceVersionRecord, dce_version_id)
        requirements = tuple(
            session.scalars(
                sa.select(DceRequirementRecord)
                .where(DceRequirementRecord.tenant_id == tenant_id)
                .order_by(DceRequirementRecord.id)
            )
        )
        assert dce is not None
        assert requirements
        case_id = uuid4()
        session.add(
            CaseRecord(
                id=case_id,
                tenant_id=tenant_id,
                aggregate_revision=1,
                functional_identity_hash="c" * 64,
                title="Réhabilitation école — Gros œuvre",
                object_description=None,
                business_origin="OPPORTUNITY",
                origin_reference_id=None,
                origin_rationale=None,
                consultation_id=dce.consultation_id,
                scope_kind="CUSTOM",
                scope_json={},
                scope_fingerprint="d" * 64,
                applicable_dce_version_id=dce_version_id,
                lifecycle="ACTIVE",
                commercial_stage="ANALYSIS",
                decision_readiness="NOT_ASSESSED",
                dce_freshness="CURRENT",
                responsibility_status="UNASSIGNED",
                stopped_reason=None,
                stopped_at=None,
                archived_reason=None,
                archived_at=None,
                created_by_actor_id=None,
                updated_by_actor_id=None,
            )
        )
        session.add(
            DceDocumentClassificationRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                dce_document_id=document_id,
                classification="UNRECOGNIZED_EXTERNAL_CLASSIFICATION",
                rationale=None,
                source="TEST",
                previous_classification_id=None,
                is_current=True,
                created_by_actor_id=None,
            )
        )

    requirement = requirements[0]
    confirmation_command = RecordDceRequirementConfirmationCommand(
        command_id=uuid4(),
        idempotency_key=uuid4(),
        correlation_id=dce_version_id,
        confirmation_id=uuid4(),
        requirement_id=requirement.id,
        expected_confirmation_revision=0,
        outcome="CONFIRMED",
        reason_code="SOURCE_REVIEWED",
    )
    CommandDispatcher(
        session_factory=session_factory,
        handlers={"RecordDceRequirementConfirmation": RecordDceRequirementConfirmationHandler()},
    ).dispatch(
        command=confirmation_command,
        context=CommandContext(
            tenant_id=tenant_id,
            actor_id=uuid4(),
            actor_kind="PATRON_ADMIN",
            received_at=NOW,
        ),
    )

    with session_factory() as session:
        reader = SqlAlchemyCaseDceReadingReader(session)
        projection = reader.get(tenant_id=tenant_id, case_id=case_id)
        tenant_denied = reader.get(tenant_id=uuid4(), case_id=case_id)

    assert projection is not None
    assert projection.availability is CaseDceReadingAvailability.AVAILABLE
    assert projection.reading is not None
    assert tenant_denied is None
    assert projection.reading.dce_version_id == dce_version_id
    assert projection.reading.counters.total == len(projection.reading.requirements)
    assert projection.reading.counters.confirmed == 1
    assert projection.reading.counters.pending_human_confirmation == len(
        projection.reading.requirements
    ) - 1
    assert all(
        item.document_family == "SOURCE_UNCLASSIFIED" for item in projection.reading.requirements
    )
    assert all("ligne" in item.source_locator_label for item in projection.reading.requirements)
    assert tuple(projection.reading.requirements) == tuple(
        sorted(
            projection.reading.requirements,
            key=lambda item: (
                item.requirement_type,
                item.source_locator_label,
                str(item.requirement_id),
            ),
        )
    )

    primitive_projection = asdict(projection)
    assert not _forbidden_keys(primitive_projection)
    assert "Le DC1 est obligatoire." not in str(primitive_projection)
    assert "dce-staging/" not in str(primitive_projection)
    assert "reglement-consultation.txt" not in str(primitive_projection)


@pytest.mark.db
@pytest.mark.integration
def test_case_dce_reading_projection_distinguishes_missing_case_and_missing_dce(
    session_factory, tmp_path: Path
) -> None:
    from app.modules.dce.infrastructure.quarantine import LocalQuarantineStorageAdapter

    storage = LocalQuarantineStorageAdapter(root=tmp_path)
    tenant_id, _, dce_version_id = _seed_admitted_document(
        session_factory,
        storage=storage,
        source_bytes=b"Le DC1 est obligatoire.",
    )
    with session_factory.begin() as session:
        dce = session.get(DceVersionRecord, dce_version_id)
        assert dce is not None
        dce.lifecycle = "SUPERSEDED"
        dce.superseded_at = NOW
        case_id = uuid4()
        superseded_case_id = uuid4()
        session.add(
            CaseRecord(
                id=case_id,
                tenant_id=tenant_id,
                aggregate_revision=1,
                functional_identity_hash="e" * 64,
                title="Affaire sans DCE applicable",
                object_description=None,
                business_origin="OPPORTUNITY",
                origin_reference_id=None,
                origin_rationale=None,
                consultation_id=dce.consultation_id,
                scope_kind="CUSTOM",
                scope_json={},
                scope_fingerprint="f" * 64,
                applicable_dce_version_id=None,
                lifecycle="ACTIVE",
                commercial_stage="ANALYSIS",
                decision_readiness="NOT_ASSESSED",
                dce_freshness="NO_DCE",
                responsibility_status="UNASSIGNED",
                stopped_reason=None,
                stopped_at=None,
                archived_reason=None,
                archived_at=None,
                created_by_actor_id=None,
                updated_by_actor_id=None,
            )
        )
        session.add(
            CaseRecord(
                id=superseded_case_id,
                tenant_id=tenant_id,
                aggregate_revision=1,
                functional_identity_hash="0" * 64,
                title="Affaire sur rectificatif à revoir",
                object_description=None,
                business_origin="OPPORTUNITY",
                origin_reference_id=None,
                origin_rationale=None,
                consultation_id=dce.consultation_id,
                scope_kind="CUSTOM",
                scope_json={},
                scope_fingerprint="1" * 64,
                applicable_dce_version_id=dce_version_id,
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

    with session_factory() as session:
        reader = SqlAlchemyCaseDceReadingReader(session)
        missing_case = reader.get(tenant_id=tenant_id, case_id=uuid4())
        missing_dce = reader.get(tenant_id=tenant_id, case_id=case_id)
        superseded = reader.get(tenant_id=tenant_id, case_id=superseded_case_id)

    assert missing_case is None
    assert missing_dce is not None
    assert missing_dce.availability is CaseDceReadingAvailability.NO_APPLICABLE_DCE
    assert missing_dce.reading is None
    assert superseded is not None
    assert superseded.availability is CaseDceReadingAvailability.AVAILABLE
    assert superseded.reading is not None
    assert superseded.reading.lifecycle == "SUPERSEDED"


def _forbidden_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return (set(value) & _FORBIDDEN_KEYS) | set().union(
            *(_forbidden_keys(item) for item in value.values())
        )
    if isinstance(value, (tuple, list)):
        return set().union(*(_forbidden_keys(item) for item in value)) if value else set()
    return set()
