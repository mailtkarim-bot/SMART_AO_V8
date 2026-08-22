import type {
  AssignedCase,
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
} from "../shared/types";

const makeId = () => crypto.randomUUID();

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

export function createApiClient(baseUrl: string, token: string) {
  const root = baseUrl.replace(/\/$/, "");

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (init.body) headers.set("Content-Type", "application/json");
    if (token.trim()) headers.set("Authorization", `Bearer ${token.trim()}`);

    const response = await fetch(`${root}${path}`, { ...init, headers });
    const parsed = await parseResponseBody(response);
    if (!response.ok) {
      const detail = responseDetail(parsed);
      const error = new Error(
        detail ?? `La requête a échoué (${response.status}).`,
      ) as Error & { status?: number; detail?: string };
      error.status = response.status;
      error.detail = detail;
      throw error;
    }
    return parsed as T;
  }

  return {
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
      if (token.trim()) headers.set("Authorization", `Bearer ${token.trim()}`);
      const response = await fetch(
        `${root}/api/v1/patron/enterprise/companies/${encodeURIComponent(companyId)}/documents/uploads/${encodeURIComponent(uploadId)}/content`,
        { method: "PUT", headers, body: file },
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
      if (token.trim()) headers.set("Authorization", `Bearer ${token.trim()}`);
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
        },
      ).then(async (response) => {
        const body = await response.text();
        const parsed = body ? JSON.parse(body) : undefined;
        if (!response.ok) {
          throw new Error(
            typeof parsed?.detail === "string"
              ? parsed.detail
              : `La preview a échoué (${response.status}).`,
          );
        }
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
      if (token.trim()) headers.set("Authorization", `Bearer ${token.trim()}`);
      const response = await fetch(
        `${root}/api/v1/patron/submission-packages/${encodeURIComponent(submissionPackageId)}/export`,
        { headers },
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
