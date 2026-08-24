import type { Dispatch, SetStateAction } from "react";

import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ApiClient } from "../../infrastructure/api";
import type { BoampObservation } from "../../shared/types";
import { useBoampOpportunities } from "./useBoampOpportunities";

type HookMessage = { tone: "success" | "error" | "warning"; text: string };
type BoampApi = Pick<ApiClient, "listBoampObservations" | "qualifyBoampObservation">;

const observation = (id = "observation-1"): BoampObservation => ({
  observation_id: id,
  source_notice_id: `BOAMP-${id}`,
  title: "Réhabilitation d’une école",
  publication_date: "2026-08-20",
  response_deadline: "2026-09-15T12:00:00Z",
  department_codes: ["59"],
  market_types: ["TRAVAUX"],
  source_status: "EN_COURS",
  score_version: "BOAMP_PUBLIC_V1",
  score: 82,
  score_explanation: { keyword_hits: ["réhabilitation"] },
  fingerprint_sha256: "a".repeat(64),
});

function renderBoampHook(
  api: BoampApi,
  setMessage: Dispatch<SetStateAction<HookMessage | null>>,
) {
  return renderHook(() => useBoampOpportunities(api as ApiClient, setMessage));
}

describe("useBoampOpportunities", () => {
  it("loads observations and selects the first item", async () => {
    const api = {
      listBoampObservations: vi.fn().mockResolvedValue({ observations: [observation()] }),
      qualifyBoampObservation: vi.fn(),
    } satisfies BoampApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderBoampHook(api, setMessage);

    await act(async () => {
      await result.current.refreshObservations();
    });

    expect(result.current.observations).toHaveLength(1);
    expect(result.current.selectedObservationId).toBe("observation-1");
    expect(result.current.qualificationForm.decision).toBe("QUALIFIED");
  });

  it("qualifies the selected observation and reports an idempotent replay", async () => {
    const api = {
      listBoampObservations: vi.fn().mockResolvedValue({ observations: [observation()] }),
      qualifyBoampObservation: vi.fn().mockResolvedValue({
        qualification_id: "qualification-1",
        event_id: "event-1",
        replayed: true,
      }),
    } satisfies BoampApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderBoampHook(api, setMessage);

    await act(async () => {
      await result.current.refreshObservations();
    });
    await act(async () => {
      await result.current.qualifySelected();
    });

    expect(api.qualifyBoampObservation).toHaveBeenCalledWith("observation-1", {
      decision: "QUALIFIED",
      reason_code: "RELEVANT_PUBLIC_SIGNAL",
    });
    expect(setMessage).toHaveBeenCalledWith({
      tone: "success",
      text: "Qualification déjà enregistrée : rejeu idempotent.",
    });
  });

  it("does not call the API without a selected observation", async () => {
    const api = {
      listBoampObservations: vi.fn().mockResolvedValue({ observations: [] }),
      qualifyBoampObservation: vi.fn(),
    } satisfies BoampApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderBoampHook(api, setMessage);

    await act(async () => {
      await result.current.qualifySelected();
    });

    expect(api.qualifyBoampObservation).not.toHaveBeenCalled();
    expect(setMessage).toHaveBeenCalledWith({
      tone: "warning",
      text: "Sélectionnez une opportunité BOAMP avant de qualifier.",
    });
  });

  it("reports a projection failure", async () => {
    const api = {
      listBoampObservations: vi.fn().mockRejectedValue(new Error("BOAMP unavailable")),
      qualifyBoampObservation: vi.fn(),
    } satisfies BoampApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderBoampHook(api, setMessage);

    await act(async () => {
      await result.current.refreshObservations();
    });

    expect(result.current.observations).toEqual([]);
    expect(setMessage).toHaveBeenCalledWith({ tone: "error", text: "BOAMP unavailable" });
  });
});
