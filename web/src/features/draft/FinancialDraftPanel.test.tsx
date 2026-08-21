import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AssignedCase, DraftReport } from "../../shared/types";
import type { FinancialLineForm } from "./useFinancialDraft";
import { FinancialDraftPanel } from "./FinancialDraftPanel";

const cases: AssignedCase[] = [
  {
    case_id: "case-1",
    work_label: "Réhabilitation du groupe scolaire",
    case_lifecycle: "ACTIVE",
    commercial_stage: "REVIEW",
    dce_availability: "READY",
  },
];

const draft: DraftReport = {
  report_id: "report-1",
  case_id: "case-1",
  status: "DRAFT",
  aggregate_revision: 2,
  currency_code: "EUR",
  calculated_at: "2026-08-20T12:00:00Z",
  ruleset_version: 1,
  summary: {
    sales_total_minor: 250000,
    direct_cost_total_minor: 100000,
    overhead_total_minor: 25000,
    subcontracting_total_minor: 0,
    contingency_total_minor: 0,
    gross_margin_minor: 125000,
    gross_margin_rate_bps: 5000,
    forecast_cashflow_minor: 125000,
  },
  lines: [
    {
      line_id: "line-1",
      category: "SALES",
      label: "Étude technique",
      quantity_decimal: "2",
      unit: "jour",
      amount_minor: 250000,
      currency_code: "EUR",
    },
  ],
};

const lineForm: FinancialLineForm = {
  category: "SALES",
  label: "",
  quantity_decimal: "1",
  unit: "forfait",
  amount_minor: "",
};

function renderPanel(
  overrides: Partial<React.ComponentProps<typeof FinancialDraftPanel>> = {},
) {
  const props: React.ComponentProps<typeof FinancialDraftPanel> = {
    cases,
    selectedCaseId: "case-1",
    setSelectedCaseId: vi.fn(),
    reportId: "report-1",
    setReportId: vi.fn(),
    draft: null,
    loadingDraft: false,
    lineForm,
    setLineForm: vi.fn(),
    summaryCards: [
      { label: "Ventes", value: "2 500 €", accent: "blue" },
      { label: "Marge brute", value: "1 250 €", accent: "green" },
    ],
    createDraft: vi.fn(),
    loadDraft: vi.fn(),
    submitLine: vi.fn(),
    formatMoney: (minor, currency) => `${minor} ${currency}`,
    formatDate: () => "20 août 2026",
    categoryLabel: (category) => (category === "SALES" ? "Ventes" : category),
    ...overrides,
  };
  return render(<FinancialDraftPanel {...props} />);
}

describe("FinancialDraftPanel", () => {
  it("shows the controlled empty state and delegates draft commands", () => {
    const createDraft = vi.fn();
    const loadDraft = vi.fn();
    renderPanel({ createDraft, loadDraft });

    expect(screen.getByText("Sélectionnez un brouillon pour commencer.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Nouveau brouillon/ }));
    fireEvent.click(screen.getByRole("button", { name: /Lire le brouillon/ }));
    expect(createDraft).toHaveBeenCalledTimes(1);
    expect(loadDraft).toHaveBeenCalledTimes(1);
  });

  it("renders financial amounts only inside the patron draft projection", () => {
    renderPanel({ draft });

    expect(screen.getByText("Étude technique")).toBeInTheDocument();
    expect(screen.getByText("250000 EUR")).toBeInTheDocument();
    expect(screen.getByText("Les montants restent visibles uniquement dans cet espace patron.")).toBeInTheDocument();
    expect(screen.getByText("DRAFT · Révision 2")).toBeInTheDocument();
  });

  it("submits the line form through the hook boundary", () => {
    const submitLine = vi.fn((event: React.FormEvent<HTMLFormElement>) => event.preventDefault());
    renderPanel({ draft, submitLine });

    fireEvent.submit(screen.getByRole("button", { name: /Ajouter/ }).closest("form")!);

    expect(submitLine).toHaveBeenCalledTimes(1);
  });
});
