import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { CollaboratorTask, PreparationPackage } from "../../shared/types";
import { CollaboratorWizardPanel } from "./CollaboratorWizardPanel";

const packageProjection: PreparationPackage = {
  package_id: "package-1",
  case_id: "case-1",
  assignment_id: "assignment-1",
  dce_version_id: "dce-1",
  state: "A_REVIEW",
  aggregate_revision: 7,
  latest_readiness: {
    readiness_id: "readiness-1",
    revision: 2,
    state: "READY_WITH_WARNINGS",
    blocker_codes: [],
    warning_codes: ["OPTIONAL_REFERENCE_MISSING"],
    checked_requirement_count: 4,
    checked_task_count: 2,
  },
  generated_documents: [
    {
      document_id: "document-1",
      version: 1,
      document_kind: "TECHNICAL_RESPONSE",
      state: "GENERATED",
      readiness_revision: 2,
    },
  ],
};

const task: CollaboratorTask = {
  task_id: "task-1",
  case_id: "case-1",
  assignment_id: "assignment-1",
  requirement_id: "requirement-1",
  task_kind: "EVIDENCE_COLLECTION",
  title: "Collecter la référence chantier",
  objective: "Structurer la preuve de référence",
  priority: "HIGH",
  state: "OPEN",
  due_at: null,
  aggregate_revision: 4,
};

function renderPanel(
  overrides: Partial<React.ComponentProps<typeof CollaboratorWizardPanel>> = {},
) {
  const props: React.ComponentProps<typeof CollaboratorWizardPanel> = {
    wizardCaseId: "case-1",
    wizardPackageId: "package-1",
    wizardPackage: null,
    wizardTasks: [],
    wizardTaskId: "",
    wizardResultText: "",
    wizardOutcome: "RECORDED",
    wizardSnapshotId: "",
    wizardTransmissionId: "",
    wizardPreviewDocumentId: null,
    wizardPreviewContent: null,
    wizardDocumentBusy: false,
    setWizardCaseId: vi.fn(),
    setWizardPackageId: vi.fn(),
    setWizardTaskId: vi.fn(),
    setWizardResultText: vi.fn(),
    setWizardOutcome: vi.fn(),
    setWizardSnapshotId: vi.fn(),
    setWizardTransmissionId: vi.fn(),
    onLoad: vi.fn(),
    onClaimTask: vi.fn(),
    onRecordResult: vi.fn(),
    onCompleteTask: vi.fn(),
    onEvaluateReadiness: vi.fn(),
    onGenerateDocument: vi.fn(),
    onTransmitSnapshot: vi.fn(),
    onPreviewDocument: vi.fn(),
    onDownloadDocument: vi.fn(),
    ...overrides,
  };
  return render(<CollaboratorWizardPanel {...props} />);
}

describe("CollaboratorWizardPanel", () => {
  it("renders the non-financial empty state and delegates loading", () => {
    const onLoad = vi.fn();
    renderPanel({ onLoad });

    expect(screen.getByText("Le wizard est prêt à être chargé")).toBeInTheDocument();
    expect(screen.getByText(/Aucune donnée financière n’est exposée ici/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Charger le wizard/ }));
    expect(onLoad).toHaveBeenCalledTimes(1);
  });

  it("renders readiness, generated document and task controls from server projections", () => {
    renderPanel({
      wizardPackage: packageProjection,
      wizardTasks: [task],
      wizardTaskId: "task-1",
    });

    expect(screen.getByText("Collecter la référence chantier")).toBeInTheDocument();
    expect(screen.getAllByText("READY_WITH_WARNINGS")).toHaveLength(2);
    expect(screen.getByText("OPTIONAL_REFERENCE_MISSING")).toBeInTheDocument();
    expect(screen.getByText("TECHNICAL_RESPONSE")).toBeInTheDocument();
    expect(screen.getByText("Enregistrer le résultat")).toBeInTheDocument();
  });

  it("delegates document preview and download actions", () => {
    const onPreviewDocument = vi.fn();
    const onDownloadDocument = vi.fn();
    renderPanel({
      wizardPackage: packageProjection,
      onPreviewDocument,
      onDownloadDocument,
    });

    fireEvent.click(screen.getByRole("button", { name: "Aperçu" }));
    fireEvent.click(screen.getByRole("button", { name: "Télécharger" }));

    expect(onPreviewDocument).toHaveBeenCalledWith("document-1");
    expect(onDownloadDocument).toHaveBeenCalledWith("document-1");
  });

  it("renders the selected document preview without exposing storage metadata", () => {
    renderPanel({
      wizardPackage: packageProjection,
      wizardPreviewDocumentId: "document-1",
      wizardPreviewContent: "# Réponse technique\n\nContenu contrôlé",
    });

    expect(screen.getByRole("heading", { name: "Aperçu du document sélectionné" })).toBeInTheDocument();
    expect(screen.getByText(/# Réponse technique/)).toBeInTheDocument();
    expect(screen.queryByText(/storage_key|content_sha256/)).not.toBeInTheDocument();
  });

  it("delegates task, readiness and transmission actions without external deposit semantics", () => {
    const onClaimTask = vi.fn();
    const onRecordResult = vi.fn();
    const onCompleteTask = vi.fn();
    const onEvaluateReadiness = vi.fn();
    const onGenerateDocument = vi.fn();
    const onTransmitSnapshot = vi.fn();
    renderPanel({
      wizardPackage: packageProjection,
      wizardTasks: [task],
      wizardTaskId: "task-1",
      onClaimTask,
      onRecordResult,
      onCompleteTask,
      onEvaluateReadiness,
      onGenerateDocument,
      onTransmitSnapshot,
    });

    fireEvent.click(screen.getByRole("button", { name: "Prendre en charge" }));
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer le résultat" }));
    fireEvent.click(screen.getByRole("button", { name: "Clôturer" }));
    fireEvent.click(screen.getByRole("button", { name: "Vérifier la complétude" }));
    fireEvent.click(screen.getByRole("button", { name: "Générer la réponse technique" }));
    fireEvent.click(screen.getByRole("button", { name: /Transmettre au patron/ }));

    expect(onClaimTask).toHaveBeenCalledTimes(1);
    expect(onRecordResult).toHaveBeenCalledTimes(1);
    expect(onCompleteTask).toHaveBeenCalledTimes(1);
    expect(onEvaluateReadiness).toHaveBeenCalledTimes(1);
    expect(onGenerateDocument).toHaveBeenCalledTimes(1);
    expect(onTransmitSnapshot).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/ne dépose jamais le dossier sur un portail externe/)).toBeInTheDocument();
  });
});
