import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type {
  DecisionPricingReconciliationItem,
  DecisionRiskRequirementLink,
} from "../../shared/types";
import { DecisionRiskRequirementsPanel } from "./DecisionRiskRequirementsPanel";

const link: DecisionRiskRequirementLink = {
  link_id: "link-1",
  case_id: "case-1",
  risk_id: "risk-12345678",
  requirement_id: "requirement-12345678",
  dce_version_id: "dce-12345678",
  relationship: "REQUIRES_MITIGATION",
  rationale: "La confirmation humaine relie le risque à l’exigence.",
  source_refs: ["fragment-1"],
  created_at: "2026-08-26T10:00:00Z",
  action_id: "action-1",
  action_state: "OPEN",
  action_severity: "BLOCKING",
  action_revision: 2,
};

const item: DecisionPricingReconciliationItem = {
  link_id: "link-1",
  batch_id: "batch-1",
  document_kind: "DPGF",
  batch_state: "COMMITTED",
  row_number: 12,
  code: "LOT-12",
  designation: "Protection collective",
  unit: "u",
  match_basis: "CODE_OR_DESIGNATION",
  verification_status: "COMMITTED_NORMALIZED_IMPORT",
};

function renderPanel(overrides: Partial<React.ComponentProps<typeof DecisionRiskRequirementsPanel>> = {}) {
  return render(
    <DecisionRiskRequirementsPanel
      caseId="case-1"
      links={[link]}
      nextCursor={null}
      selectedLinkId="link-1"
      pricingItems={[]}
      search=""
      loading={false}
      searching={false}
      formatDate={() => "26 août 2026 10:00"}
      onRefresh={vi.fn()}
      onLoadMore={vi.fn()}
      onSelectLink={vi.fn()}
      onSearchChange={vi.fn()}
      onReconcilePricing={vi.fn()}
      {...overrides}
    />,
  );
}

describe("DecisionRiskRequirementsPanel", () => {
  it("renders verified link metadata without financial values", () => {
    renderPanel();

    expect(screen.getByText("Risques, exigences et lots candidats")).toBeInTheDocument();
    expect(screen.getAllByText("REQUIRES_MITIGATION")).toHaveLength(2);
    expect(screen.getByText(/Action : OPEN · BLOCKING/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/montant|marge|prix/i);
  });

  it("selects a link and submits a bounded reconciliation search", () => {
    const onSelectLink = vi.fn();
    const onSearchChange = vi.fn();
    const onReconcilePricing = vi.fn();
    renderPanel({ onSelectLink, onSearchChange, onReconcilePricing });

    fireEvent.click(screen.getByRole("button", { name: /REQUIRES_MITIGATION/ }));
    fireEvent.change(screen.getByRole("textbox", { name: "Recherche DPGF ou BPU" }), {
      target: { value: "protection" },
    });
    fireEvent.submit(screen.getByRole("textbox", { name: "Recherche DPGF ou BPU" }).closest("form")!);

    expect(onSelectLink).toHaveBeenCalledWith("link-1");
    expect(onSearchChange).toHaveBeenCalledWith("protection");
    expect(onReconcilePricing).toHaveBeenCalledOnce();
  });

  it("renders server-provided candidates without quantities or prices", () => {
    renderPanel({ pricingItems: [item] });

    expect(screen.getByText("DPGF · ligne 12")).toBeInTheDocument();
    expect(screen.getByText(/LOT-12 · Protection collective/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/unit_price|total_minor|quantity_decimal/i);
  });
});
