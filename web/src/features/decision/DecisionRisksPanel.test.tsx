import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { StructuredRiskProjection } from "../../shared/types";
import { DecisionRisksPanel } from "./DecisionRisksPanel";

const risk: StructuredRiskProjection = {
  risk_id: "risk-12345678",
  case_id: "case-1",
  dce_version_id: "dce-1",
  risk_code: "PENALTY_DELAY",
  category: "CCAP",
  title: "Pénalités de retard",
  severity: "HIGH",
  likelihood: "LIKELY",
  treatment: "OPEN",
  revision: 1,
  due_at: null,
  latest_treatment_evidence: null,
};

function renderPanel(
  overrides: Partial<React.ComponentProps<typeof DecisionRisksPanel>> = {},
) {
  return render(
    <DecisionRisksPanel
      caseId="case-1"
      risks={[risk]}
      loading={false}
      transitioningRiskId={null}
      canManage
      onRefresh={vi.fn()}
      onTransition={vi.fn()}
      {...overrides}
    />,
  );
}

describe("DecisionRisksPanel", () => {
  it("renders risk metadata and bounded treatment fields", () => {
    renderPanel();

    expect(screen.getByText("Traiter les risques sur preuve")).toBeInTheDocument();
    expect(screen.getByText("PENALTY_DELAY · Pénalités de retard")).toBeInTheDocument();
    expect(screen.getByText("Élevé")).toBeInTheDocument();
    expect(screen.getByLabelText("Locator de preuve PENALTY_DELAY")).toHaveValue("{}");
  });

  it("rejects invalid evidence before dispatching", () => {
    const onTransition = vi.fn();
    renderPanel({ onTransition });

    fireEvent.change(screen.getByLabelText("Extrait de preuve"), {
      target: { value: "Extrait CCAP page 8" },
    });
    fireEvent.change(screen.getByLabelText("Justification"), {
      target: { value: "Risque accepté après revue patronale" },
    });
    fireEvent.change(screen.getByLabelText("Fin byte"), { target: { value: "0" } });
    fireEvent.submit(screen.getByLabelText("Justification").closest("form")!);

    expect(screen.getByRole("alert")).toHaveTextContent("strictement supérieure");
    expect(onTransition).not.toHaveBeenCalled();
  });

  it("submits an accepted treatment with parsed evidence", () => {
    const onTransition = vi.fn();
    renderPanel({ onTransition });

    fireEvent.change(screen.getByLabelText("Décision"), { target: { value: "ACCEPTED" } });
    fireEvent.change(screen.getByLabelText("Extrait de preuve"), {
      target: { value: "CCAP page 8" },
    });
    fireEvent.change(screen.getByLabelText("Locator de preuve PENALTY_DELAY"), {
      target: { value: '{"page":8}' },
    });
    fireEvent.change(screen.getByLabelText("Début byte"), { target: { value: "100" } });
    fireEvent.change(screen.getByLabelText("Fin byte"), { target: { value: "120" } });
    fireEvent.change(screen.getByLabelText("Justification"), {
      target: { value: "Accepté avec suivi patronal" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer le traitement" }));

    expect(onTransition).toHaveBeenCalledWith(risk, {
      to_treatment: "ACCEPTED",
      evidence_excerpt: "CCAP page 8",
      evidence_locator: { page: 8 },
      evidence_start_byte_offset: 100,
      evidence_end_byte_offset: 120,
      rationale: "Accepté avec suivi patronal",
    });
  });

  it("keeps an already treated risk read-only", () => {
    renderPanel({ risks: [{ ...risk, treatment: "MITIGATED" }] });

    expect(screen.getByText(/Traitement finalisé/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Justification")).not.toBeInTheDocument();
  });
});
