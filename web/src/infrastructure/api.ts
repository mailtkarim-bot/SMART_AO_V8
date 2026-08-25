import type {
  AssignedCase,
  CreateCaseInput,
  CreateCaseResponse,
  AuthSession,
  CurrentActor,
  BackendReadiness,
  CommandReceipt,
  DraftReport,
  FinancialCategory,
  PatronAssignment,
  PatronAssignmentInteractions,
  PatronAssignmentJournalItem,
  PatronAction,
  PatronDecisionDossier,
  PricingScenario,
  SubmissionEvidenceReceipt,
  SubmissionPackageReceipt,
  SubmissionSignatureProjection,
  SubmissionSignatureReceipt,
  CollaboratorTaskList,
  PreparationPackage,
  CommitPricingImportRequest,
  PricingImportCommitReceipt,
  PricingImportPreview,
  PricingImportBatchRead,
  EnterpriseCompany,
  EnterpriseCompanyInput,
  EnterpriseDocumentUploadInput,
  EnterpriseDocumentVerificationInput,
  EnterpriseReceipt,
  EnterpriseUploadReceipt,
  EnterpriseCapability,
  EnterpriseCapabilityInput,
  EnterpriseCapabilityVersionInput,
  BoampObservation,
  BoampQualificationInput,
  BoampQualificationReceipt,
  CaseDceReading,
  KnowledgeSearchResponse,
  CreateDecisionRequest,
  CreateDecisionResponse,
  FreezeDecisionContextRequest,
  FreezeDecisionContextResponse,
  ResolveDecisionConditionRequest,
  ResolveDecisionConditionResponse,
} from "../shared/types";

const makeId = () => crypto.randomUUID();

function readCookie(name: string): string | undefined {
  if (typeof document === "undefined") return undefined;
  const prefix = `${encodeURIComponent(name)}=`;
  const cookie = document.cookie
    .split("; ")
    .find((entry) => entry.startsWith(prefix));
  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : undefined;
}

function isAuthSession(value: unknown): value is AuthSession {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.access_token === "string" &&
    candidate.token_type === "Bearer" &&
    typeof candidate.expires_in === "number"
  );
}

function apiError(status: number, body: unknown): Error & { status?: number; detail?: string } {
  const detail = responseDetail(body);
  const error = new Error(
    detail ?? `La requête a échoué (${status}).`,
  ) as Error & { status?: number; detail?: string };
  error.status = status;
  error.detail = detail;
  return error;
}

async function parseResponseBody(response: Response): Promise<unknown> {
  const body = await response.text();
  if (!body) return undefined;
  try {
    return JSON.parse(body);
  } catch {
    return undefined;
  }
}

function responseDetail(body: unknown): string | undefined {
  if (typeof body !== "object" || body === null || !("detail" in body)) {
    return undefined;
  }
  const detail = (body as { detail?: unknown }).detail;
  return typeof detail === "string" ? detail : undefined;
}

const REQUEST_TIMEOUT_MS = 30_000;

type SessionExpiredListener = () => void;

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit,
  timeoutMs = REQUEST_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = globalThis.setTimeout(() => controller.abort(), timeoutMs);
  const abortFromCaller = () => controller.abort();
  init.signal?.addEventListener("abort", abortFromCaller, { once: true });
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    globalThis.clearTimeout(timeoutId);
    init.signal?.removeEventListener("abort", abortFromCaller);
  }
}

function isReplayableBody(body: BodyInit | null | undefined): boolean {
  return (
    body === undefined ||
    body === null ||
    typeof body === "string" ||
    body instanceof FormData ||
    body instanceof Blob ||
    body instanceof ArrayBuffer ||
    body instanceof URLSearchParams
  );
}

export type ApiClient = ReturnType<typeof createApiClient>;

type TokenRefreshListener = (session: AuthSession) => void;

