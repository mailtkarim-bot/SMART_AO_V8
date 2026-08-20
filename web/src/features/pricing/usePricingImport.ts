import { useEffect, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import type { ApiClient } from "../../infrastructure/api";

type Message = { tone: "success" | "error" | "warning"; text: string };
type SetMessage = Dispatch<SetStateAction<Message | null>>;
export type PricingImportState = "IDLE" | "COMMITTED" | "REPLAYED";
export type PricingImportReloadState = "NOT_ATTEMPTED" | "SUCCEEDED" | "FAILED";

type PricingImportActions = {
  pricingImportBatchId: string;
  pricingImportBatchRevision: string;
  pricingImportReportRevision: string;
  pricingImportState: PricingImportState;
  pricingImportReloadState: PricingImportReloadState;
  pricingImportSubmitting: boolean;
  setPricingImportBatchId: Dispatch<SetStateAction<string>>;
  setPricingImportBatchRevision: Dispatch<SetStateAction<string>>;
  setPricingImportReportRevision: Dispatch<SetStateAction<string>>;
  commitPricingImport: () => Promise<void>;
};

export function usePricingImport(
  api: ApiClient,
  setMessage: SetMessage,
  reportId: string,
  selectedCaseId: string,
  onDraftReload: () => Promise<void>,
): PricingImportActions {
  const [pricingImportBatchId, setPricingImportBatchId] = useState("");
  const [pricingImportBatchRevision, setPricingImportBatchRevision] = useState("1");
  const [pricingImportReportRevision, setPricingImportReportRevision] = useState("0");
  const [pricingImportState, setPricingImportState] = useState<PricingImportState>("IDLE");
  const [pricingImportReloadState, setPricingImportReloadState] =
    useState<PricingImportReloadState>("NOT_ATTEMPTED");
  const [pricingImportSubmitting, setPricingImportSubmitting] = useState(false);

  useEffect(() => {
    setPricingImportState("IDLE");
  }, [selectedCaseId, reportId, pricingImportBatchId]);

  async function commitPricingImport() {
    if (pricingImportSubmitting) return;
    if (!selectedCaseId || !pricingImportBatchId.trim() || !reportId.trim()) {
      setMessage({ tone: "error", text: "Sélectionnez une affaire, un batch et un brouillon avant le commit." });
      return;
    }
    const expectedBatchRevision = Number(pricingImportBatchRevision);
    const expectedReportRevision = Number(pricingImportReportRevision);
    if (
      !Number.isInteger(expectedBatchRevision) ||
      expectedBatchRevision < 1 ||
      !Number.isInteger(expectedReportRevision) ||
      expectedReportRevision < 0
    ) {
      setMessage({ tone: "error", text: "Les révisions attendues doivent être des entiers valides." });
      return;
    }
    setPricingImportSubmitting(true);
    setPricingImportReloadState("NOT_ATTEMPTED");
    try {
      const receipt = await api.commitPricingImport(selectedCaseId, pricingImportBatchId.trim(), {
        report_id: reportId.trim(),
        expected_batch_revision: expectedBatchRevision,
        expected_report_revision: expectedReportRevision,
      });
      const reportReference = receipt.aggregate_refs.find(
        (reference) => reference.aggregate_type === "FinancialReportSnapshot",
      );
      const batchReference = receipt.aggregate_refs.find(
        (reference) => reference.aggregate_type === "PricingImportBatch",
      );
      if (reportReference) setPricingImportReportRevision(String(reportReference.aggregate_revision));
      if (batchReference) setPricingImportBatchRevision(String(batchReference.aggregate_revision));
      setPricingImportState(receipt.replayed ? "REPLAYED" : "COMMITTED");
      setMessage({
        tone: "success",
        text: receipt.replayed
          ? "Import déjà commité : rejeu idempotent sans nouvelle ligne."
          : "Import commité dans le brouillon financier patronal.",
      });
      try {
        await onDraftReload();
        setPricingImportReloadState("SUCCEEDED");
      } catch {
        setPricingImportReloadState("FAILED");
        setMessage({
          tone: "warning",
          text: "Import confirmé, mais le brouillon n’a pas pu être rechargé. Relancez sa lecture.",
        });
      }
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Le commit de l’import a échoué." });
    } finally {
      setPricingImportSubmitting(false);
    }
  }

  return {
    pricingImportBatchId,
    pricingImportBatchRevision,
    pricingImportReportRevision,
    pricingImportState,
    pricingImportReloadState,
    pricingImportSubmitting,
    setPricingImportBatchId,
    setPricingImportBatchRevision,
    setPricingImportReportRevision,
    commitPricingImport,
  };
}
