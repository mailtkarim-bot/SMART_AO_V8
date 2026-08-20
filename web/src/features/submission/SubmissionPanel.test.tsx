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
    evidenceForm,
    setPreparationPackageId: vi.fn(),
    setPreparationRevision: vi.fn(),
    setSubmissionPackageId: vi.fn(),
    setEvidenceForm: vi.fn(),
    onPrepare: vi.fn(),
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
    expect(screen.getByText("external_submission: NOT_PERFORMED")).toBeInTheDocument();

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
