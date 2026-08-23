import { afterEach, describe, expect, it, vi } from "vitest";

import { createApiClient } from "./api";

describe("api client response parsing", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("maps a non-JSON error response to the generic status message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("<html>proxy failure</html>", {
          status: 502,
          headers: { "Content-Type": "text/html" },
        }),
      ),
    );

    await expect(
      createApiClient("https://app.example.test", "token").listAssignedCases(),
    ).rejects.toThrow("La requête a échoué (502).");
  });
});


describe("BOAMP transport", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("lists observations and posts a closed qualification command", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ observations: [] }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            qualification_id: "qualification-1",
            event_id: "event-1",
            replayed: false,
          }),
          { status: 200 },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    const client = createApiClient("https://app.example.test", "access-1");

    await expect(client.listBoampObservations()).resolves.toEqual({ observations: [] });
    await expect(
      client.qualifyBoampObservation("obs/1", {
        decision: "QUALIFIED",
        reason_code: "RELEVANT_PUBLIC_SIGNAL",
      }),
    ).resolves.toMatchObject({ replayed: false });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://app.example.test/api/v1/patron/boamp-opportunities",
      expect.objectContaining({ credentials: "include" }),
    );
    const request = fetchMock.mock.calls[1]?.[1] as RequestInit;
    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      "https://app.example.test/api/v1/patron/boamp-opportunities/obs%2F1/qualification",
    );
    const body = JSON.parse(String(request.body)) as Record<string, unknown>;
    expect(body).toMatchObject({
      decision: "QUALIFIED",
      reason_code: "RELEVANT_PUBLIC_SIGNAL",
    });
    expect(body.command_id).toEqual(expect.any(String));
    expect(body.idempotency_key).toEqual(expect.any(String));
  });

  it("reads DCE metadata and searches knowledge with encoded query parameters", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ case_id: "case-1", availability: "AVAILABLE" }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ case_id: "case-1", query: "délai", results: [] }), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const client = createApiClient("https://app.example.test", "access-1");

    await expect(client.getCaseDceReading("case/1")).resolves.toMatchObject({ availability: "AVAILABLE" });
    await expect(client.searchCaseKnowledge("case/1", "délai d’exécution", 5)).resolves.toMatchObject({ results: [] });

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "https://app.example.test/api/v1/cases/case%2F1/dce-reading",
    );
    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      "https://app.example.test/api/v1/cases/case%2F1/knowledge/search?q=d%C3%A9lai+d%E2%80%99ex%C3%A9cution&top_k=5",
    );
  });
});

describe("browser authentication transport", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    document.cookie = "smart_ao_csrf=; Max-Age=0; path=/";
  });

  it("logs in with credentials and includes cookies without persisting the access token", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ access_token: "access-1", token_type: "Bearer", expires_in: 900 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const client = createApiClient("https://app.example.test", "");
    await expect(
      client.login({ email: "patron@example.test", password: "x", tenant_id: "tenant-1" }),
    ).resolves.toMatchObject({ access_token: "access-1" });

    expect(fetchMock).toHaveBeenCalledWith(
      "https://app.example.test/api/v1/auth/login",
      expect.objectContaining({ method: "POST", credentials: "include" }),
    );
    expect(window.localStorage.getItem("smart-ao-token")).toBeNull();
  });

  it("refreshes once on a protected GET returning 401 and retries with the new token", async () => {
    document.cookie = "smart_ao_csrf=csrf-1; path=/";
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "UNAUTHENTICATED" }), { status: 401 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ access_token: "access-2", token_type: "Bearer", expires_in: 900 }), {
          status: 200,
        }),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const client = createApiClient("https://app.example.test", "access-1");
    await expect(client.listAssignedCases()).resolves.toEqual([]);

    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://app.example.test/api/v1/auth/refresh",
      expect.objectContaining({ method: "POST", credentials: "include", headers: expect.anything() }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "https://app.example.test/api/v1/cases/assigned",
      expect.objectContaining({ headers: expect.anything(), credentials: "include" }),
    );
  });

  it("logs out with the double-submit CSRF header", async () => {
    document.cookie = "smart_ao_csrf=csrf-logout; path=/";
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(createApiClient("https://app.example.test", "access-1").logout()).resolves.toBeUndefined();
    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(request.credentials).toBe("include");
    expect(new Headers(request.headers).get("Authorization")).toBe("Bearer access-1");
    expect(new Headers(request.headers).get("X-CSRF-Token")).toBe("csrf-logout");
  });
});
