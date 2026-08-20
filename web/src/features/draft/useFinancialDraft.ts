import type { FormEvent } from "react";
import { useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import type { ApiClient } from "../../infrastructure/api";
import type { DraftReport, FinancialCategory } from "../../shared/types";

type Message = { tone: "success" | "error" | "warning"; text: string };
type SetMessage = Dispatch<SetStateAction<Message | null>>;

type LineForm = {
  category: FinancialCategory;
  label: string;
  quantity_decimal: string;
  unit: string;
  amount_minor: string;
};

const initialLineForm: LineForm = {
  category: "SALES",
  label: "",
  quantity_decimal: "1",
  unit: "forfait",
  amount_minor: "",
};

export function useFinancialDraft(
  api: ApiClient,
  setMessage: SetMessage,
  selectedCaseId: string,
) {
  const [reportId, setReportId] = useState("");
  const [draft, setDraft] = useState<DraftReport | null>(null);
  const [loadingDraft, setLoadingDraft] = useState(false);
  const [lineForm, setLineForm] = useState<LineForm>(initialLineForm);

  async function createDraft() {
    if (!selectedCaseId) {
      setMessage({ tone: "error", text: "Sélectionnez une affaire avant de créer un brouillon." });
      return;
    }
    setLoadingDraft(true);
    setMessage(null);
    try {
      const receipt = await api.createDraft(selectedCaseId);
      const newReportId = receipt.aggregate_refs[0]?.aggregate_id;
      if (!newReportId) throw new Error("Le serveur n’a pas retourné l’identifiant du brouillon.");
      setReportId(newReportId);
      const loadedDraft = await api.getDraft(selectedCaseId, newReportId);
      setDraft(loadedDraft);
      setMessage({
        tone: "success",
        text: receipt.replayed ? "Brouillon existant rechargé." : "Nouveau brouillon créé.",
      });
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Impossible de créer le brouillon." });
    } finally {
      setLoadingDraft(false);
    }
  }

  async function loadDraft() {
    if (!selectedCaseId || !reportId.trim()) {
      setMessage({ tone: "error", text: "Sélectionnez une affaire et renseignez l’identifiant du brouillon." });
      return;
    }
    setLoadingDraft(true);
    setMessage(null);
    try {
      const loadedDraft = await api.getDraft(selectedCaseId, reportId.trim());
      setDraft(loadedDraft);
      setMessage({ tone: "success", text: "Brouillon chargé en lecture seule contrôlée." });
    } catch (error) {
      setDraft(null);
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Impossible de charger le brouillon." });
    } finally {
      setLoadingDraft(false);
    }
  }

  async function submitLine(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft || !selectedCaseId) return;
    const amount = Number(lineForm.amount_minor);
    if (!Number.isInteger(amount)) {
      setMessage({ tone: "error", text: "Le montant doit être exprimé en centimes entiers." });
      return;
    }
    try {
      const receipt = await api.addLine(selectedCaseId, draft.report_id, {
        ...lineForm,
        amount_minor: amount,
        expected_revision: draft.aggregate_revision,
      });
      setMessage({
        tone: "success",
        text: receipt.replayed ? "Ajout rejoué sans doublon." : "Ligne ajoutée au brouillon.",
      });
      setLineForm((current) => ({ ...current, label: "", amount_minor: "" }));
      await loadDraft();
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "L’ajout de la ligne a échoué." });
    }
  }

  return {
    reportId,
    draft,
    loadingDraft,
    lineForm,
    setReportId,
    setLineForm,
    createDraft,
    loadDraft,
    submitLine,
  };
}
