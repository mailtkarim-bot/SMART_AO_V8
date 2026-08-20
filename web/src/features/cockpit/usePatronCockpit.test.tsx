import type { Dispatch, SetStateAction } from "react";
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ApiClient } from "../../infrastructure/api";
import type {
  PatronAssignment,
  PatronAssignmentInteractions,
} from "../../shared/types";
import { usePatronCockpit } from "./usePatronCockpit";

type HookMessage = { tone: "success" | "error" | "warning"; text: string };
type CockpitApi = Pick<
  ApiClient,
  "listPatronAssignments" | "getAssignmentJournal" | "getAssignmentInteractions"
>;

const assignment = (id = "assignment-1", caseId = "case-1"): PatronAssignment => ({
  assignment_id: id,
  case_id: caseId,
  case_title: "Réhabilitation du groupe scolaire",
  case_lifecycle: "ACTIVE",
  state: "ACTIVE",
  aggregate_revision: 6,
  starts_at: "2026-01-01T00:00:00Z",
  ends_at: null,
  ended_at: null,
  scope_actions: ["REVIEW", "DECIDE"],
  scope_classifications: ["INTERNAL_OPERATIONAL"],
});

const interactions = (): PatronAssignmentInteractions => ({
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
});

function renderCockpitHook(
  api: CockpitApi,
  setMessage: Dispatch<SetStateAction<HookMessage | null>>,
  onCaseSelected: (caseId: string) => Promise<void> = vi.fn().mockResolvedValue(undefined),
) {
  return renderHook(() => usePatronCockpit(api as ApiClient, setMessage, onCaseSelected));
}

describe("usePatronCockpit", () => {
  it("loads assignments and hydrates the first assignment details", async () => {
    const api = {
      listPatronAssignments: vi.fn().mockResolvedValue({ items: [assignment()] }),
      getAssignmentJournal: vi.fn().mockResolvedValue({
        assignment: assignment(),
        items: [
          {
            record_id: "journal-1",
            event_type: "ASSIGNMENT_CREATED",
            resulting_state: "ACTIVE",
            resulting_revision: 1,
          },
        ],
      }),
      getAssignmentInteractions: vi.fn().mockResolvedValue(interactions()),
    } satisfies CockpitApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderCockpitHook(api, setMessage);

    await act(async () => {
      await result.current.refreshAssignments();
    });

    expect(result.current.assignments).toHaveLength(1);
    expect(result.current.selectedAssignmentId).toBe("assignment-1");
    expect(result.current.journal[0]?.event_type).toBe("ASSIGNMENT_CREATED");
    expect(result.current.interactions?.items[0]?.kind).toBe("CLARIFICATION_REQUEST");
  });

  it("loads journal and interactions in parallel and reports projection failures", async () => {
    const api = {
      listPatronAssignments: vi.fn(),
      getAssignmentJournal: vi.fn().mockRejectedValue(new Error("journal unavailable")),
      getAssignmentInteractions: vi.fn().mockResolvedValue(interactions()),
    } satisfies CockpitApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderCockpitHook(api, setMessage);

    await act(async () => {
      await result.current.loadAssignmentDetails("assignment-1");
    });

    expect(api.getAssignmentJournal).toHaveBeenCalledWith("assignment-1");
    expect(api.getAssignmentInteractions).toHaveBeenCalledWith("assignment-1");
    expect(result.current.journal).toEqual([]);
    expect(result.current.interactions).toBeNull();
    expect(setMessage).toHaveBeenCalledWith({
      tone: "error",
      text: "journal unavailable",
    });
  });

  it("selects an assignment and refreshes the related case context", async () => {
    const api = {
      listPatronAssignments: vi.fn(),
      getAssignmentJournal: vi.fn().mockResolvedValue({ assignment: assignment(), items: [] }),
      getAssignmentInteractions: vi.fn().mockResolvedValue(interactions()),
    } satisfies CockpitApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const onCaseSelected = vi.fn().mockResolvedValue(undefined);
    const { result } = renderCockpitHook(api, setMessage, onCaseSelected);

    await act(async () => {
      await result.current.selectAssignment(assignment("assignment-2", "case-2"));
    });

    expect(result.current.selectedAssignmentId).toBe("assignment-2");
    expect(api.getAssignmentJournal).toHaveBeenCalledWith("assignment-2");
    expect(api.getAssignmentInteractions).toHaveBeenCalledWith("assignment-2");
    expect(onCaseSelected).toHaveBeenCalledWith("case-2");
  });

  it("keeps an empty cockpit when the assignments projection fails", async () => {
    const api = {
      listPatronAssignments: vi.fn().mockRejectedValue(new Error("assignments unavailable")),
      getAssignmentJournal: vi.fn(),
      getAssignmentInteractions: vi.fn(),
    } satisfies CockpitApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderCockpitHook(api, setMessage);

    await act(async () => {
      await result.current.refreshAssignments();
    });

    expect(result.current.assignments).toEqual([]);
    expect(setMessage).toHaveBeenCalledWith({
      tone: "error",
      text: "assignments unavailable",
    });
  });
});
