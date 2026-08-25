"""Deterministic technical-document content assembly."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from uuid import UUID

from app.modules.preparation.application.ports import PreparationRequirementInput


@dataclass(frozen=True, slots=True)
class TechnicalDocumentFacts:
    """Server-resolved facts allowed in a collaborator technical draft."""

    case_id: UUID
    dce_version_id: UUID
    readiness_state: str
    readiness_revision: int
    document_version: int
    requirements: tuple[PreparationRequirementInput, ...]
    blocker_codes: tuple[str, ...]
    warning_codes: tuple[str, ...]


def build_technical_document(facts: TechnicalDocumentFacts) -> str:
    """Build canonical Markdown without sources, secrets or financial facts."""

    lines = [
        "# Réponse technique — préparation contrôlée",
        "",
        "## Identification de la préparation",
        f"- Affaire : `{facts.case_id}`",
        f"- Version DCE : `{facts.dce_version_id}`",
        f"- État de complétude : `{facts.readiness_state}`",
        f"- Révision de complétude : `{facts.readiness_revision}`",
        f"- Version du document : `{facts.document_version}`",
        "",
        "## Exigences DCE confirmées",
    ]
    if facts.requirements:
        lines.extend(
            f"- `{item.requirement_id}` — {item.requirement_type} — "
            f"{item.directive_signal} — {item.confirmation_outcome or 'PENDING_HUMAN_CONFIRMATION'}"
            for item in facts.requirements
        )
    else:
        lines.append("- Aucune exigence matérialisée dans le périmètre courant.")
    lines.extend(
        [
            "",
            "## Contrôle de complétude",
            "- Blocages : " + (", ".join(facts.blocker_codes) or "aucun"),
            "- Avertissements : " + (", ".join(facts.warning_codes) or "aucun"),
            "",
            "Ce document est un brouillon technique versionné réservé au contrôle humain.",
        ]
    )
    return "\n".join(lines) + "\n"


class ControlledDocumentKind(StrEnum):
    DC1 = "DC1"
    DC2 = "DC2"
    DC4 = "DC4"


@dataclass(frozen=True, slots=True)
class EnterpriseDocumentFact:
    document_kind: str
    verification_status: str
    expires_at: date | None


@dataclass(frozen=True, slots=True)
class ControlledDocumentResult:
    kind: ControlledDocumentKind
    content: str
    blockers: tuple[str, ...]


def cross_match_enterprise_documents(
    *,
    required_kinds: tuple[str, ...],
    documents: tuple[EnterpriseDocumentFact, ...],
    as_of: date,
) -> tuple[str, ...]:
    """Return only missing/expired blockers; never infer legal validity."""
    blockers: list[str] = []
    for kind in required_kinds:
        matching = [document for document in documents if document.document_kind == kind]
        if not any(
            document.verification_status == "VALIDATED"
            and (document.expires_at is None or document.expires_at >= as_of)
            for document in matching
        ):
            blockers.append(f"ENTERPRISE_DOCUMENT_{kind}_NOT_VALIDATED")
    return tuple(blockers)


def build_controlled_btp_document(
    *,
    kind: ControlledDocumentKind,
    case_id: UUID,
    dce_version_id: UUID,
    document_version: int,
    facts: dict[str, str],
    blockers: tuple[str, ...],
) -> ControlledDocumentResult:
    """Build a non-binding Markdown envelope from server-provided facts only."""
    ordered_facts = sorted(facts.items())
    lines = [
        f"# {kind.value} — brouillon contrôlé",
        "",
        "> Document de préparation non contractuel. Validation humaine et "
        "signature externe obligatoires.",
        "",
        "## Traçabilité",
        f"- Affaire : `{case_id}`",
        f"- Version DCE : `{dce_version_id}`",
        f"- Version du document : `{document_version}`",
        "",
        "## Faits fournis par le serveur",
    ]
    lines.extend(f"- {key} : {value or '[À COMPLÉTER]'}" for key, value in ordered_facts)
    lines.extend(
        [
            "",
            "## Contrôles à effectuer",
            "- Blocages : " + (", ".join(blockers) or "aucun détecté"),
            "- Les champs absents, les échéances et la conformité juridique restent "
            "à confirmer par un opérateur habilité.",
        ]
    )
    return ControlledDocumentResult(kind=kind, content="\n".join(lines) + "\n", blockers=blockers)