export function createApiClient(
  baseUrl: string,
  token: string,
  onTokenRefreshed?: TokenRefreshListener,
  onSessionExpired?: SessionExpiredListener,
) {
  const root = baseUrl.replace(/\/$/, "");
  let currentToken = token;
  let refreshPromise: Promise<AuthSession | null> | null = null;

  async function refreshSession(): Promise<AuthSession | null> {
    if (refreshPromise) return refreshPromise;
    refreshPromise = (async () => {
      const csrfToken = readCookie("smart_ao_csrf");
      if (!csrfToken) return null;
      const response = await fetchWithTimeout(`${root}/api/v1/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: { Accept: "application/json", "X-CSRF-Token": csrfToken },
      });
      const parsed = await parseResponseBody(response);
      if (!response.ok || !isAuthSession(parsed)) return null;
      currentToken = parsed.access_token;
      onTokenRefreshed?.(parsed);
      return parsed;
    })().finally(() => {
      refreshPromise = null;
    });
    return refreshPromise;
  }

  async function request<T>(
    path: string,
    init: RequestInit = {},
    hasRetried = false,
  ): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (typeof init.body === "string") {
      headers.set("Content-Type", "application/json");
    }
    if (currentToken.trim()) {
      headers.set("Authorization", `Bearer ${currentToken.trim()}`);
    }

    const response = await fetchWithTimeout(`${root}${path}`, {
      ...init,
      credentials: "include",
      headers,
    });
    const parsed = await parseResponseBody(response);
    const canRetry =
      !hasRetried &&
      response.status === 401 &&
      path !== "/api/v1/auth/me" &&
      path !== "/api/v1/auth/login" &&
      path !== "/api/v1/auth/refresh" &&
      path !== "/api/v1/auth/logout" &&
      isReplayableBody(init.body);
    if (canRetry) {
      const refreshed = await refreshSession();
      if (refreshed) return request<T>(path, init, true);
      currentToken = "";
      onSessionExpired?.();
    }
    if (!response.ok) {
      throw apiError(response.status, parsed);
    }
    return parsed as T;
  }

  async function requestBlob(
    path: string,
    init: RequestInit = {},
    hasRetried = false,
  ): Promise<Blob> {
    const headers = new Headers(init.headers);
    headers.set("Accept", headers.get("Accept") ?? "application/octet-stream");
    if (currentToken.trim()) {
      headers.set("Authorization", `Bearer ${currentToken.trim()}`);
    }
    const response = await fetchWithTimeout(`${root}${path}`, {
      ...init,
      credentials: "include",
      headers,
    });
    if (response.status === 401 && !hasRetried) {
      const refreshed = await refreshSession();
      if (refreshed) return requestBlob(path, init, true);
      currentToken = "";
      onSessionExpired?.();
    }
    if (!response.ok) {
      const parsed = await parseResponseBody(response);
      throw apiError(response.status, parsed);
    }
    return response.blob();
  }

  async function login(input: {
    email: string;
    password: string;
    tenant_id: string;
  }): Promise<AuthSession> {
    const result = await request<AuthSession>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(input),
    });
    currentToken = result.access_token;
    onTokenRefreshed?.(result);
    return result;
  }

  async function logout(): Promise<void> {
    const csrfToken = readCookie("smart_ao_csrf");
    await request<void>("/api/v1/auth/logout", {
      method: "POST",
      headers: csrfToken ? { "X-CSRF-Token": csrfToken } : undefined,
    });
    currentToken = "";
  }

  return {
    login,
    refresh: refreshSession,
    getCurrentActor: () => request<CurrentActor>("/api/v1/auth/me"),
    logout,
    getBackendReadiness: () => request<BackendReadiness>("/healthz/ready"),
    listAssignedCases: () => request<AssignedCase[]>("/api/v1/cases/assigned"),
    createCase: (input: CreateCaseInput) =>
      request<CreateCaseResponse>("/api/v1/cases", {
        method: "POST",
        body: JSON.stringify({
          command_id: makeId(),
          idempotency_key: makeId(),
          correlation_id: makeId(),
          ...input,
        }),
      }),
    listPatronAssignments: () =>
      request<{ items: PatronAssignment[] }>("/api/v1/patron/assignments"),
    getAssignmentJournal: (assignmentId: string) =>
      request<{ assignment: PatronAssignment; items: PatronAssignmentJournalItem[] }>(
        `/api/v1/patron/assignments/${encodeURIComponent(assignmentId)}/journal`,
      ),
    getAssignmentInteractions: (assignmentId: string) =>
      request<PatronAssignmentInteractions>(
        `/api/v1/patron/assignments/${encodeURIComponent(assignmentId)}/interactions`,
      ),
    listPatronActions: () =>
      request<{ items: PatronAction[]; open_count: number }>("/api/v1/patron/actions"),
    listBoampObservations: () =>
      request<{ observations: BoampObservation[] }>(
        "/api/v1/patron/boamp-opportunities",
      ),
    qualifyBoampObservation: (
      observationId: string,
      input: BoampQualificationInput,
    ) =>
      request<BoampQualificationReceipt>(
        `/api/v1/patron/boamp-opportunities/${encodeURIComponent(observationId)}/qualification`,
        {
          method: "POST",
          body: JSON.stringify({
            command_id: makeId(),
            idempotency_key: makeId(),
            ...input,
          }),
        },
      ),
    getCaseDceReading: (caseId: string) =>
      request<CaseDceReading>(
        `/api/v1/cases/${encodeURIComponent(caseId)}/dce-reading`,
      ),
    searchCaseKnowledge: (caseId: string, query: string, topK = 5) => {
      const params = new URLSearchParams({ q: query, top_k: String(topK) });
      return request<KnowledgeSearchResponse>(
        `/api/v1/cases/${encodeURIComponent(caseId)}/knowledge/search?${params.toString()}`,
      );
    },
    getDecisionDossier: (caseId: string) =>
      request<PatronDecisionDossier>(
        `/api/v1/patron/cases/${encodeURIComponent(caseId)}/decision-dossier`,
      ),
    createDecision: (caseId: string, input: CreateDecisionRequest) =>
      request<CreateDecisionResponse>(
        `/api/v1/patron/cases/${encodeURIComponent(caseId)}/decisions`,
        {
          method: "POST",
          body: JSON.stringify({
            command_id: input.command_id ?? makeId(),
            idempotency_key: input.idempotency_key ?? makeId(),
            scope_fingerprint: input.scope_fingerprint,
          }),
        },
      ),
    freezeDecisionContext: (
      caseId: string,
      decisionId: string,
      input: FreezeDecisionContextRequest,
    ) =>
      request<FreezeDecisionContextResponse>(
        `/api/v1/patron/cases/${encodeURIComponent(caseId)}/decisions/${encodeURIComponent(decisionId)}/context`,
        {
          method: "POST",
          body: JSON.stringify({
            command_id: input.command_id ?? makeId(),
            idempotency_key: input.idempotency_key ?? makeId(),
            context_id: input.context_id,
            expected_revision: input.expected_revision,
            rationale: input.rationale,
            unknowns: input.unknowns ?? [],
            risks: input.risks ?? [],
            references: input.references,
          }),
        },
      ),
    resolveDecisionCondition: (
      caseId: string,
      decisionId: string,
      conditionId: string,
      input: ResolveDecisionConditionRequest,
    ) =>
      request<ResolveDecisionConditionResponse>(
        `/api/v1/patron/cases/${encodeURIComponent(caseId)}/decisions/${encodeURIComponent(decisionId)}/conditions/${encodeURIComponent(conditionId)}/resolve`,
        {
          method: "POST",
          body: JSON.stringify({
            command_id: input.command_id ?? makeId(),
            idempotency_key: input.idempotency_key ?? makeId(),
            transition_id: input.transition_id ?? makeId(),
            expected_revision: input.expected_revision,
            target_status: input.target_status,
            evidence_reference: input.evidence_reference,
            failure_reason: input.failure_reason,
          }),
        },
      ),
    listPricingScenarios: (caseId: string) =>
      request<PricingScenario[]>(
        `/api/v1/patron/cases/${encodeURIComponent(caseId)}/pricing-scenarios`,
      ),
    listEnterpriseCapabilities: (companyId: string) =>
      request<{ capabilities: EnterpriseCapability[] }>(
        `/api/v1/patron/enterprise/companies/${encodeURIComponent(companyId)}/capabilities`,
      ),
    createEnterpriseCapability: (companyId: string, input: EnterpriseCapabilityInput) =>
      request<EnterpriseReceipt>(
        `/api/v1/patron/enterprise/companies/${encodeURIComponent(companyId)}/capabilities`,
        {
          method: "POST",
          body: JSON.stringify({ command_id: makeId(), idempotency_key: makeId(), ...input }),
        },
      ),
    addEnterpriseCapabilityVersion: (
      capabilityId: string,
      input: EnterpriseCapabilityVersionInput,
    ) =>
      request<EnterpriseReceipt>(
        `/api/v1/patron/enterprise/capabilities/${encodeURIComponent(capabilityId)}/versions`,
        {
          method: "POST",
          body: JSON.stringify({ command_id: makeId(), idempotency_key: makeId(), ...input }),
        },
      ),
    getEnterpriseCompany: () =>
      request<EnterpriseCompany>("/api/v1/patron/enterprise/company"),
    createEnterpriseCompany: (input: EnterpriseCompanyInput) =>
      request<EnterpriseReceipt>("/api/v1/patron/enterprise/company", {
        method: "POST",
        body: JSON.stringify({
          command_id: makeId(),
          idempotency_key: makeId(),
          ...input,
        }),
      }),
    prepareEnterpriseDocumentUpload: (companyId: string, input: EnterpriseDocumentUploadInput) =>
      request<EnterpriseReceipt>(
        `/api/v1/patron/enterprise/companies/${encodeURIComponent(companyId)}/documents/upload`,
        {
          method: "POST",
          body: JSON.stringify({
            command_id: makeId(),
            idempotency_key: makeId(),
            ...input,
          }),
        },
      ),
    uploadEnterpriseDocumentContent: (
      companyId: string,
      uploadId: string,
      file: File,
    ) =>
      request<EnterpriseUploadReceipt>(
        `/api/v1/patron/enterprise/companies/${encodeURIComponent(companyId)}/documents/uploads/${encodeURIComponent(uploadId)}/content`,
        {
          method: "PUT",
          headers: { "Idempotency-Key": makeId() },
          body: file,
        },
      ),
    verifyEnterpriseDocument: (
      companyId: string,
      documentId: string,
      input: EnterpriseDocumentVerificationInput,
    ) =>
      request<EnterpriseReceipt>(
        `/api/v1/patron/enterprise/companies/${encodeURIComponent(companyId)}/documents/${encodeURIComponent(documentId)}/verification`,
        {
          method: "POST",
          body: JSON.stringify({
            command_id: makeId(),
            idempotency_key: makeId(),
            ...input,
          }),
        },
      ),
    createPricingImportPreview: (
      caseId: string,
      file: File,
      documentKind: "DPGF" | "BPU" | "EXCEL" = "EXCEL",
    ) => {
      const form = new FormData();
      form.append("upload", file);
      const query = new URLSearchParams({ document_kind: documentKind });
      return request<PricingImportPreview>(
        `/api/v1/patron/cases/${encodeURIComponent(caseId)}/pricing-import/preview?${query}`,
        {
          method: "POST",
          headers: { "X-Command-Id": makeId(), "Idempotency-Key": makeId() },
          body: form,
        },
      );
    },
    getPricingImport: (caseId: string, batchId: string) =>
      request<PricingImportBatchRead>(
        `/api/v1/patron/cases/${encodeURIComponent(caseId)}/pricing-import/${encodeURIComponent(batchId)}`,
      ),
    commitPricingImport: (
      caseId: string,
      batchId: string,
      input: Omit<CommitPricingImportRequest, "command_id" | "idempotency_key"> & {
        command_id?: string;
        idempotency_key?: string;
      },
    ) =>
      request<PricingImportCommitReceipt>(
        `/api/v1/patron/cases/${encodeURIComponent(caseId)}/pricing-import/${encodeURIComponent(batchId)}/commit`,
        {
          method: "POST",
          body: JSON.stringify({
            command_id: input.command_id ?? makeId(),
            idempotency_key: input.idempotency_key ?? makeId(),
            ...input,
          }),
        },
      ),
    prepareSubmissionPackage: (preparationPackageId: string, expectedRevision: number) =>
      request<SubmissionPackageReceipt>(
        `/api/v1/patron/preparation/${encodeURIComponent(preparationPackageId)}/submission-packages`,
        {
          method: "POST",
          body: JSON.stringify({
            command_id: makeId(),
            idempotency_key: makeId(),
            expected_preparation_revision: expectedRevision,
          }),
        },
      ),
    downloadSubmissionPackage: (submissionPackageId: string): Promise<Blob> =>
      requestBlob(
        `/api/v1/patron/submission-packages/${encodeURIComponent(submissionPackageId)}/export`,
        { headers: { Accept: "application/zip" } },
      ),
    getCollaboratorPreparation: (packageId: string) =>
      request<PreparationPackage>(
        `/api/v1/collaborator/preparation/${encodeURIComponent(packageId)}`,
      ),
    listCollaboratorTasks: (caseId: string) =>
      request<CollaboratorTaskList>(
        `/api/v1/collaborator/cases/${encodeURIComponent(caseId)}/tasks`,
      ),
    evaluatePreparationReadiness: (
      caseId: string,
      input: {
        package_id: string;
        assignment_id: string;
        dce_version_id: string;
        expected_revision: number;
      },
    ) =>
      request<CommandReceipt>(
        `/api/v1/collaborator/cases/${encodeURIComponent(caseId)}/preparation/readiness`,
        {
          method: "POST",
          body: JSON.stringify({ command_id: makeId(), idempotency_key: makeId(), ...input }),
        },
      ),
    generateTechnicalDocument: (
      packageId: string,
      input: { expected_revision: number; readiness_revision: number },
    ) =>
      request<CommandReceipt>(
        `/api/v1/collaborator/preparation/${encodeURIComponent(packageId)}/documents`,
        {
          method: "POST",
          body: JSON.stringify({
            command_id: makeId(),
            idempotency_key: makeId(),
            document_kind: "TECHNICAL_RESPONSE",
            ...input,
          }),
        },
      ),
    claimCollaboratorTask: (taskId: string, expectedRevision: number) =>
      request<CommandReceipt>(
        `/api/v1/collaborator/tasks/${encodeURIComponent(taskId)}/claim`,
        {
          method: "POST",
          body: JSON.stringify({
            command_id: makeId(),
            idempotency_key: makeId(),
            expected_revision: expectedRevision,
          }),
        },
      ),
    recordCollaboratorTaskResult: (
      taskId: string,
      input: {
        expected_revision: number;
        result_text: string;
        source_locator?: string;
        outcome: "RECORDED" | "NOT_APPLICABLE" | "UNABLE_TO_COMPLETE";
      },
    ) =>
      request<CommandReceipt>(
        `/api/v1/collaborator/tasks/${encodeURIComponent(taskId)}/results`,
        {
          method: "POST",
          body: JSON.stringify({ command_id: makeId(), idempotency_key: makeId(), ...input }),
        },
      ),
    completeCollaboratorTask: (taskId: string, expectedRevision: number) =>
      request<CommandReceipt>(
        `/api/v1/collaborator/tasks/${encodeURIComponent(taskId)}/complete`,
        {
          method: "POST",
          body: JSON.stringify({
            command_id: makeId(),
            idempotency_key: makeId(),
            expected_revision: expectedRevision,
          }),
        },
      ),
    createPreparationSnapshot: (
      packageId: string,
      input: { snapshot_id: string; expected_package_revision: number },
    ) =>
      request<CommandReceipt>(
        `/api/v1/collaborator/preparation/${encodeURIComponent(packageId)}/snapshots`,
        {
          method: "POST",
          body: JSON.stringify({
            command_id: makeId(),
            idempotency_key: makeId(),
            package_id: packageId,
            ...input,
          }),
        },
      ),
    transmitPreparationSnapshot: (
      packageId: string,
      input: { snapshot_id: string; transmission_id: string; expected_package_revision: number },
    ) =>
      request<CommandReceipt>(
        `/api/v1/collaborator/preparation/${encodeURIComponent(packageId)}/transmissions`,
        {
          method: "POST",
          body: JSON.stringify({
            command_id: makeId(),
            idempotency_key: makeId(),
            package_id: packageId,
            ...input,
          }),
        },
      ),
    requestSubmissionSignature: (submissionPackageId: string, expectedPackageVersion: number) =>
      request<SubmissionSignatureReceipt>(
        `/api/v1/patron/submission-packages/${encodeURIComponent(submissionPackageId)}/signatures`,
        {
          method: "POST",
          body: JSON.stringify({
            command_id: makeId(),
            idempotency_key: makeId(),
            signature_id: makeId(),
            expected_package_version: expectedPackageVersion,
          }),
        },
      ),
    getSubmissionSignature: (signatureId: string) =>
      request<SubmissionSignatureProjection>(
        `/api/v1/patron/submission-signatures/${encodeURIComponent(signatureId)}`,
      ),
    recordSubmissionEvidence: (
      submissionPackageId: string,
      input: {
        evidence_type: "MANUAL_RECEIPT" | "MANUAL_PORTAL_REFERENCE";
        external_reference_hash: string;
        evidence_sha256: string;
        notes_redacted?: string;
      },
    ) =>
      request<SubmissionEvidenceReceipt>(
        `/api/v1/patron/submission-packages/${encodeURIComponent(submissionPackageId)}/evidence`,
        {
          method: "POST",
          body: JSON.stringify({
            command_id: makeId(),
            idempotency_key: makeId(),
            evidence_id: makeId(),
            ...input,
          }),
        },
      ),
    createDraft: (caseId: string) =>
      request<CommandReceipt>(
        `/api/v1/patron/cases/${encodeURIComponent(caseId)}/financial-reports/drafts`,
        {
          method: "POST",
          body: JSON.stringify({
            command_id: makeId(),
            idempotency_key: makeId(),
            currency_code: "EUR",
            ruleset_version: 1,
          }),
        },
      ),
    getDraft: (caseId: string, reportId: string) =>
      request<DraftReport>(
        `/api/v1/patron/cases/${encodeURIComponent(caseId)}/financial-reports/${encodeURIComponent(reportId)}/draft`,
      ),
    addLine: (
      caseId: string,
      reportId: string,
      input: {
        category: FinancialCategory;
        label: string;
        quantity_decimal: string;
        unit: string;
        amount_minor: number;
        expected_revision: number;
      },
    ) =>
      request<CommandReceipt>(
        `/api/v1/patron/cases/${encodeURIComponent(caseId)}/financial-reports/${encodeURIComponent(reportId)}/lines`,
        {
          method: "POST",
          body: JSON.stringify({
            command_id: makeId(),
            idempotency_key: makeId(),
            expected_revision: input.expected_revision,
            category: input.category,
            label: input.label,
            quantity_decimal: input.quantity_decimal,
            unit: input.unit,
            amount_minor: input.amount_minor,
          }),
        },
      ),
  };
}
