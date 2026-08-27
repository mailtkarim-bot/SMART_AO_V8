import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { DceContractRiskSignal } from "../../shared/types";
import { DceContractRiskSignalsPanel } from "./DceContractRiskSignalsPanel";

const signal: DceContractRiskSignal = {
  observation_id: "observation-1",
  dce_version_id: "dce-1",
  document_family: "CCAP",
  requirement_kind: "CCAP_PENALTIES",
  rule_id: "CCAP_DELAY_PENALTIES_V1",
  rule_version: "RC_ANALYZER_V1",
  directive: "REQUIRED_SIGNAL",
  fragment_id: "fragment-1",
  source_locator_label: "CCAP · page 8",
  start_byte_offset: 120,
  end_byte_offset: 145,
  verification_status: "REVIEW_REQUIRED",
};

function renderPanel(
  overrides: Partial<React.ComponentProps<typeof DceContractRiskSignalsPanel>> = {},
) {
  return render(
    <DceContractRiskSignalsPanel
      caseId="case-1"
      signals={[signal]}
      loading={false}
      registeringObservationId={null}
      canManage
      onRefresh={vi.fn()}
      onRegister={vi.fn()}
      {...overrides}
    />,
  );
}

describe("DceContractRiskSignalsPanel", () => {
  it("renders the detected signal and its provenance metadata", () => {
    renderPanel();

    expect(screen.getByText("Transformer les signaux en risques suivis")).toBeInTheDocument();
    expect(screen.getByText("CCAP_PENALTIES")).toBeInTheDocument();
    expect(screen.getByText(/CCAP · page 8/)).toBeInTheDocument();
    expect(screen.getByText(/règle RC_ANALYZER_V1/)).toBeInTheDocument();
    expect(screen.getByText("REQUIRED_SIGNAL")).toBeInTheDocument();
  });

  it("requires a human statement and source excerpt before registering", () => {
    const onRegister = vi.fn();
    renderPanel({ onRegister });

    fireEvent.submit(screen.getByLabelText("Formulation du risque").closest("form")!);

    expect(screen.getByRole("alert")).toHaveTextContent("obligatoires");
    expect(onRegister).not.toHaveBeenCalled();
  });

  it("submits a structured risk with signal provenance and bounded fields", () => {
    const onRegister = vi.fn();
    renderPanel({ onRegister });

    fireEvent.change(screen.getByLabelText("Formulation du risque"), {
      target: { value: "Le marché prévoit une pénalité en cas de retard." },
    });
    fireEvent.change(screen.getByLabelText("Extrait de preuve source"), {
      target: { value: "Des pénalités de retard seront appliquées." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer le risque" }));

    expect(onRegister).toHaveBeenCalledWith(signal, expect.objectContaining({
      dce_version_id: "dce-1",
      source_fragment_id: "fragment-1",
      category: "CCAP",
      risk_code: "CCAP_PENALTIES",
      severity: "HIGH",
      likelihood: "POSSIBLE",
      source_excerpt: "Des pénalités de retard seront appliquées.",
      start_byte_offset: 120,
      end_byte_offset: 145,
    }));
  });

  it("does not expose promotion controls to read-only users", () => {
    renderPanel({ canManage: false });

    expect(screen.getByText(/promotion en risque structuré est réservée/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Enregistrer le risque" })).not.toBeInTheDocument();
  });
});
