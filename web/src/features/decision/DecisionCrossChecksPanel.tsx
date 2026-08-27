import type {
  DecisionCctpPricingCrossingItem,
  DecisionDocumentContradictionItem,
} from "../../shared/types";

type DecisionCrossChecksPanelProps = {
  caseId: string;
  crossings: DecisionCctpPricingCrossingItem[];
  contradictions: DecisionDocumentContradictionItem[];
  loading: boolean;
  onRefresh: () => void;
};

function displayValue(value: string | null, fallback: string): string {
  return value?.trim() || fallback;
}

function scoreLabel(scoreBps: number): string {
  return `${(scoreBps / 100).toFixed(0)} %`;
}

export function DecisionCrossChecksPanel({
  caseId,
  crossings,
  contradictions,
  loading,
  onRefresh,
}: DecisionCrossChecksPanelProps) {
  return (
    <section className="section-block decision-section" id="decision-cross-checks-section">
      <div className="section-heading">
        <div>
          <span className="section-kicker">CONTRÔLES AUTOMATIQUES</span>
          <h2>Repérer les incohérences avant de décider</h2>
        </div>
        <div className="top-actions">
          <span className="count-pill">{contradictions.length} contradiction{contradictions.length > 1 ? "s" : ""}</span>
          <button className="secondary-button" type="button" onClick={onRefresh} disabled={!caseId || loading}>
            {loading ? "Chargement…" : "Actualiser"}
          </button>
        </div>
      </div>
      {!caseId ? (
        <div className="empty-card"><strong>Aucune affaire sélectionnée</strong><p>Sélectionnez une affaire pour lancer les contrôles croisés.</p></div>
      ) : crossings.length === 0 && contradictions.length === 0 && !loading ? (
        <div className="empty-card"><strong>Aucune incohérence détectée</strong><p>Les projections sont vides ou aucun contrôle n’est actuellement disponible pour cette affaire.</p></div>
      ) : (
        <div className="decision-grid">
          <div className="detail-panel">
            <div className="panel-heading"><div><h3>CCTP ↔ DPGF / BPU</h3><p>Candidats normalisés, vérifiables côté patron.</p></div><span className="count-pill">{crossings.length}</span></div>
            {crossings.length === 0 ? <p className="panel-empty">Aucun croisement candidat.</p> : (
              <div className="source-list" aria-label="Croisements CCTP pricing">
                {crossings.map((item) => (
                  <div className="source-row" key={`${item.batch_id}-${item.row_number}-${item.source_fragment_id}`}>
                    <strong>{item.document_kind} · ligne {item.row_number} · score {scoreLabel(item.match_score_bps)}</strong>
                    <span>{displayValue(item.code, "Code absent")} · {displayValue(item.designation, "Désignation absente")}</span>
                    <small>{item.source_locator_label} · {displayValue(item.unit, "Unité absente")} · {item.verification_status}</small>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="detail-panel">
            <div className="panel-heading"><div><h3>Contradictions à revoir</h3><p>Détection déterministe ; aucune conclusion juridique automatique.</p></div><span className="count-pill">{contradictions.length}</span></div>
            {contradictions.length === 0 ? <p className="panel-empty">Aucune contradiction à examiner.</p> : (
              <div className="source-list" aria-label="Contradictions documentaires">
                {contradictions.map((item) => (
                  <div className="source-row" key={item.contradiction_id}>
                    <strong>{item.contradiction_type}</strong>
                    <span>{item.related_document_kind} · ligne {item.related_row_number} · {displayValue(item.related_code, "Code absent")}</span>
                    <small>{item.source_locator_label} · {item.comparison_basis} · {item.verification_status}</small>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
