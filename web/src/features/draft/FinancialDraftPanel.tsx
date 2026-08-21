import type { Dispatch, FormEvent, SetStateAction } from "react";

import type { AssignedCase, DraftReport, FinancialCategory } from "../../shared/types";
import type { FinancialLineForm } from "./useFinancialDraft";

type SummaryCard = { label: string; value: string; accent: string };

type FinancialDraftPanelProps = {
  cases: AssignedCase[];
  selectedCaseId: string;
  setSelectedCaseId: Dispatch<SetStateAction<string>>;
  reportId: string;
  setReportId: Dispatch<SetStateAction<string>>;
  draft: DraftReport | null;
  loadingDraft: boolean;
  lineForm: FinancialLineForm;
  setLineForm: Dispatch<SetStateAction<FinancialLineForm>>;
  summaryCards: SummaryCard[];
  createDraft: () => void;
  loadDraft: () => void;
  submitLine: (event: FormEvent<HTMLFormElement>) => void;
  formatMoney: (minor: number, currency: string) => string;
  formatDate: (value: string) => string;
  categoryLabel: (category: FinancialCategory) => string;
};

export function FinancialDraftPanel({
  cases,
  selectedCaseId,
  setSelectedCaseId,
  reportId,
  setReportId,
  draft,
  loadingDraft,
  lineForm,
  setLineForm,
  summaryCards,
  createDraft,
  loadDraft,
  submitLine,
  formatMoney,
  formatDate,
  categoryLabel,
}: FinancialDraftPanelProps) {
  return (
    <section className="section-block draft-section" id="draft-section">
      <div className="section-heading">
        <div>
          <span className="section-kicker">CHIFFRAGE PRIVÉ</span>
          <h2>Brouillon financier</h2>
        </div>
        {draft && (
          <span className="draft-status">
            <span className="status-dot" /> DRAFT · Révision {draft.aggregate_revision}
          </span>
        )}
      </div>
      <div className="draft-toolbar">
        <label>
          <span>Affaire sélectionnée</span>
          <select value={selectedCaseId} onChange={(event) => setSelectedCaseId(event.target.value)}>
            <option value="">Choisir une affaire</option>
            {cases.map((item) => (
              <option key={item.case_id} value={item.case_id}>
                {item.work_label}
              </option>
            ))}
          </select>
        </label>
        <label className="report-input">
          <span>Identifiant du brouillon</span>
          <input
            value={reportId}
            onChange={(event) => setReportId(event.target.value)}
            placeholder="UUID du snapshot DRAFT"
          />
        </label>
        <div className="draft-actions">
          <button className="secondary-button" onClick={createDraft} disabled={loadingDraft} type="button">
            + Nouveau brouillon
          </button>
          <button
            className="primary-button load-button"
            onClick={loadDraft}
            disabled={loadingDraft}
            type="button"
          >
            {loadingDraft ? "Chargement…" : "Lire le brouillon"}
            <span>→</span>
          </button>
        </div>
      </div>
      {draft ? (
        <>
          <div className="summary-grid">
            {summaryCards.map((card) => (
              <div className={`summary-card ${card.accent}`} key={card.label}>
                <span>{card.label}</span>
                <strong>{card.value}</strong>
                <small>
                  {card.label === "Marge brute"
                    ? `${(draft.summary.gross_margin_rate_bps / 100).toFixed(1)} % du chiffre d’affaires`
                    : `Révision ${draft.aggregate_revision}`}
                </small>
              </div>
            ))}
          </div>
          <div className="draft-panel">
            <div className="panel-heading">
              <div>
                <h3>Lignes du brouillon</h3>
                <p>Les montants restent visibles uniquement dans cet espace patron.</p>
              </div>
              <span className="rule-tag">Règleset v{draft.ruleset_version}</span>
            </div>
            <div className="line-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Catégorie</th>
                    <th>Libellé</th>
                    <th>Quantité</th>
                    <th>Unité</th>
                    <th className="amount-column">Montant</th>
                  </tr>
                </thead>
                <tbody>
                  {draft.lines.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="table-empty">
                        Aucune ligne. Ajoutez le premier poste du chiffrage.
                      </td>
                    </tr>
                  ) : (
                    draft.lines.map((line) => (
                      <tr key={line.line_id}>
                        <td>
                          <span className="category-badge">{categoryLabel(line.category)}</span>
                        </td>
                        <td>
                          <strong>{line.label}</strong>
                        </td>
                        <td>{line.quantity_decimal}</td>
                        <td>{line.unit}</td>
                        <td className="amount-column">
                          {formatMoney(line.amount_minor, line.currency_code)}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <form className="add-line-form" onSubmit={submitLine}>
              <div className="form-title">
                <span className="plus-mark">+</span>
                <div>
                  <strong>Ajouter une ligne</strong>
                  <small>La révision courante sera appliquée automatiquement.</small>
                </div>
              </div>
              <label>
                <span>Catégorie</span>
                <select
                  value={lineForm.category}
                  onChange={(event) =>
                    setLineForm({ ...lineForm, category: event.target.value as FinancialCategory })
                  }
                >
                  <option value="SALES">Ventes</option>
                  <option value="DIRECT_COST">Coûts directs</option>
                  <option value="OVERHEAD">Frais généraux</option>
                  <option value="SUBCONTRACTING">Sous-traitance</option>
                  <option value="CONTINGENCY">Aléas</option>
                </select>
              </label>
              <label>
                <span>Libellé</span>
                <input
                  required
                  value={lineForm.label}
                  onChange={(event) => setLineForm({ ...lineForm, label: event.target.value })}
                  placeholder="Ex. étude technique"
                />
              </label>
              <label>
                <span>Quantité</span>
                <input
                  required
                  value={lineForm.quantity_decimal}
                  onChange={(event) =>
                    setLineForm({ ...lineForm, quantity_decimal: event.target.value })
                  }
                />
              </label>
              <label>
                <span>Unité</span>
                <input
                  required
                  value={lineForm.unit}
                  onChange={(event) => setLineForm({ ...lineForm, unit: event.target.value })}
                />
              </label>
              <label>
                <span>Montant (centimes)</span>
                <input
                  required
                  type="number"
                  step="1"
                  value={lineForm.amount_minor}
                  onChange={(event) =>
                    setLineForm({ ...lineForm, amount_minor: event.target.value })
                  }
                  placeholder="125000"
                />
              </label>
              <button className="primary-button add-button" type="submit">
                Ajouter <span>→</span>
              </button>
            </form>
            <div className="last-updated">
              Dernière lecture serveur : {formatDate(draft.calculated_at)} · Aucun cache local du
              montant
            </div>
          </div>
        </>
      ) : (
        <div className="empty-draft">
          <div className="empty-icon">◫</div>
          <div>
            <strong>Sélectionnez un brouillon pour commencer.</strong>
            <p>
              La lecture est tenant-scopée et ne montre que les snapshots DRAFT autorisés par le
              serveur.
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
