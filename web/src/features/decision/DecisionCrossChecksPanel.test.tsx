import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type {
  DecisionCctpPricingCrossingItem,
  DecisionDocumentContradictionItem,
} from "../../shared/types";
import { DecisionCrossChecksPanel } from "./DecisionCrossChecksPanel";

const crossing: DecisionCctpPricingCrossingItem = {
  dce_version_id: "dce-1",
  source_fragment_id: "fragment-1",
  source_locator_label: "CCTP · page 4",
  source_start_byte_offset: 10,
  source_end_byte_offset: 60,
  batch_id: "batch-1",
  document_kind: "DPGF",
  row_number: 12,
  code: "LOT-12",
  designation: "Protection collective",
  unit: "m2",
  match_score_bps: 8700,
  match_basis: "CODE_OR_DESIGNATION",
  verification_status: "REVIEW_REQUIRED",
};

const contradiction: DecisionDocumentContradictionItem = {
  contradiction_id: "contradiction-1",
  dce_version_id: "dce-1",
  contradiction_type: "PRICING_UNIT_MISMATCH",
  source_fragment_id: "fragment-1",
  source_locator_label: "CCTP · page 4",
  source_start_byte_offset: 10,
  source_end_byte_offset: 60,
  related_batch_id: "batch-1",
  related_document_kind: "BPU",
  related_row_number: 12,
  related_code: "LOT-12",
  related_designation: "Protection collective",
  related_unit: "u",
  comparison_basis: "CCTP_EXPLICIT_UNIT_V1",
  verification_status: "REVIEW_REQUIRED",
};

describe("DecisionCrossChecksPanel", () => {
  it("renders candidates and contradictions without monetary values", () => {
    render(
      <DecisionCrossChecksPanel
        caseId="case-1"
        crossings={[crossing]}
        contradictions={[contradiction]}
        loading={false}
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.getByText("Repérer les incohérences avant de décider")).toBeInTheDocument();
    expect(screen.getByText(/DPGF · ligne 12 · score 87 %/)).toBeInTheDocument();
    expect(screen.getByText("PRICING_UNIT_MISMATCH")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/unit_price_minor|total_minor|montant|marge/i);
  });

  it("shows the safe empty state", () => {
    render(
      <DecisionCrossChecksPanel
        caseId="case-1"
        crossings={[]}
        contradictions={[]}
        loading={false}
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.getByText("Aucune incohérence détectée")).toBeInTheDocument();
  });
});
