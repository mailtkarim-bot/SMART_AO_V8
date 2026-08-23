import type {
  AssignedCase,
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

export type ApiClient = ReturnType<typeof createApiClient>;

type TokenRefreshListener = (session: AuthSession) => void;

export function createApiClient(
  baseUrl: string,
  token: string,
  onTokenRefreshed?: TokenRefreshListener,
) {
  const root = baseUrl.replace(/\/$/, "");
  let currentToken = token;
  let refreshPromise: Promise<AuthSession | null> | null = null;

  async function refreshSession(): Promise<AuthSession | null> {
    if (refreshPromise) return refreshPromise;
    refreshPromise = (async () => {
      const csrfToken = readCookie("smart_ao_csrf");
      if (!csrfToken) return null;
      const response = await fetch(`${root}/api/v1/auth/refresh`, {
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

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (init.body && !(init.body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
    }
    if (currentToken.trim()) {
      headers.set("Authorization", `Bearer ${currentToken.trim()}`);
    }

    const response = await fetch(`${root}${path}`, {
      ...init,
      credentials: "include",
      headers,
    });
    const parsed = await parseResponseBody(response);
    const canRetry = response.status === 401 && path !== "/api/v1/auth/me" &&
      path !== "/api/v1/auth/login" && path !== "/api/v1/auth/refresh" &&
      path !== "/api/v1/auth/logout" &&
      (init.body === undefined || typeof init.body === "string");
    if (canRetry && await refreshSession()) {
      return request<T>(path, init);
    }
    if (!response.ok) {
      throw apiError(response.status, parsed);
    }
    return parsed as T;
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
    getDecisionDossier: (caseId: string) =>
      request<PatronDecisionDossier>(
        `/api/v1/patron/cases/${encodeURIComponent(caseId)}/decision-dossier`,
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
    uploadEnterpriseDocumentContent: async (
      companyId: string,
      uploadId: string,
      file: File,
    ): Promise<EnterpriseUploadReceipt> => {
      const headers = new Headers();
      headers.set("Accept", "application/json");
      headers.set("Idempotency-Key", makeId());
      if (currentToken.trim()) headers.set("Authorization", `Bearer ${currentToken.trim()}`);
      const response = await fetch(
        `${root}/api/v1/patron/enterprise/companies/${encodeURIComponent(companyId)}/documents/uploads/${encodeURIComponent(uploadId)}/content`,
        { method: "PUT", headers, body: file, credentials: "include" },
      );
      const parsed = await parseResponseBody(response);
      if (!response.ok) {
        throw new Error(
          responseDetail(parsed) ?? `Le téléversement a échoué (${response.status}).`,
        );
      }
      return parsed as EnterpriseUploadReceipt;
    },
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
      const headers = new Headers({ Accept: "application/json" });
      if (currentToken.trim()) headers.set("Authorization", `Bearer ${currentToken.trim()}`);
      const query = new URLSearchParams({ document_kind: documentKind });
      return fetch(
        `${root}/api/v1/patron/cases/${encodeURIComponent(caseId)}/pricing-import/preview?${query}`,
        {
          method: "POST",
          headers: new Headers({
            ...Object.fromEntries(headers.entries()),
            "X-Command-Id": makeId(),
            "Idempotency-Key": makeId(),
          }),
          body: form,
          credentials: "include",
        },
      ).then(async (response) => {
        const parsed = await parseResponseBody(response);
        if (!response.ok) throw apiError(response.status, parsed);
        return parsed as PricingImportPreview;
      });
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
    downloadSubmissionPackage: async (submissionPackageId: string): Promise<Blob> => {
      const headers = new Headers({ Accept: "application/zip" });
      if (currentToken.trim()) headers.set("Authorization", `Bearer ${currentToken.trim()}`);
      const response = await fetch(
        `${root}/api/v1/patron/submission-packages/${encodeURIComponent(submissionPackageId)}/export`,
        { headers, credentials: "include" },
      );
      if (!response.ok) {
        const body = await response.text();
        let detail: string | undefined;
        try {
          detail = body ? (JSON.parse(body) as { detail?: string }).detail : undefined;
        } catch {
          detail = undefined;
        }
        throw new Error(detail ?? `L’export a échoué (${response.status}).`);
      }
      return response.blob();
    },
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
