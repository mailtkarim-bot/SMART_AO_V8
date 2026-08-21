import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ApiClient } from "../../infrastructure/api";
import { useBackendReadiness } from "./useBackendReadiness";

const ready = {
  status: "ok" as const,
  service: "smart-ao-v8" as const,
  checks: { database: "ok" as const, clamav: "ok" as const },
};

function apiWith(getBackendReadiness: ApiClient["getBackendReadiness"]): ApiClient {
  return { getBackendReadiness } as ApiClient;
}

describe("useBackendReadiness", () => {
  it("records a ready backend and exposes its checks", async () => {
    const getBackendReadiness = vi.fn().mockResolvedValue(ready);
    const { result } = renderHook(() => useBackendReadiness(apiWith(getBackendReadiness)));

    await act(async () => {
      await result.current.checkBackendReadiness();
    });

    expect(getBackendReadiness).toHaveBeenCalledOnce();
    expect(result.current.backendReadinessState).toBe("ready");
    expect(result.current.backendReadiness).toEqual(ready);
  });

  it("keeps a non-ready response distinct from a network error", async () => {
    const notReady = {
      status: "not_ready" as const,
      service: "smart-ao-v8" as const,
      checks: { database: "ok" as const, clamav: "failed" as const },
    };
    const { result } = renderHook(() => useBackendReadiness(apiWith(vi.fn().mockResolvedValue(notReady))));

    await act(async () => {
      await result.current.checkBackendReadiness();
    });

    expect(result.current.backendReadinessState).toBe("not_ready");
    expect(result.current.backendReadiness?.checks.clamav).toBe("failed");
  });

  it("clears stale readiness after an unreachable backend", async () => {
    const { result } = renderHook(() =>
      useBackendReadiness(apiWith(vi.fn().mockRejectedValue(new Error("offline")))),
    );

    await act(async () => {
      await result.current.checkBackendReadiness();
    });

    expect(result.current.backendReadinessState).toBe("error");
    expect(result.current.backendReadiness).toBeNull();
  });
});
