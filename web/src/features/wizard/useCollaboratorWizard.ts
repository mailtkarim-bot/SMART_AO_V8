import { useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import type { ApiClient } from "../../infrastructure/api";
import type {
  CollaboratorTask,
  CollaboratorTaskWorkflow,
  CreateInformationRequestInput,
  DeclareTaskBlockerInput,
  RecordInformationResponseInput,
  ResolveTaskBlockerInput,
  PreparationPackage,
} from "../../shared/types";

type Message = { tone: "success" | "error" | "warning"; text: string };
type SetMessage = Dispatch<SetStateAction<Message | null>>;
type WizardOutcome = "RECORDED" | "NOT_APPLICABLE" | "UNABLE_TO_COMPLETE";

export function useCollaboratorWizard(api: ApiClient, setMessage: SetMessage) {
  const [wizardCaseId, setWizardCaseId] = useState("");
  const [wizardPackageId, setWizardPackageId] = useState("");
  const [wizardPackage, setWizardPackage] = useState<PreparationPackage | null>(null);
  const [wizardTasks, setWizardTasks] = useState<CollaboratorTask[]>([]);
  const [wizardTaskId, setWizardTaskId] = useState("");
  const [wizardResultText, setWizardResultText] = useState("");
  const [wizardOutcome, setWizardOutcome] = useState<WizardOutcome>("RECORDED");
  const [wizardSnapshotId, setWizardSnapshotId] = useState("");
  const [wizardTransmissionId, setWizardTransmissionId] = useState("");
  const [wizardPreviewDocumentId, setWizardPreviewDocumentId] = useState<string | null>(null);
  const [wizardPreviewContent, setWizardPreviewContent] = useState<string | null>(null);
  const [wizardDocumentBusy, setWizardDocumentBusy] = useState(false);
  const [wizardTaskWorkflow, setWizardTaskWorkflow] = useState<CollaboratorTaskWorkflow | null>(null);

  async function loadCollaboratorWizard(notify = true) {
    if (!wizardPackageId.trim() || !wizardCaseId.trim()) {
      setMessage({ tone: "error", text: "Renseignez l’affaire et le package de préparation collaborateur." });
      return;
    }
    try {
      const [packageResult, taskResult] = await Promise.all([
        api.getCollaboratorPreparation(wizardPackageId.trim()),
        api.listCollaboratorTasks(wizardCaseId.trim()),
      ]);
      setWizardPackage(packageResult);
      setWizardTasks(taskResult.tasks);
      if (!wizardTaskId && taskResult.tasks[0]) setWizardTaskId(taskResult.tasks[0].task_id);
      if (notify) {
        setMessage({ tone: "success", text: "Wizard collaborateur chargé depuis les projections serveur." });
      }
    } catch (error) {
      setWizardPackage(null);
      setWizardTasks([]);
      if (notify) {
        setMessage({
          tone: "error",
          text: error instanceof Error ? error.message : "Impossible de charger le wizard collaborateur.",
        });
      }
    }
  }

  async function refreshCollaboratorWizard() {
    if (wizardPackageId.trim() && wizardCaseId.trim()) await loadCollaboratorWizard(false);
  }

  async function evaluateWizardReadiness() {
    if (!wizardPackage) return;
    try {
      await api.evaluatePreparationReadiness(wizardPackage.case_id, {
        package_id: wizardPackage.package_id,
        assignment_id: wizardPackage.assignment_id,
        dce_version_id: wizardPackage.dce_version_id,
        expected_revision: wizardPackage.aggregate_revision,
      });
      setMessage({ tone: "success", text: "Complétude recalculée. Les blocages restent opposables au serveur." });
      await refreshCollaboratorWizard();
    } catch (error) {
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "La vérification de complétude a échoué.",
      });
    }
  }

  async function generateWizardDocument() {
    if (!wizardPackage?.latest_readiness) return;
    try {
      await api.generateTechnicalDocument(wizardPackage.package_id, {
        expected_revision: wizardPackage.aggregate_revision,
        readiness_revision: wizardPackage.latest_readiness.revision,
      });
      setMessage({ tone: "success", text: "Génération documentaire demandée avec contrôle de complétude." });
      await refreshCollaboratorWizard();
    } catch (error) {
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "La génération documentaire a échoué.",
      });
    }
  }

  async function loadWizardTaskWorkflow(taskId = wizardTaskId) {
    if (!taskId) return;
    try {
      setWizardTaskWorkflow(await api.getCollaboratorTaskWorkflow(taskId));
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Impossible de charger le workflow." });
    }
  }

  async function createWizardInformationRequest(input: CreateInformationRequestInput) {
    if (!wizardTaskId) return;
    try {
      await api.createInformationRequest(wizardTaskId, input);
      await loadWizardTaskWorkflow();
      setMessage({ tone: "success", text: "Demande d’information créée." });
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Impossible de créer la demande." });
    }
  }

  async function recordWizardInformationResponse(requestId: string, input: RecordInformationResponseInput) {
    try {
      await api.recordInformationResponse(requestId, input);
      await loadWizardTaskWorkflow();
      setMessage({ tone: "success", text: "Réponse à la demande enregistrée." });
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Impossible d’enregistrer la réponse." });
    }
  }

  async function declareWizardTaskBlocker(input: DeclareTaskBlockerInput) {
    if (!wizardTaskId) return;
    try {
      await api.declareTaskBlocker(wizardTaskId, input);
      await loadWizardTaskWorkflow();
      await refreshCollaboratorWizard();
      setMessage({ tone: "success", text: "Bloqueur déclaré et opposable." });
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Impossible de déclarer le bloqueur." });
    }
  }

  async function resolveWizardTaskBlocker(blockerId: string, input: ResolveTaskBlockerInput) {
    if (!wizardTaskId) return;
    try {
      await api.resolveTaskBlocker(wizardTaskId, blockerId, input);
      await loadWizardTaskWorkflow();
      await refreshCollaboratorWizard();
      setMessage({ tone: "success", text: "Bloqueur résolu." });
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Impossible de résoudre le bloqueur." });
    }
  }

  async function previewWizardDocument(documentId: string) {
    if (!wizardPackage) return;
    setWizardDocumentBusy(true);
    try {
      const blob = await api.getGeneratedDocumentContent(wizardPackage.package_id, documentId);
      setWizardPreviewDocumentId(documentId);
      setWizardPreviewContent(await blob.text());
    } catch (error) {
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Impossible de prévisualiser le document.",
      });
    } finally {
      setWizardDocumentBusy(false);
    }
  }

  async function downloadWizardDocument(documentId: string) {
    if (!wizardPackage) return;
    setWizardDocumentBusy(true);
    try {
      const blob = await api.getGeneratedDocumentContent(wizardPackage.package_id, documentId, true);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "document-genere.md";
      anchor.click();
      URL.revokeObjectURL(url);
      setMessage({ tone: "success", text: "Document généré téléchargé." });
    } catch (error) {
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Impossible de télécharger le document.",
      });
    } finally {
      setWizardDocumentBusy(false);
    }
  }

  async function claimWizardTask() {
    const task = wizardTasks.find((item) => item.task_id === wizardTaskId);
    if (!task) return;
    try {
      await api.claimCollaboratorTask(task.task_id, task.aggregate_revision);
      setMessage({ tone: "success", text: "Tâche prise en charge." });
      await refreshCollaboratorWizard();
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "La prise en charge a échoué." });
    }
  }

  async function recordWizardTaskResult() {
    const task = wizardTasks.find((item) => item.task_id === wizardTaskId);
    if (!task || !wizardResultText.trim()) return;
    try {
      await api.recordCollaboratorTaskResult(task.task_id, {
        expected_revision: task.aggregate_revision,
        result_text: wizardResultText.trim(),
        outcome: wizardOutcome,
      });
      setWizardResultText("");
      setMessage({ tone: "success", text: "Résultat structuré enregistré." });
      await refreshCollaboratorWizard();
    } catch (error) {
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Le résultat n’a pas été enregistré.",
      });
    }
  }

  async function completeWizardTask() {
    const task = wizardTasks.find((item) => item.task_id === wizardTaskId);
    if (!task) return;
    try {
      await api.completeCollaboratorTask(task.task_id, task.aggregate_revision);
      setMessage({ tone: "success", text: "Tâche clôturée avec révision optimiste." });
      await refreshCollaboratorWizard();
    } catch (error) {
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "La clôture de la tâche a échoué.",
      });
    }
  }

  async function transmitWizardSnapshot() {
    if (!wizardPackage || !wizardSnapshotId.trim() || !wizardTransmissionId.trim()) return;
    try {
      await api.transmitPreparationSnapshot(wizardPackage.package_id, {
        snapshot_id: wizardSnapshotId.trim(),
        transmission_id: wizardTransmissionId.trim(),
        expected_package_revision: wizardPackage.aggregate_revision,
      });
      setMessage({
        tone: "success",
        text: "Snapshot transmis au patron. Aucun dépôt externe n’est effectué par cette action.",
      });
      await refreshCollaboratorWizard();
    } catch (error) {
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "La transmission du snapshot a échoué.",
      });
    }
  }

  return {
    wizardCaseId,
    wizardPackageId,
    wizardPackage,
    wizardTasks,
    wizardTaskId,
    wizardResultText,
    wizardOutcome,
    wizardSnapshotId,
    wizardTransmissionId,
    wizardPreviewDocumentId,
    wizardPreviewContent,
    wizardDocumentBusy,
    wizardTaskWorkflow,
    setWizardCaseId,
    setWizardPackageId,
    setWizardTaskId,
    setWizardResultText,
    setWizardOutcome,
    setWizardSnapshotId,
    setWizardTransmissionId,
    previewWizardDocument,
    downloadWizardDocument,
    loadWizardTaskWorkflow,
    createWizardInformationRequest,
    recordWizardInformationResponse,
    declareWizardTaskBlocker,
    resolveWizardTaskBlocker,
    loadCollaboratorWizard,
    refreshCollaboratorWizard,
    evaluateWizardReadiness,
    generateWizardDocument,
    claimWizardTask,
    recordWizardTaskResult,
    completeWizardTask,
    transmitWizardSnapshot,
  };
}
