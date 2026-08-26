import type {
  DecisionPricingReconciliationItem,
  DecisionRiskRequirementLink,
} from "../../shared/types";

type DecisionRiskRequirementsPanelProps = {
  caseId: string;
  links: DecisionRiskRequirementLink[];
  nextCursor: string | null;
  selectedLinkId: string;
  pricingItems: DecisionPricingReconciliationItem[];
  search: string;
  loading: boolean;
  searching: boolean;
  formatDate: (value: string) => string;
  onRefresh: () => void;
  onLoadMore: () => void;
  onSelectLink: (linkId: string) => void;
  onSearchChange: (value: string) => void;
  onReconcilePricing: () => void;
};

function displayValue(value: string | null): string {
  return value?.trim() || "Non renseigné";
}

export function DecisionRiskRequirementsPanel({
  caseId,
  links,
  nextCursor,
  selectedLinkId,
  pricingItems,
  search,
  loading,
  searching,
  formatDate,
  onRefresh,
  onLoadMore,
  onSelectLink,
  onSearchChange,
  onReconcilePricing,
}: DecisionRiskRequirementsPanelProps) {
  const selectedLink = links.find((item) => item.link_id === selectedLinkId) ?? null;

  return (
    <section className="section-block decision-section" id="decision-risk-requirements-section">
      <div className="section-heading">
        <div>
          <span className="section-kicker">CONTRÔLES CROISÉS</span>
          <h2>Risques, exigences et lots candidats</h2>
        </div>
        <div className="top-actions">
          <span className="count-pill">{links.length} lien{links.length > 1 ? "s" : ""}</span>
          <button className="secondary-button" type="button" onClick={onRefresh} disabled={!caseId || loading}>
            {loading ? "Chargement…" : "Actualiser"}
          </button>
        </div>
      </div>

      {!caseId ? (
        <div className="empty-card">
          <strong>Aucune affaire sélectionnée</strong>
          <p>Sélectionnez une affaire pour afficher les rapprochements autorisés.</p>
        </div>
      ) : links.length === 0 && !loading ? (
        <div className="empty-card">
          <strong>Aucun lien risque–exigence projeté</strong>
          <p>Les liens confirmés apparaîtront ici sans exposer de contenu financier.</p>
        </div>
      ) : (
        <div className="decision-grid">
          <div className="detail-panel">
            <div className="panel-heading">
              <div>
                <h3>Liens vérifiés</h3>
                <p>Projection patronale tenant-scoped, triée par création.</p>
              </div>
            </div>
            <div className="source-list" aria-label="Liens risque exigence">
              {links.map((link) => (
                <button
                  className={`source-row ${link.link_id === selectedLinkId ? "selected" : ""}`}
                  key={link.link_id}
                  type="button"
                  onClick={() => onSelectLink(link.link_id)}
                >
                  <strong>{link.relationship}</strong>
                  <span>
                    Risque {link.risk_id.slice(0, 8)} · Exigence {link.requirement_id.slice(0, 8)} · {formatDate(link.created_at)}
                  </span>
                  <small>
                    Action : {displayValue(link.action_state)}
                    {link.action_severity ? ` · ${link.action_severity}` : ""}
                  </small>
                </button>
              ))}
            </div>
            {nextCursor && (
              <button className="secondary-button" type="button" onClick={onLoadMore} disabled={loading}>
                {loading ? "Chargement…" : "Charger la page suivante"}
              </button>
            )}
          </div>

          <div className="detail-panel">
            <div className="panel-heading">
              <div>
                <h3>Rapprochement DPGF / BPU</h3>
                <p>Recherche uniquement dans les lots normalisés et engagés.</p>
              </div>
            </div>
            {!selectedLink ? (
              <p className="panel-empty">Sélectionnez un lien vérifié pour rechercher un candidat.</p>
            ) : (
              <>
                <div className="decision-facts">
                  <span><small>Relation</small><strong>{selectedLink.relationship}</strong></span>
                  <span><small>Version DCE</small><strong>{selectedLink.dce_version_id.slice(0, 8)}</strong></span>
                  <span><small>Action</small><strong>{displayValue(selectedLink.action_state)}</strong></span>
                </div>
                <form
                  className="decision-form condition-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    onReconcilePricing();
                  }}
                >
                  <label>
                    Recherche contrôlée
                    <input
                      value={search}
                      onChange={(event) => onSearchChange(event.target.value)}
                      minLength={2}
                      maxLength={120}
                      placeholder="Code ou désignation"
                      aria-label="Recherche DPGF ou BPU"
                    />
                  </label>
                  <button className="primary-button" type="submit" disabled={search.trim().length < 2 || searching}>
                    {searching ? "Recherche…" : "Rechercher"}
                  </button>
                </form>
                {pricingItems.length === 0 ? (
                  <p className="panel-empty">Aucun candidat affiché pour cette recherche.</p>
                ) : (
                  <div className="source-list" aria-label="Candidats DPGF BPU">
                    {pricingItems.map((item) => (
                      <div className="source-row" key={`${item.batch_id}-${item.row_number}`}>
                        <strong>{item.document_kind} · ligne {item.row_number}</strong>
                        <span>{item.code || "Code absent"} · {item.designation || "Désignation absente"}</span>
                        <small>{item.unit || "Unité absente"} · {item.verification_status}</small>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
