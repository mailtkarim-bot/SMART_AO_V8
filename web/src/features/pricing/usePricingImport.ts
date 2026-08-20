import { useEffect, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import type { ApiClient } from "../../infrastructure/api";

type Message = { tone: "success" | "error"; text: string };
type SetMessage = Dispatch<SetStateAction<Message | null>>;
export type PricingImportState = "IDLE" | "COMMITTED" | "REPLAYED";

type PricingImportActions = {
  pricingImportBatchId: string;
  pricingImportBatchRevision: string;
  pricingImportReportRevision: string;
  pricingImportState: PricingImportState;
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

  useEffect(() => {
    setPricingImportState("IDLE");
  }, [selectedCaseId, reportId, pricingImportBatchId]);

  async function commitPricingImport() {
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
      await onDraftReload();
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Le commit de l’import a échoué." });
    }
  }

  return {
    pricingImportBatchId,
    pricingImportBatchRevision,
    pricingImportReportRevision,
    pricingImportState,
    setPricingImportBatchId,
    setPricingImportBatchRevision,
    setPricingImportReportRevision,
    commitPricingImport,
  };
}
