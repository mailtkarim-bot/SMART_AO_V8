import type { FormEvent } from "react";
import type { Dispatch, SetStateAction } from "react";
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ApiClient } from "../../infrastructure/api";
import type { CommandReceipt, DraftReport } from "../../shared/types";
import { useFinancialDraft } from "./useFinancialDraft";

type HookMessage = { tone: "success" | "error" | "warning"; text: string };
type DraftApi = Pick<ApiClient, "createDraft" | "getDraft" | "addLine">;

const receipt = (replayed = false): CommandReceipt => ({
  status: "SUCCEEDED",
  command_id: "command-draft-1",
  idempotency_key: "idempotency-draft-1",
  result_code: "FINANCIAL_REPORT_DRAFT_LINE_ADDED",
  aggregate_refs: [
    {
      aggregate_type: "FinancialReportSnapshot",
      aggregate_id: "report-1",
      aggregate_revision: 3,
    },
  ],
  event_ids: ["event-draft-1"],
  replayed,
});

const draft = (revision = 2): DraftReport => ({
  report_id: "report-1",
  case_id: "case-1",
  status: "DRAFT",
  aggregate_revision: revision,
  currency_code: "EUR",
  calculated_at: "2026-08-20T12:00:00Z",
  ruleset_version: 1,
  summary: {
    sales_total_minor: 0,
    direct_cost_total_minor: 0,
    overhead_total_minor: 0,
    subcontracting_total_minor: 0,
    contingency_total_minor: 0,
    gross_margin_minor: 0,
    gross_margin_rate_bps: 0,
    forecast_cashflow_minor: 0,
  },
  lines: [],
});

function renderDraftHook(
  api: DraftApi,
  setMessage: Dispatch<SetStateAction<HookMessage | null>>,
  selectedCaseId = "case-1",
) {
  return renderHook(() => useFinancialDraft(api as ApiClient, setMessage, selectedCaseId));
}

describe("useFinancialDraft", () => {
  it("requires a selected case before creating a draft", async () => {
    const api = {
      createDraft: vi.fn(),
      getDraft: vi.fn(),
      addLine: vi.fn(),
    } satisfies DraftApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderDraftHook(api, setMessage, "");

    await act(async () => {
      await result.current.createDraft();
    });

    expect(api.createDraft).not.toHaveBeenCalled();
    expect(setMessage).toHaveBeenCalledWith({
      tone: "error",
      text: "Sélectionnez une affaire avant de créer un brouillon.",
    });
  });

  it("creates a draft, stores its report identifier and loads its projection", async () => {
    const api = {
      createDraft: vi.fn().mockResolvedValue(receipt()),
      getDraft: vi.fn().mockResolvedValue(draft()),
      addLine: vi.fn(),
    } satisfies DraftApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderDraftHook(api, setMessage);

    await act(async () => {
      await result.current.createDraft();
    });

    expect(api.createDraft).toHaveBeenCalledWith("case-1");
    expect(api.getDraft).toHaveBeenCalledWith("case-1", "report-1");
    expect(result.current.reportId).toBe("report-1");
    expect(result.current.draft?.aggregate_revision).toBe(2);
    expect(result.current.loadingDraft).toBe(false);
    expect(setMessage).toHaveBeenLastCalledWith({
      tone: "success",
      text: "Nouveau brouillon créé.",
    });
  });

  it("rejects a draft read without a report identifier", async () => {
    const api = {
      createDraft: vi.fn(),
      getDraft: vi.fn(),
      addLine: vi.fn(),
    } satisfies DraftApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderDraftHook(api, setMessage);

    await act(async () => {
      await result.current.loadDraft();
    });

    expect(api.getDraft).not.toHaveBeenCalled();
    expect(setMessage).toHaveBeenCalledWith({
      tone: "error",
      text: "Sélectionnez une affaire et renseignez l’identifiant du brouillon.",
    });
  });

  it("rejects non-integer cent amounts before calling the API", async () => {
    const api = {
      createDraft: vi.fn(),
      getDraft: vi.fn().mockResolvedValue(draft()),
      addLine: vi.fn(),
    } satisfies DraftApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderDraftHook(api, setMessage);

    act(() => {
      result.current.setReportId("report-1");
      result.current.setLineForm((current) => ({ ...current, amount_minor: "12.5", label: "Étude" }));
    });
    await act(async () => {
      await result.current.loadDraft();
    });
    await act(async () => {
      await result.current.submitLine({ preventDefault: vi.fn() } as unknown as FormEvent<HTMLFormElement>);
    });

    expect(api.addLine).not.toHaveBeenCalled();
    expect(setMessage).toHaveBeenLastCalledWith({
      tone: "error",
      text: "Le montant doit être exprimé en centimes entiers.",
    });
  });

  it("adds a line with the current optimistic revision and reloads the draft", async () => {
    const api = {
      createDraft: vi.fn(),
      getDraft: vi.fn().mockResolvedValueOnce(draft()).mockResolvedValueOnce(draft(3)),
      addLine: vi.fn().mockResolvedValue(receipt()),
    } satisfies DraftApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderDraftHook(api, setMessage);

    act(() => {
      result.current.setReportId("report-1");
    });
    await act(async () => {
      await result.current.loadDraft();
    });
    act(() => {
      result.current.setLineForm((current) => ({
        ...current,
        label: "Étude technique",
        quantity_decimal: "2",
        unit: "jour",
        amount_minor: "125000",
      }));
    });
    await act(async () => {
      await result.current.submitLine({ preventDefault: vi.fn() } as unknown as FormEvent<HTMLFormElement>);
    });

    expect(api.addLine).toHaveBeenCalledWith("case-1", "report-1", {
      category: "SALES",
      label: "Étude technique",
      quantity_decimal: "2",
      unit: "jour",
      amount_minor: 125000,
      expected_revision: 2,
    });
    expect(api.getDraft).toHaveBeenCalledTimes(2);
    expect(result.current.draft?.aggregate_revision).toBe(3);
    expect(result.current.lineForm.label).toBe("");
    expect(result.current.lineForm.amount_minor).toBe("");
    expect(setMessage).toHaveBeenCalledWith({
      tone: "success",
      text: "Ligne ajoutée au brouillon.",
    });
  });
});
