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

describe("Decision lifecycle transport", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts create, freeze and resolve commands with encoded paths", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ result_code: "DECISION_DRAFT_CREATED" }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ result_code: "DECISION_CONTEXT_FROZEN" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ result_code: "DECISION_CONDITION_RESOLVED" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = createApiClient("https://app.example.test", "access-1");

    await client.createDecision("case/1", {});
    await client.freezeDecisionContext("case/1", "decision/1", {
      context_id: "context-1",
      expected_revision: 0,
      rationale: "Contexte contrôlé",
      references: [{ aggregate_type: "CASE", aggregate_id: "case-1", aggregate_revision: 1, reference_role: "CASE" }],
    });
    await client.resolveDecisionCondition("case/1", "decision/1", "condition/1", {
      expected_revision: 2,
      target_status: "SATISFIED",
      evidence_reference: "proof-1",
    });

    expect(fetchMock.mock.calls[0]?.[0]).toBe("https://app.example.test/api/v1/patron/cases/case%2F1/decisions");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("https://app.example.test/api/v1/patron/cases/case%2F1/decisions/decision%2F1/context");
    expect(fetchMock.mock.calls[2]?.[0]).toBe("https://app.example.test/api/v1/patron/cases/case%2F1/decisions/decision%2F1/conditions/condition%2F1/resolve");
    const createBody = JSON.parse(String((fetchMock.mock.calls[0]?.[1] as RequestInit).body)) as Record<string, unknown>;
    expect(createBody).toMatchObject({ command_id: expect.any(String), idempotency_key: expect.any(String) });
  });
});


describe("Decision risk requirement transport", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("lists paginated links and searches pricing reconciliation candidates", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ items: [], next_cursor: "cursor-1" }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ link_id: "link-1", search: "protection", items: [] }), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const client = createApiClient("https://app.example.test", "access-1");

    await expect(client.listDecisionRiskRequirementLinks("case/1", 20, "cursor/1")).resolves.toMatchObject({
      next_cursor: "cursor-1",
    });
    await expect(
      client.reconcileDecisionPricing("case/1", "link/1", "protection collective", 10),
    ).resolves.toMatchObject({ link_id: "link-1" });

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "https://app.example.test/api/v1/patron/cases/case%2F1/risk-requirement-links?limit=20&cursor=cursor%2F1",
    );
    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      "https://app.example.test/api/v1/patron/cases/case%2F1/risk-requirement-links/link%2F1/pricing-reconciliation?search=protection+collective&limit=10",
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

  it("refreshes and retries a multipart pricing preview after a 401", async () => {
    document.cookie = "smart_ao_csrf=csrf-1; path=/";
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "UNAUTHENTICATED" }), { status: 401 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ access_token: "access-2", token_type: "Bearer", expires_in: 900 }), {
          status: 200,
        }),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify({ batch_id: "batch-1" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const client = createApiClient("https://app.example.test", "access-1");
    await expect(
      client.createPricingImportPreview(
        "case-1",
        new File(["xlsx"], "pricing.xlsx", { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }),
      ),
    ).resolves.toMatchObject({ batch_id: "batch-1" });

    expect(fetchMock).toHaveBeenCalledTimes(3);
    const retryRequest = fetchMock.mock.calls[2]?.[1] as RequestInit;
    expect(retryRequest.body).toBeInstanceOf(FormData);
    expect(new Headers(retryRequest.headers).get("Authorization")).toBe("Bearer access-2");
  });

  it("refreshes and retries a binary submission export after a 401", async () => {
    document.cookie = "smart_ao_csrf=csrf-1; path=/";
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "UNAUTHENTICATED" }), { status: 401 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ access_token: "access-2", token_type: "Bearer", expires_in: 900 }), {
          status: 200,
        }),
      )
      .mockResolvedValueOnce(new Response("zip-bytes", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const client = createApiClient("https://app.example.test", "access-1");
    const archive = await client.downloadSubmissionPackage("package-1");
    await expect(archive.text()).resolves.toBe("zip-bytes");
    expect(fetchMock).toHaveBeenCalledTimes(3);
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


describe("Case creation transport", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts a complete idempotent case command", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "SUCCEEDED",
          result_code: "CASE_CREATED",
          command_id: "command-1",
          idempotency_key: "idempotency-1",
          case_id: "case-1",
          version: 1,
          event_ids: ["event-1"],
          navigation: "CASE_OVERVIEW",
          replayed: false,
        }),
        { status: 201 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = createApiClient("https://app.example.test", "access-1");

    await expect(
      client.createCase({
        title: "Réhabilitation énergétique",
        object_description: "Travaux sur le groupe scolaire.",
        scope_kind: "MULTI_LOT",
        lot_numbers: ["01", "02A"],
        scope_justification: "Périmètre initial à confirmer après lecture DCE.",
        origin_kind: "MANUAL",
      }),
    ).resolves.toMatchObject({ case_id: "case-1", navigation: "CASE_OVERVIEW" });

    expect(fetchMock.mock.calls[0]?.[0]).toBe("https://app.example.test/api/v1/cases");
    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    const body = JSON.parse(String(request.body)) as Record<string, unknown>;
    expect(body).toMatchObject({
      title: "Réhabilitation énergétique",
      object_description: "Travaux sur le groupe scolaire.",
      scope_kind: "MULTI_LOT",
      lot_numbers: ["01", "02A"],
      origin_kind: "MANUAL",
    });
    expect(body.command_id).toEqual(expect.any(String));
    expect(body.idempotency_key).toEqual(expect.any(String));
    expect(body.correlation_id).toEqual(expect.any(String));
    expect(new Headers(request.headers).get("Authorization")).toBe("Bearer access-1");
  });
});
