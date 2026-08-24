import type { ComponentProps } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { PricingImportBatchRead, PricingScenario } from "../../shared/types";
import { PricingPanel } from "./PricingPanel";

type PanelProps = ComponentProps<typeof PricingPanel>;

const preview: PricingImportBatchRead = {
  batch_id: "batch-1",
  case_id: "case-1",
  document_kind: "BPU",
  state: "PREVIEWED",
  aggregate_revision: 1,
  row_count: 1,
  valid_row_count: 1,
  error_count: 0,
  total_minor: 1500,
  rows: [
    {
      row_number: 2,
      code: "A-01",
      designation: "Terrassement",
      unit: "m2",
      quantity_decimal: "1",
      unit_price_minor: 1500,
      total_minor: 1500,
      errors: [],
    },
  ],
};

const scenario: PricingScenario = {
  scenario_id: "scenario-1",
  case_id: "case-1",
  scenario_key: "BASELINE",
  scenario_type: "BASELINE",
  version: 2,
  state: "SELECTED",
  assumptions: {},
  sales_total_minor: 100000,
  total_cost_minor: 70000,
  gross_margin_minor: 30000,
  gross_margin_rate_bps: 3000,
  source_snapshot_revision: 4,
};

function renderPanel(overrides: Partial<PanelProps> = {}) {
  const props: PanelProps = {
    scenarios: [],
    formatMoney: (minor) => `${minor} EUR`,
    selectedCaseId: "case-1",
    reportId: "report-1",
    pricingImportBatchId: "batch-1",
    pricingImportBatchRevision: "1",
    pricingImportReportRevision: "0",
    pricingImportState: "IDLE",
    pricingImportPreview: null,
    pricingImportReloadState: "NOT_ATTEMPTED",
    pricingImportUploading: false,
    pricingImportLoading: false,
    pricingImportSubmitting: false,
    setPricingImportBatchId: vi.fn(),
    setPricingImportBatchRevision: vi.fn(),
    setPricingImportReportRevision: vi.fn(),
    onPreview: vi.fn(),
    onReload: vi.fn(),
    onCommit: vi.fn(),
    ...overrides,
  };
  return { ...render(<PricingPanel {...props} />), props };
}

describe("PricingPanel integration", () => {
  it("renders private scenarios and commits from the patron panel", () => {
    const onCommit = vi.fn();
    renderPanel({ scenarios: [scenario], onCommit });

    expect(screen.getByText("BASELINE · v2")).toBeInTheDocument();
    expect(screen.getByText("30000 EUR")).toBeInTheDocument();
    expect(screen.getByText("Marge 30.0 % · SELECTED")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /commiter les lignes validées/i }));
    expect(onCommit).toHaveBeenCalledOnce();
  });

  it.each([
    ["selectedCaseId", { selectedCaseId: "" }],
    ["reportId", { reportId: "" }],
    ["batch", { pricingImportBatchId: "" }],
    ["submitting", { pricingImportSubmitting: true }],
  ])("disables commit when %s is unavailable", (_reason, override) => {
    renderPanel(override);

    const button = screen.getByRole("button", { name: /commiter les lignes validées|commit en cours/i });
    expect(button).toBeDisabled();
  });

  it("renders the persisted preview and exposes patron reload/upload actions", () => {
    const onPreview = vi.fn();
    const onReload = vi.fn();
    renderPanel({ pricingImportPreview: preview, onPreview, onReload });

    expect(screen.getByText(/BPU · PREVIEWED/)).toBeInTheDocument();
    expect(screen.getByText(/#2 · Terrassement/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /relire le batch/i }));
    expect(onReload).toHaveBeenCalledOnce();
    fireEvent.change(screen.getByLabelText(/fichier dpgf/i), {
      target: { files: [new File(["xlsx"], "pricing.xlsx")] },
    });
    expect(onPreview).toHaveBeenCalledOnce();
  });

  it("shows a processing label while the hook is submitting", () => {
    renderPanel({ pricingImportSubmitting: true });

    expect(screen.getByRole("button", { name: /commit en cours/i })).toBeDisabled();
  });

  it("keeps a confirmed commit visible when the reload failed", () => {
    renderPanel({ pricingImportState: "COMMITTED", pricingImportReloadState: "FAILED" });

    expect(screen.getByText("COMMITTED")).toBeInTheDocument();
    expect(screen.getByText("Commit confirmé. Rechargez le brouillon pour resynchroniser l’affichage.")).toBeInTheDocument();
  });
});
