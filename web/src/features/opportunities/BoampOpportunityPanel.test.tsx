import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { BoampObservation, BoampQualificationForm } from "../../shared/types";
import { BoampOpportunityPanel } from "./BoampOpportunityPanel";

const observation: BoampObservation = {
  observation_id: "observation-1",
  source_notice_id: "BOAMP-1",
  title: "Réhabilitation d’une école",
  publication_date: "2026-08-20",
  response_deadline: "2026-09-15T12:00:00Z",
  department_codes: ["59"],
  market_types: ["TRAVAUX"],
  source_status: "EN_COURS",
  score_version: "BOAMP_PUBLIC_V1",
  score: 82,
  score_explanation: {},
  fingerprint_sha256: "a".repeat(64),
};

const form: BoampQualificationForm = {
  decision: "QUALIFIED",
  reason_code: "RELEVANT_PUBLIC_SIGNAL",
};

function renderPanel(overrides: Partial<React.ComponentProps<typeof BoampOpportunityPanel>> = {}) {
  return render(
    <BoampOpportunityPanel
      observations={[]}
      selectedObservationId=""
      qualificationForm={form}
      loading={false}
      qualifying={false}
      onRefresh={vi.fn()}
      onSelect={vi.fn()}
      onDecisionChange={vi.fn()}
      onReasonChange={vi.fn()}
      onQualify={vi.fn()}
      {...overrides}
    />,
  );
}

describe("BoampOpportunityPanel", () => {
  it("renders a tenant-scoped empty state", () => {
    renderPanel();
    expect(screen.getByText("Aucune opportunité BOAMP disponible")).toBeInTheDocument();
    expect(screen.getByText(/Aucune donnée financière/)).toBeInTheDocument();
  });

  it("renders the selected public projection and delegates actions", () => {
    const onSelect = vi.fn();
    const onQualify = vi.fn();
    renderPanel({
      observations: [observation],
      selectedObservationId: observation.observation_id,
      onSelect,
      onQualify,
    });

    expect(screen.getAllByText("Réhabilitation d’une école")).toHaveLength(2);
    expect(screen.getByText("BOAMP-1")).toBeInTheDocument();
    expect(screen.getByText("82")).toBeInTheDocument();
    expect(screen.queryByText("a".repeat(64))).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Réhabilitation d’une école/ }));
    fireEvent.click(screen.getByRole("button", { name: /Enregistrer la qualification/ }));
    expect(onSelect).toHaveBeenCalledWith("observation-1");
    expect(onQualify).toHaveBeenCalledOnce();
  });

  it("delegates refresh and selection changes", () => {
    const onRefresh = vi.fn();
    const onSelect = vi.fn();
    renderPanel({ observations: [observation], onRefresh, onSelect });

    fireEvent.click(screen.getByRole("button", { name: "Actualiser" }));
    fireEvent.click(screen.getByRole("button", { name: /Réhabilitation d’une école/ }));
    expect(onRefresh).toHaveBeenCalledOnce();
    expect(onSelect).toHaveBeenCalledWith("observation-1");
  });
});
