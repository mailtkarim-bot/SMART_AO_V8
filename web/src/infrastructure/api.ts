import type {
  AssignedCase,
  CommandReceipt,
  DraftReport,
  FinancialCategory,
} from "../shared/types";

const makeId = () => crypto.randomUUID();

export type ApiClient = ReturnType<typeof createApiClient>;

export function createApiClient(baseUrl: string, token: string) {
  const root = baseUrl.replace(/\/$/, "");

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (init.body) headers.set("Content-Type", "application/json");
    if (token.trim()) headers.set("Authorization", `Bearer ${token.trim()}`);

    const response = await fetch(`${root}${path}`, { ...init, headers });
    const body = await response.text();
    const parsed = body ? JSON.parse(body) : undefined;
    if (!response.ok) {
      const error = new Error(
        typeof parsed?.detail === "string"
          ? parsed.detail
          : `La requête a échoué (${response.status}).`,
      ) as Error & { status?: number; detail?: string };
      error.status = response.status;
      error.detail = parsed?.detail;
      throw error;
    }
    return parsed as T;
  }

  return {
    listAssignedCases: () => request<AssignedCase[]>("/api/v1/cases/assigned"),
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
