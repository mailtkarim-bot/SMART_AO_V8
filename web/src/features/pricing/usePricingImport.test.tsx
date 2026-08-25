import type { Dispatch, SetStateAction } from "react";
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ApiClient } from "../../infrastructure/api";
import type {
  PricingImportBatchRead,
  PricingImportCommitReceipt,
  PricingImportPreview,
} from "../../shared/types";
import { usePricingImport } from "./usePricingImport";

type HookMessage = { tone: "success" | "error" | "warning"; text: string };
type PricingApi = Partial<Pick<
  ApiClient,
  "commitPricingImport" | "createPricingImportPreview" | "getPricingImport"
>>;

const preview = (overrides: Partial<PricingImportPreview> = {}): PricingImportPreview => ({
  batch_id: "batch-2",
  case_id: "case-1",
  document_kind: "EXCEL",
  state: "PREVIEWED",
  aggregate_revision: 1,
  row_count: 2,
  valid_row_count: 2,
  error_count: 0,
  total_minor: 32500,
  rows: [],
  filename: "pricing.xlsx",
  truncated: false,
  limit_reason: null,
  result_code: "PRICING_IMPORT_PREVIEWED",
  command_id: "command-preview",
  idempotency_key: "idempotency-preview",
  event_ids: ["event-preview"],
  replayed: false,
  ...overrides,
});

const receipt = (replayed = false): PricingImportCommitReceipt => ({
  status: "SUCCEEDED",
  command_id: "command-1",
  idempotency_key: "idempotency-1",
  result_code: "PRICING_IMPORT_COMMITTED",
  aggregate_refs: [
    {
      aggregate_type: "FinancialReportSnapshot",
      aggregate_id: "report-1",
      aggregate_revision: 4,
    },
    {
      aggregate_type: "PricingImportBatch",
      aggregate_id: "batch-1",
      aggregate_revision: 3,
    },
  ],
  event_ids: ["event-1"],
  replayed,
});

function renderPricingHook(
  api: PricingApi,
  setMessage: Dispatch<SetStateAction<HookMessage | null>>,
  onDraftReload: () => Promise<void> = vi.fn().mockResolvedValue(undefined),
) {
  return renderHook(() =>
    usePricingImport(
      api as ApiClient,
      setMessage,
      "report-1",
      "case-1",
      onDraftReload,
    ),
  );
}

function setBatch(result: { current: ReturnType<typeof usePricingImport> }) {
  act(() => {
    result.current.setPricingImportBatchId(" batch-1 ");
  });
}

