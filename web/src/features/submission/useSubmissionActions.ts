import { useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import type { ApiClient } from "../../infrastructure/api";
import type { SubmissionEvidenceForm } from "./SubmissionPanel";

type Message = { tone: "success" | "error"; text: string };
type SetMessage = Dispatch<SetStateAction<Message | null>>;

type SubmissionActions = {
  preparationPackageId: string;
  preparationRevision: string;
  submissionPackageId: string;
  submissionExported: boolean;
  evidenceForm: SubmissionEvidenceForm;
  setPreparationPackageId: Dispatch<SetStateAction<string>>;
  setPreparationRevision: Dispatch<SetStateAction<string>>;
  setSubmissionPackageId: Dispatch<SetStateAction<string>>;
  setEvidenceForm: Dispatch<SetStateAction<SubmissionEvidenceForm>>;
  prepareSubmissionPackage: () => Promise<void>;
  exportSubmissionPackage: () => Promise<void>;
  recordSubmissionEvidence: () => Promise<void>;
};

export function useSubmissionActions(api: ApiClient, setMessage: SetMessage): SubmissionActions {
  const [preparationPackageId, setPreparationPackageId] = useState("");
  const [preparationRevision, setPreparationRevision] = useState("1");
  const [submissionPackageId, setSubmissionPackageId] = useState("");
  const [submissionExported, setSubmissionExported] = useState(false);
  const [evidenceForm, setEvidenceForm] = useState<SubmissionEvidenceForm>({
    evidence_type: "MANUAL_RECEIPT",
    external_reference_hash: "",
    evidence_sha256: "",
    notes_redacted: "",
  });

  async function prepareSubmissionPackage() {
    if (!preparationPackageId.trim()) {
      setMessage({ tone: "error", text: "Renseignez l’identifiant de la préparation à déposer." });
      return;
    }
    try {
      const receipt = await api.prepareSubmissionPackage(
        preparationPackageId.trim(),
        Number(preparationRevision),
      );
      const packageId = receipt.aggregate_refs[0]?.aggregate_id;
      if (packageId) setSubmissionPackageId(packageId);
      setMessage({
        tone: "success",
        text: receipt.replayed
          ? "Paquet de dépôt déjà préparé, identifiant rechargé."
          : "Paquet préparé pour contrôle patronal. Aucun dépôt externe n’a été effectué.",
      });
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Impossible de préparer le paquet." });
    }
  }

  async function exportSubmissionPackage() {
    if (!submissionPackageId.trim()) {
      setMessage({ tone: "error", text: "Préparez ou renseignez un paquet avant de l’exporter." });
      return;
    }
    try {
      const archive = await api.downloadSubmissionPackage(submissionPackageId.trim());
      const url = URL.createObjectURL(archive);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `submission-${submissionPackageId.trim()}.zip`;
      anchor.click();
      URL.revokeObjectURL(url);
      setSubmissionExported(true);
      setMessage({ tone: "success", text: "Dossier exporté. L’audit et la notification de téléchargement ont été enregistrés." });
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Impossible d’exporter le dossier." });
    }
  }

  async function recordSubmissionEvidence() {
    if (!submissionPackageId.trim()) {
      setMessage({ tone: "error", text: "Préparez ou renseignez un paquet avant d’enregistrer sa preuve." });
      return;
    }
    try {
      const receipt = await api.recordSubmissionEvidence(submissionPackageId.trim(), {
        ...evidenceForm,
        notes_redacted: evidenceForm.notes_redacted || undefined,
      });
      setMessage({
        tone: "success",
        text: receipt.external_submission === "NOT_PERFORMED"
          ? "Preuve append-only enregistrée. Le dépôt externe reste à effectuer manuellement."
          : "Preuve enregistrée.",
      });
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Impossible d’enregistrer la preuve." });
    }
  }

  return {
    preparationPackageId,
    preparationRevision,
    submissionPackageId,
    submissionExported,
    evidenceForm,
    setPreparationPackageId,
    setPreparationRevision,
    setSubmissionPackageId,
    setEvidenceForm,
    prepareSubmissionPackage,
    exportSubmissionPackage,
    recordSubmissionEvidence,
  };
}
