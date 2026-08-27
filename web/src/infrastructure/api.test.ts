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
      .mockResolvedValueOnce(new Response(JSON.stringify({ result_code: "DECISION_CONDITION_RESOLVED" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ result_code: "DECISION_FINALIZED" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ risk_id: "risk/1", treatment: "OPEN", revision: 1 }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ result_code: "DECISION_RISK_TREATMENT_TRANSITIONED", treatment: "MITIGATED" }), { status: 201 }));
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
    await client.finalizeDecision("case/1", "decision/1", {
      expected_revision: 3,
      displayed_fingerprint: "a".repeat(64),
      outcome: "GO",
      justification: "Décision patronale motivée",
    });
    await client.getDecisionRisk("case/1", "risk/1");
    await client.transitionDecisionRiskTreatment("case/1", "risk/1", {
      expected_revision: 1,
      to_treatment: "MITIGATED",
      evidence_excerpt: "CCAP page 8",
      evidence_locator: { page: 8 },
      evidence_start_byte_offset: 100,
      evidence_end_byte_offset: 120,
      rationale: "Mesure de réduction validée",
    });

    expect(fetchMock.mock.calls[0]?.[0]).toBe("https://app.example.test/api/v1/patron/cases/case%2F1/decisions");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("https://app.example.test/api/v1/patron/cases/case%2F1/decisions/decision%2F1/context");
    expect(fetchMock.mock.calls[2]?.[0]).toBe("https://app.example.test/api/v1/patron/cases/case%2F1/decisions/decision%2F1/conditions/condition%2F1/resolve");
    expect(fetchMock.mock.calls[3]?.[0]).toBe("https://app.example.test/api/v1/patron/cases/case%2F1/decisions/decision%2F1/go-no-go");
    expect(fetchMock.mock.calls[4]?.[0]).toBe("https://app.example.test/api/v1/patron/cases/case%2F1/risks/risk%2F1");
    expect(fetchMock.mock.calls[5]?.[0]).toBe("https://app.example.test/api/v1/patron/cases/case%2F1/risks/risk%2F1/treatment");
    const finalizeBody = JSON.parse(String((fetchMock.mock.calls[3]?.[1] as RequestInit).body)) as Record<string, unknown>;
    expect(finalizeBody).toMatchObject({
      displayed_fingerprint: "a".repeat(64),
      outcome: "GO",
      conditions: [],
      command_id: expect.any(String),
      idempotency_key: expect.any(String),
    });
    const createBody = JSON.parse(String((fetchMock.mock.calls[0]?.[1] as RequestInit).body)) as Record<string, unknown>;
    expect(createBody).toMatchObject({ command_id: expect.any(String), idempotency_key: expect.any(String) });
    const transitionBody = JSON.parse(String((fetchMock.mock.calls[5]?.[1] as RequestInit).body)) as Record<string, unknown>;
    expect(transitionBody).toMatchObject({
      risk_id: "risk/1",
      expected_revision: 1,
      to_treatment: "MITIGATED",
      evidence_locator: { page: 8 },
      command_id: expect.any(String),
      idempotency_key: expect.any(String),
    });
  });
});


describe("Preparation review transport", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("reads reviews and sends revision-checked patron decisions", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ package_id: "package-1", reviews: [] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ result_code: "PREPARATION_REVIEW_REQUESTED" }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ result_code: "PREPARATION_REVIEW_DECIDED" }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ result_code: "PREPARATION_CORRECTION_ADDED" }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = createApiClient("https://app.example.test", "access-1");

    await client.listPreparationReviews("package/1");
    await client.requestPreparationReview("package/1", {
      expected_package_revision: 3,
      target_document_id: "document-1",
      target_version: 2,
    });
    await client.decidePreparationReview("package/1", {
      expected_review_revision: 1,
      review_id: "review/1",
      target_document_id: "document-1",
      decision_code: "ACCEPTED",
      decision_note: "Validé.",
    });
    await client.addPreparationCorrection("package/1", {
      review_id: "review/1",
      target_document_id: "document-1",
      correction_code: "WORDING_UNCLEAR",
      instruction: "Préciser la source.",
    });

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "https://app.example.test/api/v1/preparation/package%2F1/reviews",
      "https://app.example.test/api/v1/preparation/package%2F1/reviews",
      "https://app.example.test/api/v1/preparation/package%2F1/reviews/review%2F1/decision",
      "https://app.example.test/api/v1/preparation/package%2F1/reviews/review%2F1/corrections",
    ]);
    const decisionBody = JSON.parse(String((fetchMock.mock.calls[2]?.[1] as RequestInit).body)) as Record<string, unknown>;
    expect(decisionBody).toMatchObject({ expected_review_revision: 1, decision_code: "ACCEPTED", command_id: expect.any(String) });
  });
});