describe("usePricingImport", () => {
  it("persists an uploaded preview and exposes its batch revision", async () => {
    const api = {
      createPricingImportPreview: vi.fn().mockResolvedValue(preview()),
    } satisfies PricingApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderPricingHook(api, setMessage);
    const file = new File(["xlsx"], "pricing.xlsx");

    await act(async () => {
      await result.current.previewPricingImport(file);
    });

    expect(api.createPricingImportPreview).toHaveBeenCalledWith("case-1", file);
    expect(result.current.pricingImportBatchId).toBe("batch-2");
    expect(result.current.pricingImportBatchRevision).toBe("1");
    expect(result.current.pricingImportState).toBe("PREVIEWED");
    expect(result.current.pricingImportPreview?.total_minor).toBe(32500);
  });

  it("warns the patron when the preview hit a safety budget and was truncated", async () => {
    const api = {
      createPricingImportPreview: vi.fn().mockResolvedValue(
        preview({ truncated: true, limit_reason: "ROW_LIMIT" }),
      ),
    } satisfies PricingApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderPricingHook(api, setMessage);
    const file = new File(["xlsx"], "pricing.xlsx");

    await act(async () => {
      await result.current.previewPricingImport(file);
    });

    expect(result.current.pricingImportState).toBe("PREVIEWED");
    const mockSetMessage = setMessage as unknown as { mock: { calls: [HookMessage][] } };
    const message = mockSetMessage.mock.calls.at(-1)?.[0] ?? null;
    expect(message?.tone).toBe("warning");
    expect(message?.text).toContain("limite de lignes");
  });

  it("reloads a persisted batch and reflects its committed state", async () => {
    const committed: PricingImportBatchRead = {
      ...preview(),
      state: "COMMITTED",
      aggregate_revision: 2,
    };
    const api = {
      getPricingImport: vi.fn().mockResolvedValue(committed),
    } satisfies PricingApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderPricingHook(api, setMessage);
    setBatch(result);

    await act(async () => {
      await result.current.reloadPricingImport();
    });

    expect(api.getPricingImport).toHaveBeenCalledWith("case-1", "batch-1");
    expect(result.current.pricingImportState).toBe("COMMITTED");
    expect(result.current.pricingImportBatchRevision).toBe("2");
  });

  it("rejects a commit without a batch", async () => {
    const api = { commitPricingImport: vi.fn() } satisfies PricingApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderPricingHook(api, setMessage);

    await act(async () => {
      await result.current.commitPricingImport();
    });

    expect(api.commitPricingImport).not.toHaveBeenCalled();
    expect(setMessage).toHaveBeenCalledWith({
      tone: "error",
      text: "Sélectionnez une affaire, un batch et un brouillon avant le commit.",
    });
  });

  it("commits validated rows, updates revisions and confirms reload", async () => {
    const api = { commitPricingImport: vi.fn().mockResolvedValue(receipt()) } satisfies PricingApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const onDraftReload = vi.fn().mockResolvedValue(undefined);
    const { result } = renderPricingHook(api, setMessage, onDraftReload);
    setBatch(result);

    await act(async () => {
      await result.current.commitPricingImport();
    });

    expect(api.commitPricingImport).toHaveBeenCalledWith("case-1", "batch-1", {
      report_id: "report-1",
      expected_batch_revision: 1,
      expected_report_revision: 0,
    });
    expect(onDraftReload).toHaveBeenCalledOnce();
    expect(result.current.pricingImportState).toBe("COMMITTED");
    expect(result.current.pricingImportReloadState).toBe("SUCCEEDED");
    expect(result.current.pricingImportBatchRevision).toBe("3");
    expect(result.current.pricingImportReportRevision).toBe("4");
    expect(result.current.pricingImportSubmitting).toBe(false);
  });

  it("keeps the commit confirmed when reload fails", async () => {
    const api = { commitPricingImport: vi.fn().mockResolvedValue(receipt()) } satisfies PricingApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const onDraftReload = vi.fn().mockRejectedValue(new Error("reload unavailable"));
    const { result } = renderPricingHook(api, setMessage, onDraftReload);
    setBatch(result);

    await act(async () => {
      await result.current.commitPricingImport();
    });

    expect(result.current.pricingImportState).toBe("COMMITTED");
    expect(result.current.pricingImportReloadState).toBe("FAILED");
    expect(setMessage).toHaveBeenLastCalledWith({
      tone: "warning",
      text: "Import confirmé, mais le brouillon n’a pas pu être rechargé. Relancez sa lecture.",
    });
  });

  it("reports an idempotent replay without changing the business outcome", async () => {
    const api = { commitPricingImport: vi.fn().mockResolvedValue(receipt(true)) } satisfies PricingApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderPricingHook(api, setMessage);
    setBatch(result);

    await act(async () => {
      await result.current.commitPricingImport();
    });

    expect(result.current.pricingImportState).toBe("REPLAYED");
    expect(setMessage).toHaveBeenCalledWith({
      tone: "success",
      text: "Import déjà commité : rejeu idempotent sans nouvelle ligne.",
    });
  });

  it("ignores a second invocation while the first commit is pending", async () => {
    let release!: (value: PricingImportCommitReceipt) => void;
    const pending = new Promise<PricingImportCommitReceipt>((resolve) => {
      release = resolve;
    });
    const api = { commitPricingImport: vi.fn().mockReturnValue(pending) } satisfies PricingApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderPricingHook(api, setMessage);
    setBatch(result);

    let firstCommit!: Promise<void>;
    await act(async () => {
      firstCommit = result.current.commitPricingImport();
      await Promise.resolve();
    });
    expect(result.current.pricingImportSubmitting).toBe(true);

    await act(async () => {
      await result.current.commitPricingImport();
    });
    expect(api.commitPricingImport).toHaveBeenCalledOnce();

    release(receipt());
    await act(async () => {
      await firstCommit;
    });
    expect(result.current.pricingImportSubmitting).toBe(false);
  });

  it("resets the visible state when the pricing context changes", async () => {
    const api = { commitPricingImport: vi.fn().mockResolvedValue(receipt()) } satisfies PricingApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const onDraftReload = vi.fn().mockResolvedValue(undefined);
    const { result, rerender } = renderHook(
      ({ caseId, reportId }) =>
        usePricingImport(api as unknown as ApiClient, setMessage, reportId, caseId, onDraftReload),
      { initialProps: { caseId: "case-1", reportId: "report-1" } },
    );
    setBatch(result);

    await act(async () => {
      await result.current.commitPricingImport();
    });
    expect(result.current.pricingImportState).toBe("COMMITTED");

    rerender({ caseId: "case-2", reportId: "report-2" });
    expect(result.current.pricingImportState).toBe("IDLE");
  });
});
