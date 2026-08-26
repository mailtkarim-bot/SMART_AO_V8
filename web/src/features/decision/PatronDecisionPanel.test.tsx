import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { PatronDecisionDossier } from "../../shared/types";
import { PatronDecisionPanel } from "./PatronDecisionPanel";

const decisionDossier: PatronDecisionDossier = {
  decision_id: "decision-1",
  aggregate_revision: 1,
  case_id: "case-1",
  decision_type: "GO_CONDITIONNEL",
  lifecycle: "FINALIZED",
  outcome: "GO_CONDITIONAL",
  validity: "VALID",
  context_status: "CURRENT",
  final_justification: "Les conditions opérationnelles restent à suivre.",
  known: [],
  unknowns: [{ code: "MISSING_REFERENCE", label: "Référence à confirmer" }],
  risks: [{ code: "DEADLINE", label: "Échéance à surveiller" }],
  conditions: [
    {
      condition_id: "condition-1",
      label: "Confirmer la référence chantier",
      status: "OPEN",
      due_at: "2026-09-01T00:00:00Z",
      failure_consequence: "Revue patronale requise",
    },
  ],
  sources: [
    {
      aggregate_type: "PreparationPackage",
      aggregate_id: "package-1",
      aggregate_revision: 4,
      role: "TECHNICAL_PREPARATION",
    },
  ],
  context_fingerprint: null,
};

const frozenDecisionDossier: PatronDecisionDossier = {
  ...decisionDossier,
  lifecycle: "PENDING_PATRON",
  outcome: "UNDECIDED",
  context_status: "FROZEN",
  final_justification: null,
  context_fingerprint: "b".repeat(64),
  conditions: [],
};

describe("PatronDecisionPanel", () => {
  it("renders the controlled empty state", () => {
    render(<PatronDecisionPanel decisionDossier={null} formatDate={() => ""} />);

    expect(screen.getByText("Aucun dossier de décision disponible")).toBeInTheDocument();
    expect(screen.getByText(/contexte, les inconnus, les risques/)).toBeInTheDocument();
  });

  it("renders bounded decision facts, conditions and sources", () => {
    render(<PatronDecisionPanel decisionDossier={decisionDossier} formatDate={() => "1 sept. 2026"} />);

    expect(screen.getByText("GO_CONDITIONNEL")).toBeInTheDocument();
    expect(screen.getByText("Les conditions opérationnelles restent à suivre.")).toBeInTheDocument();
    expect(screen.getByText(/MISSING_REFERENCE/)).toBeInTheDocument();
    expect(screen.getByText(/DEADLINE/)).toBeInTheDocument();
    expect(screen.getByText("Confirmer la référence chantier")).toBeInTheDocument();
    expect(screen.getByText(/Échéance 1 sept\. 2026/)).toBeInTheDocument();
    expect(screen.getByText("PreparationPackage")).toBeInTheDocument();
    expect(screen.queryByText(/montant|marge|prix/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Finaliser et enregistrer" })).not.toBeInTheDocument();
  });

  it("submits the server fingerprint for a frozen patron decision", () => {
    const onFinalize = vi.fn();
    render(
      <PatronDecisionPanel
        decisionDossier={frozenDecisionDossier}
        formatDate={() => ""}
        canManage
        onFinalize={onFinalize}
      />,
    );

    fireEvent.change(screen.getByLabelText("Issue"), { target: { value: "NO_GO" } });
    fireEvent.change(screen.getByLabelText("Justification finale"), {
      target: { value: "Décision motivée après revue patronale." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Finaliser et enregistrer" }));

    expect(onFinalize).toHaveBeenCalledWith({
      expected_revision: 1,
      displayed_fingerprint: "b".repeat(64),
      outcome: "NO_GO",
      justification: "Décision motivée après revue patronale.",
      conditions: [],
    });
  });
});
