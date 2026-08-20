import type { Dispatch, SetStateAction } from "react";

export type SubmissionEvidenceForm = {
  evidence_type: "MANUAL_RECEIPT" | "MANUAL_PORTAL_REFERENCE";
  external_reference_hash: string;
  evidence_sha256: string;
  notes_redacted: string;
};

type SubmissionPanelProps = {
  preparationPackageId: string;
  preparationRevision: string;
  submissionPackageId: string;
  submissionExported: boolean;
  evidenceForm: SubmissionEvidenceForm;
  setPreparationPackageId: Dispatch<SetStateAction<string>>;
  setPreparationRevision: Dispatch<SetStateAction<string>>;
  setSubmissionPackageId: Dispatch<SetStateAction<string>>;
  setEvidenceForm: Dispatch<SetStateAction<SubmissionEvidenceForm>>;
  onPrepare: () => void;
  onExport: () => void;
  onRecordEvidence: () => void;
};

export function SubmissionPanel({
  preparationPackageId,
  preparationRevision,
  submissionPackageId,
  submissionExported,
  evidenceForm,
  setPreparationPackageId,
  setPreparationRevision,
  setSubmissionPackageId,
  setEvidenceForm,
  onPrepare,
  onExport,
  onRecordEvidence,
}: SubmissionPanelProps) {
  return (
    <section className="section-block submission-section" id="submission-section">
      <div className="section-heading">
        <div>
          <span className="section-kicker">PRÉPARATION & DÉPÔT</span>
          <h2>Contrôler le paquet et conserver la preuve</h2>
        </div>
        <span className="secure-pill">
          <span className="status-dot" />Dépôt externe non effectué
        </span>
      </div>
      <div className="submission-grid">
        <div className="detail-panel">
          <div className="panel-heading">
            <div>
              <h3>Préparer le paquet</h3>
              <p>La préparation est une commande patronale révisée et idempotente.</p>
            </div>
          </div>
          <label>
            <span>Identifiant de préparation</span>
            <input
              value={preparationPackageId}
              onChange={(event) => setPreparationPackageId(event.target.value)}
              placeholder="UUID du package de préparation"
            />
          </label>
          <label>
            <span>Révision attendue</span>
            <input
              type="number"
              min="1"
              step="1"
              value={preparationRevision}
              onChange={(event) => setPreparationRevision(event.target.value)}
            />
          </label>
          <button className="primary-button" type="button" onClick={onPrepare}>
            Préparer le paquet <span>→</span>
          </button>
          {submissionPackageId && (
            <>
              <button className="secondary-button" type="button" onClick={onExport}>
                Exporter le dossier ZIP <span>↓</span>
              </button>
              {submissionExported && <span className="rule-tag">Export audité</span>}
            </>
          )}
        </div>
        <div className="detail-panel">
          <div className="panel-heading">
            <div>
              <h3>Preuve manuelle</h3>
              <p>Le registre conserve seulement des références et des hashes redigés.</p>
            </div>
          </div>
          <label>
            <span>Identifiant du paquet</span>
            <input
              value={submissionPackageId}
              onChange={(event) => setSubmissionPackageId(event.target.value)}
              placeholder="UUID du paquet de dépôt"
            />
          </label>
          <label>
            <span>Type de preuve</span>
            <select
              value={evidenceForm.evidence_type}
              onChange={(event) =>
                setEvidenceForm({
                  ...evidenceForm,
                  evidence_type: event.target.value as SubmissionEvidenceForm["evidence_type"],
                })
              }
            >
              <option value="MANUAL_RECEIPT">Accusé manuel</option>
              <option value="MANUAL_PORTAL_REFERENCE">Référence portail manuelle</option>
            </select>
          </label>
          <label>
            <span>Hash de référence externe</span>
            <input
              pattern="[0-9a-f]{64}"
              required
              value={evidenceForm.external_reference_hash}
              onChange={(event) =>
                setEvidenceForm({ ...evidenceForm, external_reference_hash: event.target.value })
              }
              placeholder="64 caractères hexadécimaux"
            />
          </label>
          <label>
            <span>SHA-256 de la preuve</span>
            <input
              pattern="[0-9a-f]{64}"
              required
              value={evidenceForm.evidence_sha256}
              onChange={(event) =>
                setEvidenceForm({ ...evidenceForm, evidence_sha256: event.target.value })
              }
              placeholder="64 caractères hexadécimaux"
            />
          </label>
          <label>
            <span>Notes expurgées</span>
            <textarea
              rows={2}
              maxLength={1000}
              value={evidenceForm.notes_redacted}
              onChange={(event) =>
                setEvidenceForm({ ...evidenceForm, notes_redacted: event.target.value })
              }
              placeholder="Aucune donnée sensible"
            />
          </label>
          <button className="primary-button" type="button" onClick={onRecordEvidence}>
            Enregistrer la preuve <span>→</span>
          </button>
          <small className="invariant-note">
            Invariant serveur : <strong>external_submission: NOT_PERFORMED</strong>.
          </small>
        </div>
      </div>
    </section>
  );
}
