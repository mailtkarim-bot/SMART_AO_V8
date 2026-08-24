import type { ComponentProps } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SubmissionPanel } from "./SubmissionPanel";

type PanelProps = ComponentProps<typeof SubmissionPanel>;

const evidenceForm: PanelProps["evidenceForm"] = {
  evidence_type: "MANUAL_RECEIPT",
  external_reference_hash: "a".repeat(64),
  evidence_sha256: "b".repeat(64),
  notes_redacted: "Preuve de recette expurgée",
};

function renderPanel(overrides: Partial<PanelProps> = {}) {
  const props: PanelProps = {
    preparationPackageId: "preparation-1",
    preparationRevision: "1",
    submissionPackageId: "",
    submissionExported: false,
    signatureId: "",
    signaturePackageVersion: "1",
    signatureStatus: null,
    signatureProvider: "",
    signatureRevision: null,
    evidenceForm,
    setPreparationPackageId: vi.fn(),
    setPreparationRevision: vi.fn(),
    setSubmissionPackageId: vi.fn(),
    setSignatureId: vi.fn(),
    setSignaturePackageVersion: vi.fn(),
    setEvidenceForm: vi.fn(),
    onPrepare: vi.fn(),
    onRequestSignature: vi.fn(),
    onLoadSignature: vi.fn(),
    onExport: vi.fn(),
    onRecordEvidence: vi.fn(),
    ...overrides,
  };
  return { ...render(<SubmissionPanel {...props} />), props };
}

describe("SubmissionPanel integration", () => {
  it("prepares a patron package and keeps external submission explicitly disabled", () => {
    const onPrepare = vi.fn();
    renderPanel({ onPrepare });

    expect(screen.getByText("Dépôt externe non effectué")).toBeInTheDocument();
    expect(screen.getAllByText("external_submission: NOT_PERFORMED")).toHaveLength(2);

    fireEvent.click(screen.getByRole("button", { name: /préparer le paquet/i }));
    expect(onPrepare).toHaveBeenCalledOnce();
    expect(screen.queryByRole("button", { name: /exporter le dossier zip/i })).not.toBeInTheDocument();
  });

  it("reveals the audited export action only after a package exists", () => {
    const onExport = vi.fn();
    const { rerender, props } = renderPanel({
      submissionPackageId: "submission-1",
      submissionExported: true,
      onExport,
    });

    rerender(<SubmissionPanel {...props} submissionPackageId="submission-1" submissionExported />);
    fireEvent.click(screen.getByRole("button", { name: /exporter le dossier zip/i }));

    expect(onExport).toHaveBeenCalledOnce();
    expect(screen.getByText("Export audité")).toBeInTheDocument();
  });

  it("shows a bounded signature status and delegates patron actions", () => {
    const onRequestSignature = vi.fn();
    const onLoadSignature = vi.fn();
    renderPanel({
      signatureId: "signature-1",
      signatureStatus: "SIGNED",
      signatureProvider: "TEST_PROVIDER",
      signatureRevision: 2,
      onRequestSignature,
      onLoadSignature,
    });

    expect(screen.getByText("Signature électronique")).toBeInTheDocument();
    expect(screen.getByText("SIGNED")).toBeInTheDocument();
    expect(screen.getByText("Provider : TEST_PROVIDER")).toBeInTheDocument();
    expect(screen.getByText("Révision signature : 2")).toBeInTheDocument();
    expect(screen.getAllByText("external_submission: NOT_PERFORMED")).toHaveLength(2);
    expect(screen.queryByText(/provider_reference_hash|signature_sha256/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /demander la signature/i }));
    fireEvent.click(screen.getByRole("button", { name: /recharger l’état/i }));
    expect(onRequestSignature).toHaveBeenCalledOnce();
    expect(onLoadSignature).toHaveBeenCalledOnce();
  });

  it("records only the redacted manual evidence action", () => {
    const onRecordEvidence = vi.fn();
    const setEvidenceForm = vi.fn();
    renderPanel({ onRecordEvidence, setEvidenceForm });

    fireEvent.change(screen.getByLabelText("Type de preuve"), {
      target: { value: "MANUAL_PORTAL_REFERENCE" },
    });
    fireEvent.change(screen.getByLabelText("Notes expurgées"), {
      target: { value: "Référence sans données sensibles" },
    });
    fireEvent.click(screen.getByRole("button", { name: /enregistrer la preuve/i }));

    expect(setEvidenceForm).toHaveBeenCalled();
    expect(onRecordEvidence).toHaveBeenCalledOnce();
    expect(screen.getByPlaceholderText("Aucune donnée sensible")).toBeInTheDocument();
  });
});
