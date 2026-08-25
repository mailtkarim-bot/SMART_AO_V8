import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { CaseDceReading, KnowledgeSearchResult } from "../../shared/types";
import { DceKnowledgePanel } from "./DceKnowledgePanel";

const reading: CaseDceReading = {
  case_id: "case-1",
  work_label: "Réhabilitation du groupe scolaire",
  case_lifecycle: "PREPARATION",
  commercial_stage: "QUALIFICATION",
  dce_freshness: "CURRENT",
  availability: "AVAILABLE",
  dce: {
    dce_version_id: "dce-1",
    lifecycle: "ADMITTED",
    integrity: "VERIFIED",
    classification_readiness: "READY",
    analysis_readiness: "READY",
    source_received_at: "2026-08-20T12:00:00Z",
  },
  counters: {
    total: 2,
    pending_human_confirmation: 1,
    confirmed: 1,
    review_required: 0,
    not_applicable: 0,
  },
  requirements: [
    {
      requirement_id: "requirement-1",
      requirement_type: "DELAI_EXECUTION",
      directive_signal: "EXPLICIT",
      confirmation_outcome: "PENDING",
      uncertainty_status: "TO_CONFIRM",
      document_family: "CCTP",
      source_locator_label: "CCTP · page 12",
    },
  ],
};

const result: KnowledgeSearchResult = {
  source_fragment_id: "fragment-1",
  dce_version_id: "dce-1",
  score: 0.91,
  locator: { label: "CCTP · page 12" },
  embedding_model: "TEST_PROVIDER",
};

function renderPanel(overrides: Partial<React.ComponentProps<typeof DceKnowledgePanel>> = {}) {
  return render(
    <DceKnowledgePanel
      selectedCaseId="case-1"
      reading={null}
      results={[]}
      query=""
      loading={false}
      searching={false}
      onQueryChange={vi.fn()}
      onLoad={vi.fn()}
      onSearch={vi.fn()}
      onResetSearch={vi.fn()}
      {...overrides}
    />,
  );
}

describe("DceKnowledgePanel", () => {
  it("asks for a case before exposing DCE data", () => {
    renderPanel({ selectedCaseId: "" });
    expect(screen.getByText("Sélectionnez une affaire")).toBeInTheDocument();
    expect(screen.queryByText("Réhabilitation du groupe scolaire")).not.toBeInTheDocument();
  });

  it("renders DCE counters, requirements and sourced results", () => {
    renderPanel({ reading, results: [result], query: "délai" });

    expect(screen.getByText("Réhabilitation du groupe scolaire")).toBeInTheDocument();
    expect(screen.getByText("DELAI_EXECUTION")).toBeInTheDocument();
    expect(screen.getByText("CCTP · page 12")).toBeInTheDocument();
    expect(screen.getByText("91%")).toBeInTheDocument();
    expect(screen.queryByText("texte intégral secret")).not.toBeInTheDocument();
  });

  it("delegates query, search, reset and reload actions", () => {
    const onQueryChange = vi.fn();
    const onLoad = vi.fn();
    const onSearch = vi.fn();
    const onResetSearch = vi.fn();
    renderPanel({
      reading,
      query: "délai",
      results: [result],
      onQueryChange,
      onLoad,
      onSearch,
      onResetSearch,
    });

    fireEvent.change(screen.getByRole("textbox", { name: "Question ou terme" }), { target: { value: "garantie" } });
    fireEvent.click(screen.getByRole("button", { name: "Actualiser la lecture" }));
    fireEvent.click(screen.getByRole("button", { name: /Rechercher/ }));
    fireEvent.click(screen.getByRole("button", { name: "Effacer" }));

    expect(onQueryChange).toHaveBeenCalledWith("garantie");
    expect(onLoad).toHaveBeenCalledOnce();
    expect(onSearch).toHaveBeenCalledOnce();
    expect(onResetSearch).toHaveBeenCalledOnce();
  });
});
