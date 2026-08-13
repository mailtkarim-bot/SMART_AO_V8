"""Executable M1 integration demonstration for the first SMART_AO slice.

This harness proves the durable history and cross-aggregate consequences of the
M1 path. It is not an HTTP route or a substitute for future command handlers:
inter-aggregate consequences are expressed explicitly and remain visible.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy.orm import Session, sessionmaker

from app.modules.case.infrastructure.models.case import (
    CaseConsultationLinkRecord,
    CaseDceApplicabilityHistoryRecord,
    CaseRecord,
)
from app.modules.dce.application.commands import CreateConsultationCommand
from app.modules.dce.application.handlers import CreateConsultationHandler
from app.modules.dce.infrastructure.models.dce_version import (
    DceDocumentRecord,
    DceVersionRecord,
)
from app.modules.decision.infrastructure.models.decision import (
    DecisionContextRecord,
    DecisionContextReferenceRecord,
    DecisionRecord,
)
from app.platform.events.dispatcher import CommandContext, CommandDispatcher


@dataclass(frozen=True, slots=True)
class M1ScenarioResult:
    consultation_id: UUID
    initial_dce_version_id: UUID
    rectification_dce_version_id: UUID
    case_id: UUID
    decision_id: UUID
    decision_context_id: UUID


class M1ScenarioRunner:
    """Runs the fixed M1 tender lifecycle on a dedicated tenant test dataset."""

    def __init__(self, *, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def run(self, *, tenant_id: UUID | str, actor_id: UUID | str) -> M1ScenarioResult:
        tenant = UUID(str(tenant_id))
        actor = UUID(str(actor_id))
        started_at = datetime(2026, 8, 13, 9, 0, tzinfo=UTC)
        consultation_id = uuid4()

        self._create_consultation(
            tenant_id=tenant,
            actor_id=actor,
            consultation_id=consultation_id,
            received_at=started_at,
        )

        initial_dce_version_id = uuid4()
        rectification_dce_version_id = uuid4()
        case_id = uuid4()
        decision_id = uuid4()
        decision_context_id = uuid4()
        scope_fingerprint = _sha256("M1:scope:lot-01")

        with self._session_factory.begin() as session:
            self._add_dce_version(
                session=session,
                tenant_id=tenant,
                actor_id=actor,
                consultation_id=consultation_id,
                dce_version_id=initial_dce_version_id,
                corpus_hash=_sha256("M1:DCE:v1"),
                source_received_at=started_at + timedelta(minutes=5),
                predecessor_dce_version_id=None,
                provenance_channel="BUYER_PLATFORM",
                storage_key="m1/dce-v1/rc.pdf",
            )
            self._add_case(
                session=session,
                tenant_id=tenant,
                actor_id=actor,
                consultation_id=consultation_id,
                dce_version_id=initial_dce_version_id,
                case_id=case_id,
                scope_fingerprint=scope_fingerprint,
                set_at=started_at + timedelta(minutes=10),
            )
            self._add_finalized_go_decision(
                session=session,
                tenant_id=tenant,
                actor_id=actor,
                case_id=case_id,
                dce_version_id=initial_dce_version_id,
                decision_id=decision_id,
                decision_context_id=decision_context_id,
                scope_fingerprint=scope_fingerprint,
                finalized_at=started_at + timedelta(minutes=20),
            )
            self._add_dce_version(
                session=session,
                tenant_id=tenant,
                actor_id=actor,
                consultation_id=consultation_id,
                dce_version_id=rectification_dce_version_id,
                corpus_hash=_sha256("M1:DCE:v2:rectification"),
                source_received_at=started_at + timedelta(minutes=30),
                predecessor_dce_version_id=initial_dce_version_id,
                provenance_channel="RECTIFICATION",
                storage_key="m1/dce-v2/rectificatif-rc.pdf",
            )
            session.flush()

            initial_dce = session.get(DceVersionRecord, initial_dce_version_id)
            case = session.get(CaseRecord, case_id)
            decision = session.get(DecisionRecord, decision_id)
            assert initial_dce is not None and case is not None and decision is not None

            initial_dce.lifecycle = "SUPERSEDED"
            initial_dce.analysis_readiness = "REVIEW_REQUIRED"
            initial_dce.superseded_at = started_at + timedelta(minutes=30)
            initial_dce.aggregate_revision = 1

            case.dce_freshness = "REVIEW_REQUIRED"
            case.aggregate_revision += 1
            case.updated_by_actor_id = actor

            decision.validity = "REVIEW_REQUIRED"
            decision.context_status = "STALE"
            decision.review_required_reason = "Rectificatif DCE v2 reçu après la décision Go."
            decision.review_required_at = started_at + timedelta(minutes=30)
            decision.aggregate_revision += 1
            decision.updated_by_actor_id = actor

        return M1ScenarioResult(
            consultation_id=consultation_id,
            initial_dce_version_id=initial_dce_version_id,
            rectification_dce_version_id=rectification_dce_version_id,
            case_id=case_id,
            decision_id=decision_id,
            decision_context_id=decision_context_id,
        )

    def _create_consultation(
        self,
        *,
        tenant_id: UUID,
        actor_id: UUID,
        consultation_id: UUID,
        received_at: datetime,
    ) -> None:
        dispatcher = CommandDispatcher(
            session_factory=self._session_factory,
            handlers={"CreateConsultation": CreateConsultationHandler()},
        )
        dispatcher.dispatch(
            command=CreateConsultationCommand(
                command_id=uuid4(),
                idempotency_key=uuid4(),
                correlation_id=uuid4(),
                consultation_id=consultation_id,
                buyer_legal_name="Ville de démonstration",
                buyer_normalized_id="VILLE-DEMO",
                external_reference="M1-2026-001",
                object_label="Réhabilitation de l’école municipale",
                location_label="Lille",
                source_channel="BUYER_PLATFORM",
                source_reference="PLACE-ACHETEUR",
                source_received_at=received_at,
            ),
            context=CommandContext(
                tenant_id=tenant_id,
                actor_id=actor_id,
                actor_kind="PATRON",
                received_at=received_at,
            ),
        )

    @staticmethod
    def _add_dce_version(
        *,
        session: Session,
        tenant_id: UUID,
        actor_id: UUID,
        consultation_id: UUID,
        dce_version_id: UUID,
        corpus_hash: str,
        source_received_at: datetime,
        predecessor_dce_version_id: UUID | None,
        provenance_channel: str,
        storage_key: str,
    ) -> None:
        session.add(
            DceVersionRecord(
                id=dce_version_id,
                tenant_id=tenant_id,
                aggregate_revision=0,
                consultation_id=consultation_id,
                corpus_hash=corpus_hash,
                predecessor_dce_version_id=predecessor_dce_version_id,
                provenance_channel=provenance_channel,
                provenance_reference="M1 démonstration",
                provenance_url=None,
                source_received_at=source_received_at,
                lifecycle="ADMITTED",
                integrity="VERIFIED",
                classification_readiness="UNCLASSIFIED",
                analysis_readiness="NOT_READY",
                withdrawal_source=None,
                withdrawal_reason=None,
                superseded_at=None,
                withdrawn_at=None,
                created_by_actor_id=actor_id,
                updated_by_actor_id=actor_id,
            )
        )
        session.flush()
        session.add(
            DceDocumentRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                dce_version_id=dce_version_id,
                storage_object_id=uuid4(),
                storage_key=storage_key,
                original_filename="reglement_consultation.pdf",
                media_type="application/pdf",
                byte_size=512,
                sha256=_sha256(storage_key),
                received_from=provenance_channel,
            )
        )

    @staticmethod
    def _add_case(
        *,
        session: Session,
        tenant_id: UUID,
        actor_id: UUID,
        consultation_id: UUID,
        dce_version_id: UUID,
        case_id: UUID,
        scope_fingerprint: str,
        set_at: datetime,
    ) -> None:
        session.add(
            CaseRecord(
                id=case_id,
                tenant_id=tenant_id,
                aggregate_revision=2,
                functional_identity_hash=_sha256(f"M1:case:{consultation_id}:{scope_fingerprint}"),
                title="Lot 01 — gros œuvre",
                object_description="Affaire M1 de démonstration.",
                business_origin="IMPORT",
                origin_reference_id=None,
                origin_rationale=None,
                consultation_id=consultation_id,
                scope_kind="SINGLE_LOT",
                scope_json={"lot_numbers": ["01"]},
                scope_fingerprint=scope_fingerprint,
                applicable_dce_version_id=dce_version_id,
                lifecycle="ACTIVE",
                commercial_stage="AWAITING_DECISION",
                decision_readiness="READY",
                dce_freshness="CURRENT",
                responsibility_status="UNASSIGNED",
                stopped_reason=None,
                stopped_at=None,
                archived_reason=None,
                archived_at=None,
                created_by_actor_id=actor_id,
                updated_by_actor_id=actor_id,
            )
        )
        session.flush()
        session.add(
            CaseConsultationLinkRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                case_id=case_id,
                consultation_id=consultation_id,
                scope_snapshot_json={"kind": "SINGLE_LOT", "lot_numbers": ["01"]},
                rationale="Lot source retenu pour l’affaire.",
                is_current=True,
                created_by_actor_id=actor_id,
            )
        )
        session.add(
            CaseDceApplicabilityHistoryRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                case_id=case_id,
                dce_version_id=dce_version_id,
                reason="Corpus DCE v1 retenu lors de l’ouverture de l’affaire.",
                is_current=True,
                set_by_actor_id=actor_id,
                set_at=set_at,
            )
        )

    @staticmethod
    def _add_finalized_go_decision(
        *,
        session: Session,
        tenant_id: UUID,
        actor_id: UUID,
        case_id: UUID,
        dce_version_id: UUID,
        decision_id: UUID,
        decision_context_id: UUID,
        scope_fingerprint: str,
        finalized_at: datetime,
    ) -> None:
        decision = DecisionRecord(
            id=decision_id,
            tenant_id=tenant_id,
            aggregate_revision=0,
            decision_type="GO_NO_GO",
            subject_type="CASE",
            subject_id=case_id,
            case_id=case_id,
            scope_fingerprint=scope_fingerprint,
            decision_key_hash=_sha256(f"M1:decision:{case_id}:{scope_fingerprint}"),
            cycle_number=1,
            lifecycle="DRAFT",
            outcome="UNDECIDED",
            validity="CURRENT",
            condition_status="NOT_APPLICABLE",
            context_status="INCOMPLETE",
            selected_final_context_id=None,
            successor_decision_id=None,
            final_justification=None,
            finalized_by_actor_id=None,
            finalized_at=None,
            review_required_reason=None,
            review_required_at=None,
            cancel_reason=None,
            cancelled_at=None,
            created_by_actor_id=actor_id,
            updated_by_actor_id=actor_id,
        )
        session.add(decision)
        session.flush()

        context_fingerprint = _sha256(f"M1:context:{case_id}:{dce_version_id}")
        session.add(
            DecisionContextRecord(
                id=decision_context_id,
                tenant_id=tenant_id,
                decision_id=decision_id,
                sequence_number=1,
                context_fingerprint=context_fingerprint,
                canonical_context_json={
                    "case_id": str(case_id),
                    "dce_version_id": str(dce_version_id),
                    "scope_fingerprint": scope_fingerprint,
                },
                rationale="Périmètre et DCE v1 contrôlés par le patron.",
                unknowns_json=[],
                prepared_at=finalized_at - timedelta(minutes=5),
                context_state="FROZEN",
                is_selected_final=True,
                prepared_by_actor_id=actor_id,
            )
        )
        session.add(
            DecisionContextReferenceRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                decision_context_id=decision_context_id,
                aggregate_type="CASE",
                aggregate_id=case_id,
                aggregate_revision=2,
                content_hash=None,
                reference_role="SUBJECT",
            )
        )
        session.add(
            DecisionContextReferenceRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                decision_context_id=decision_context_id,
                aggregate_type="DCE_VERSION",
                aggregate_id=dce_version_id,
                aggregate_revision=0,
                content_hash=_sha256("M1:DCE:v1"),
                reference_role="APPLICABLE_DCE",
            )
        )
        session.flush()

        decision.aggregate_revision = 2
        decision.lifecycle = "FINALIZED"
        decision.outcome = "GO"
        decision.validity = "CURRENT"
        decision.context_status = "FROZEN"
        decision.selected_final_context_id = decision_context_id
        decision.final_justification = "Dossier compatible avec le périmètre retenu."
        decision.finalized_by_actor_id = actor_id
        decision.finalized_at = finalized_at


def _sha256(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()
