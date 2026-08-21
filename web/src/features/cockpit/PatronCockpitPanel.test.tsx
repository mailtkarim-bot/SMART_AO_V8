import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type {
  PatronAssignment,
  PatronAssignmentInteractions,
  PatronAssignmentJournalItem,
} from "../../shared/types";
import { PatronCockpitPanel } from "./PatronCockpitPanel";

const assignment: PatronAssignment = {
  assignment_id: "assignment-1",
  case_id: "case-1",
  case_title: "Réhabilitation du groupe scolaire",
  case_lifecycle: "ACTIVE",
  state: "ACTIVE",
  aggregate_revision: 6,
  starts_at: "2026-01-01T00:00:00Z",
  ends_at: null,
  ended_at: null,
  scope_actions: ["REVIEW", "DECIDE"],
  scope_classifications: ["INTERNAL_OPERATIONAL"],
};

const journal: PatronAssignmentJournalItem[] = [
  {
    record_id: "journal-1",
    event_type: "ASSIGNMENT_CREATED",
    recorded_at: "2026-08-20T10:00:00Z",
    reason_code: null,
    resulting_state: "ACTIVE",
    resulting_revision: 1,
  },
];

const interactions: PatronAssignmentInteractions = {
  assignment_id: "assignment-1",
  case_id: "case-1",
  case_lifecycle: "ACTIVE",
  items: [
    {
      record_id: "interaction-1",
      kind: "CLARIFICATION_REQUEST",
      recorded_at: "2026-08-20T12:00:00Z",
      operational_state: "OPEN",
      priority: "HIGH",
      reason_kind: null,
      clarification_kind: "MISSING_REFERENCE",
    },
  ],
};

function renderPanel(overrides: Partial<React.ComponentProps<typeof PatronCockpitPanel>> = {}) {
  return render(
    <PatronCockpitPanel
      assignments={[]}
      selectedAssignmentId=""
      journal={[]}
      interactions={null}
      onSelectAssignment={vi.fn()}
      {...overrides}
    />,
  );
}

describe("PatronCockpitPanel", () => {
  it("renders the tenant-scoped empty state without leaking data", () => {
    renderPanel();

    expect(screen.getByText("Aucune affectation patronale visible")).toBeInTheDocument();
    expect(screen.getByText(/projection est tenant-scopée/)).toBeInTheDocument();
    expect(screen.queryByText("Réhabilitation du groupe scolaire")).not.toBeInTheDocument();
  });

  it("renders assignment details from structured journal and interactions projections", () => {
    renderPanel({
      assignments: [assignment],
      selectedAssignmentId: "assignment-1",
      journal,
      interactions,
    });

    expect(screen.getByText("Réhabilitation du groupe scolaire")).toBeInTheDocument();
    expect(screen.getByText("ASSIGNMENT_CREATED")).toBeInTheDocument();
    expect(screen.getByText("CLARIFICATION_REQUEST")).toBeInTheDocument();
    expect(screen.getByText("HIGH")).toBeInTheDocument();
    expect(screen.getByText("2 actions")).toBeInTheDocument();
  });

  it("delegates assignment selection without exposing an API concern in the view", () => {
    const onSelectAssignment = vi.fn();
    renderPanel({ assignments: [assignment], onSelectAssignment });

    fireEvent.click(screen.getByRole("button", { name: /Réhabilitation du groupe scolaire/ }));

    expect(onSelectAssignment).toHaveBeenCalledWith(assignment);
  });
});
