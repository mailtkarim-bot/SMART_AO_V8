"""Deterministic technical-document content assembly."""

from __future__ import annotations

from dataclasses import dataclass
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
