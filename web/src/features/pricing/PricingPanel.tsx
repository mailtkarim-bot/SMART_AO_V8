import type { ChangeEvent, Dispatch, SetStateAction } from "react";

import type { PricingImportBatchRead, PricingScenario } from "../../shared/types";
import type {
  PricingImportReloadState,
  PricingImportState,
} from "./usePricingImport";

type PricingPanelProps = {
  scenarios: PricingScenario[];
  formatMoney: (minor: number, currency?: string) => string;
  selectedCaseId: string;
  reportId: string;
  pricingImportBatchId: string;
  pricingImportBatchRevision: string;
  pricingImportReportRevision: string;
  pricingImportState: PricingImportState;
  pricingImportPreview: PricingImportBatchRead | null;
  pricingImportReloadState: PricingImportReloadState;
  pricingImportUploading: boolean;
  pricingImportLoading: boolean;
  pricingImportSubmitting: boolean;
  setPricingImportBatchId: Dispatch<SetStateAction<string>>;
  setPricingImportBatchRevision: Dispatch<SetStateAction<string>>;
  setPricingImportReportRevision: Dispatch<SetStateAction<string>>;
  onPreview: (file: File) => void;
  onReload: () => void;
  onCommit: () => void;
};

export function PricingPanel({
  scenarios,
  formatMoney,
  selectedCaseId,
  reportId,
  pricingImportBatchId,
  pricingImportBatchRevision,
  pricingImportReportRevision,
  pricingImportState,
  pricingImportPreview,
  pricingImportReloadState,
  pricingImportUploading,
  pricingImportLoading,
  pricingImportSubmitting,
  setPricingImportBatchId,
  setPricingImportBatchRevision,
  setPricingImportReportRevision,
  onPreview,
  onReload,
  onCommit,
}: PricingPanelProps) {
  return (
    <>
      <div className="section-heading enterprise-pricing-heading">
        <div>
          <span className="section-kicker">SCÉNARIOS PRIVÉS</span>
          <h2>Options de prix</h2>
        </div>
        <span className="count-pill">
          {scenarios.length} scénario{scenarios.length > 1 ? "s" : ""}
        </span>
      </div>
      {scenarios.length === 0 ? (
        <div className="empty-card">
          <strong>Aucun scénario chargé</strong>
          <p>Sélectionnez une affectation patronale pour consulter les scénarios privés autorisés.</p>
        </div>
      ) : (
        <div className="summary-grid">
          {scenarios.slice(0, 4).map((scenario) => (
            <div className="summary-card green" key={scenario.scenario_id}>
              <span>
                {scenario.scenario_key} · v{scenario.version}
              </span>
              <strong>{formatMoney(scenario.gross_margin_minor)}</strong>
              <small>
                Marge {(scenario.gross_margin_rate_bps / 100).toFixed(1)} % · {scenario.state}
              </small>
            </div>
          ))}
        </div>
      )}
      <div className="detail-panel import-commit-panel">
        <div className="panel-heading">
          <div>
            <h3>Importer dans le brouillon</h3>
            <p>Seules les lignes validées du batch DPGF/BPU/Excel sont appliquées, côté patron.</p>
          </div>
          <span className={`state-badge state-${pricingImportState.toLowerCase()}`}>
            {pricingImportState === "IDLE" ? "PRÊT" : pricingImportState}
          </span>
        </div>
        <div className="import-commit-grid">
          <label>
            <span>Fichier DPGF/BPU/Excel</span>
            <input
              type="file"
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              disabled={pricingImportUploading || !selectedCaseId}
              onChange={(event: ChangeEvent<HTMLInputElement>) => {
                const file = event.target.files?.[0];
                if (file) onPreview(file);
                event.target.value = "";
              }}
            />
          </label>
          <button
            className="secondary-button"
            type="button"
            onClick={onReload}
            disabled={pricingImportLoading || !selectedCaseId || !pricingImportBatchId.trim()}
          >
            {pricingImportLoading ? "Lecture…" : "Relire le batch"}
          </button>
          <label>
            <span>Batch d’import validé</span>
            <input
              value={pricingImportBatchId}
              onChange={(event) => setPricingImportBatchId(event.target.value)}
              placeholder="UUID du batch PREVIEWED"
            />
          </label>
          <label>
            <span>Révision du batch</span>
            <input
              type="number"
              min="1"
              step="1"
              value={pricingImportBatchRevision}
              onChange={(event) => setPricingImportBatchRevision(event.target.value)}
            />
          </label>
          <label>
            <span>Révision du brouillon</span>
            <input
              type="number"
              min="0"
              step="1"
              value={pricingImportReportRevision}
              onChange={(event) => setPricingImportReportRevision(event.target.value)}
            />
          </label>
          <button
            className="primary-button"
            type="button"
            onClick={onCommit}
            disabled={
              pricingImportSubmitting ||
              !selectedCaseId ||
              !reportId.trim() ||
              !pricingImportBatchId.trim()
            }
          >
            {pricingImportSubmitting ? "Commit en cours…" : "Commiter les lignes validées"} <span>→</span>
          </button>
        </div>
        {pricingImportPreview && (
          <div className="import-preview-summary">
            <strong>
              {pricingImportPreview.document_kind} · {pricingImportPreview.state} ·{" "}
              {pricingImportPreview.row_count} ligne{pricingImportPreview.row_count > 1 ? "s" : ""}
            </strong>
            <span>
              {pricingImportPreview.valid_row_count} valide
              {pricingImportPreview.valid_row_count > 1 ? "s" : ""}
              {pricingImportPreview.error_count > 0
                ? ` · ${pricingImportPreview.error_count} erreur${pricingImportPreview.error_count > 1 ? "s" : ""}`
                : ""}
            </span>
            {pricingImportPreview.rows.slice(0, 5).map((row) => (
              <div className="import-preview-row" key={row.row_number}>
                <span>
                  #{row.row_number} · {row.designation ?? "Ligne sans désignation"}
                </span>
                <span>{row.errors.length ? row.errors.join(", ") : "Valide"}</span>
              </div>
            ))}
          </div>
        )}
        <small className="invariant-note">
          Le serveur verrouille le batch et le brouillon, refuse les erreurs, applique l’idempotence
          et ne retourne aucun montant dans ce receipt.
        </small>
        {pricingImportReloadState === "FAILED" && (
          <small className="invariant-note warning">
            Commit confirmé. Rechargez le brouillon pour resynchroniser l’affichage.
          </small>
        )}
      </div>
    </>
  );
}
