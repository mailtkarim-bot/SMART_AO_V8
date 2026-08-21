import { useState } from "react";

import type { ApiClient } from "../../infrastructure/api";
import type { BackendReadiness } from "../../shared/types";

export type BackendReadinessState = "idle" | "checking" | "ready" | "not_ready" | "error";

export function useBackendReadiness(api: ApiClient) {
  const [backendReadiness, setBackendReadiness] = useState<BackendReadiness | null>(null);
  const [backendReadinessState, setBackendReadinessState] =
    useState<BackendReadinessState>("idle");

  async function checkBackendReadiness(client: ApiClient = api): Promise<BackendReadiness | null> {
    setBackendReadinessState("checking");
    try {
      const result = await client.getBackendReadiness();
      setBackendReadiness(result);
      setBackendReadinessState(result.status === "ok" ? "ready" : "not_ready");
      return result;
    } catch {
      setBackendReadiness(null);
      setBackendReadinessState("error");
      return null;
    }
  }

  return {
    backendReadiness,
    backendReadinessState,
    checkBackendReadiness,
  };
}