describe("MFA TOTP transport", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    document.cookie = "smart_ao_csrf=; Max-Age=0; path=/";
  });

  it("sends CSRF-protected enrollment, confirmation, step-up and disable requests", async () => {
    document.cookie = "smart_ao_csrf=csrf-1; path=/";
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ factor_id: "factor-1", otpauth_uri: "otpauth://totp/x", recovery_codes: ["r1"], expires_at: "2026-08-27T00:00:00Z" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ access_token: "token-2", token_type: "Bearer", expires_in: 900, used_recovery_code: false }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ access_token: "token-3", token_type: "Bearer", expires_in: 900, used_recovery_code: false }), { status: 200 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = createApiClient("https://app.example.test", "access-1");

    await client.beginTotpEnrollment();
    await client.confirmTotpEnrollment("factor-1", "123456");
    await client.stepUpTotp("654321");
    await client.disableTotp("111111");

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "https://app.example.test/api/v1/auth/mfa/totp/enroll",
      "https://app.example.test/api/v1/auth/mfa/totp/confirm",
      "https://app.example.test/api/v1/auth/mfa/totp/step-up",
      "https://app.example.test/api/v1/auth/mfa/totp/disable",
    ]);
    for (const [, init] of fetchMock.mock.calls) {
      expect(((init as RequestInit).headers as Headers).get("X-CSRF-Token")).toBe("csrf-1");
    }
  });
});

describe("Collaborator task workflow transport", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("reads and mutates information requests and blockers with encoded ids", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ task_id: "task-1", state: "OPEN", aggregate_revision: 2, information_requests: [], blockers: [] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ result_code: "INFORMATION_REQUEST_CREATED" }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ result_code: "INFORMATION_REQUEST_ANSWERED" }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ result_code: "TASK_BLOCKED" }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ result_code: "TASK_UNBLOCKED" }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = createApiClient("https://app.example.test", "access-1");

    await client.getCollaboratorTaskWorkflow("task/1");
    await client.createInformationRequest("task/1", {
      expected_task_revision: 2,
      request_kind: "CLARIFICATION",
      subject: "Objet",
      question: "Question",
      requested_object: "Pièce",
      reason: "Motif",
      priority: "HIGH",
    });
    await client.recordInformationResponse("request/1", {
      expected_revision: 1,
      response_text: "Réponse",
      outcome: "ANSWERED",
    });
    await client.declareTaskBlocker("task/1", {
      expected_revision: 2,
      blocker_kind: "MISSING_INFORMATION",
      description: "Il manque une preuve",
      resolution_owner: "COLLABORATEUR",
    });
    await client.resolveTaskBlocker("task/1", "blocker/1", {
      expected_revision: 3,
      resolution_note: "Preuve ajoutée",
    });

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "https://app.example.test/api/v1/collaborator/tasks/task%2F1/workflow",
      "https://app.example.test/api/v1/collaborator/tasks/task%2F1/information-requests",
      "https://app.example.test/api/v1/collaborator/information-requests/request%2F1/responses",
      "https://app.example.test/api/v1/collaborator/tasks/task%2F1/blockers",
      "https://app.example.test/api/v1/collaborator/tasks/task%2F1/blockers/blocker%2F1/resolve",
    ]);
    const createBody = JSON.parse(String((fetchMock.mock.calls[1]?.[1] as RequestInit).body)) as Record<string, unknown>;
    expect(createBody).toMatchObject({ expected_task_revision: 2, command_id: expect.any(String), idempotency_key: expect.any(String) });
  });
});

describe("Preparation generated document transport", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("reads preview and download content with encoded package/document ids", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response("# Document contrôlé", { status: 200, headers: { "Content-Type": "text/markdown" } }))
      .mockResolvedValueOnce(new Response("# Document contrôlé", { status: 200, headers: { "Content-Type": "text/markdown" } }));
    vi.stubGlobal("fetch", fetchMock);
    const client = createApiClient("https://app.example.test", "access-1");

    await expect(client.getGeneratedDocumentContent("package/1", "document/1").then((blob) => blob.text())).resolves.toBe("# Document contrôlé");
    await expect(client.getGeneratedDocumentContent("package/1", "document/1", true).then((blob) => blob.text())).resolves.toBe("# Document contrôlé");

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "https://app.example.test/api/v1/collaborator/preparation/package%2F1/documents/document%2F1/content",
    );
    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      "https://app.example.test/api/v1/collaborator/preparation/package%2F1/documents/document%2F1/content?download=true",
    );
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).credentials).toBe("include");
    expect(((fetchMock.mock.calls[0]?.[1] as RequestInit).headers as Headers).get("Accept")).toBe("text/markdown");
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
