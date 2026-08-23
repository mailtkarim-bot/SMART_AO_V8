import type { Dispatch, SetStateAction } from "react";

import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ApiClient } from "../../infrastructure/api";
import type { CaseDceReading, KnowledgeSearchResult } from "../../shared/types";
import { useDceKnowledge } from "./useDceKnowledge";

type HookMessage = { tone: "success" | "error" | "warning"; text: string };
type DceApi = Pick<ApiClient, "getCaseDceReading" | "searchCaseKnowledge">;

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
    total: 3,
    pending_human_confirmation: 1,
    confirmed: 2,
    review_required: 0,
    not_applicable: 0,
  },
  requirements: [],
};

const result: KnowledgeSearchResult = {
  source_fragment_id: "fragment-1",
  dce_version_id: "dce-1",
  score: 0.91,
  locator: { label: "CCTP · page 12" },
  embedding_model: "TEST_PROVIDER",
};

function renderDceHook(
  api: DceApi,
  setMessage: Dispatch<SetStateAction<HookMessage | null>>,
  caseId = "case-1",
) {
  return renderHook(() => useDceKnowledge(api as ApiClient, setMessage, caseId));
}

describe("useDceKnowledge", () => {
  it("loads the case DCE reading", async () => {
    const api = {
      getCaseDceReading: vi.fn().mockResolvedValue(reading),
      searchCaseKnowledge: vi.fn(),
    } satisfies DceApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result: hook } = renderDceHook(api, setMessage);

    await act(async () => {
      await hook.current.loadReading();
    });

    expect(api.getCaseDceReading).toHaveBeenCalledWith("case-1");
    expect(hook.current.reading?.counters.pending_human_confirmation).toBe(1);
  });

  it("searches the selected case and keeps the top-k bound", async () => {
    const api = {
      getCaseDceReading: vi.fn(),
      searchCaseKnowledge: vi.fn().mockResolvedValue({
        case_id: "case-1",
        query: "délai",
        results: [result],
      }),
    } satisfies DceApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result: hook } = renderDceHook(api, setMessage);

    await act(async () => {
      hook.current.setQuery("  délai  ");
    });
    await act(async () => {
      await hook.current.searchKnowledge();
    });

    expect(api.searchCaseKnowledge).toHaveBeenCalledWith("case-1", "délai", 5);
    expect(hook.current.results).toEqual([result]);
  });

  it("validates an empty search before calling the API", async () => {
    const api = {
      getCaseDceReading: vi.fn(),
      searchCaseKnowledge: vi.fn(),
    } satisfies DceApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result: hook } = renderDceHook(api, setMessage);

    await act(async () => {
      await hook.current.searchKnowledge();
    });

    expect(api.searchCaseKnowledge).not.toHaveBeenCalled();
    expect(setMessage).toHaveBeenCalledWith({ tone: "warning", text: "Saisissez un terme de recherche DCE." });
  });

  it("keeps a normal 404 reading absence silent", async () => {
    const api = {
      getCaseDceReading: vi.fn().mockRejectedValue(Object.assign(new Error("missing"), { status: 404 })),
      searchCaseKnowledge: vi.fn(),
    } satisfies DceApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result: hook } = renderDceHook(api, setMessage);

    await act(async () => {
      await hook.current.loadReading();
    });

    expect(hook.current.reading).toBeNull();
    expect(setMessage).not.toHaveBeenCalled();
  });
});
