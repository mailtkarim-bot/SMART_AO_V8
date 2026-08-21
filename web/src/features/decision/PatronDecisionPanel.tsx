import type { PatronDecisionDossier } from "../../shared/types";

type PatronDecisionPanelProps = {
  decisionDossier: PatronDecisionDossier | null;
  formatDate: (value: string) => string;
};

export function PatronDecisionPanel({ decisionDossier, formatDate }: PatronDecisionPanelProps) {
  return (
    <section className="section-block decision-section" id="decision-section">
      <div className="section-heading">
        <div>
          <span className="section-kicker">DOSSIER DE DÉCISION</span>
          <h2>Décider sur des faits contrôlés</h2>
        </div>
        <span className="count-pill">{decisionDossier?.validity ?? "À charger"}</span>
      </div>
      {!decisionDossier ? (
        <div className="empty-card">
          <strong>Aucun dossier de décision disponible</strong>
          <p>
            Sélectionnez une affaire et actualisez pour projeter le contexte, les inconnus, les
            risques et les conditions autorisées.
          </p>
        </div>
      ) : (
        <div className="decision-grid">
          <div className="detail-panel decision-summary">
            <div className="panel-heading">
              <div>
                <h3>{decisionDossier.decision_type}</h3>
                <p>Affaire {decisionDossier.case_id}</p>
              </div>
              <span className="state-badge state-active">{decisionDossier.outcome}</span>
            </div>
            <div className="decision-facts">
              <span>
                <small>Cycle</small>
                <strong>{decisionDossier.lifecycle}</strong>
              </span>
              <span>
                <small>Contexte</small>
                <strong>{decisionDossier.context_status}</strong>
              </span>
              <span>
                <small>Validité</small>
                <strong>{decisionDossier.validity}</strong>
              </span>
            </div>
            {decisionDossier.final_justification && (
              <blockquote>{decisionDossier.final_justification}</blockquote>
            )}
          </div>
          <div className="detail-panel">
            <div className="panel-heading">
              <div>
                <h3>Points de vigilance</h3>
                <p>Les éléments restent issus du read model serveur.</p>
              </div>
            </div>
            <div className="decision-list">
              <div>
                <strong>Inconnus</strong>
                <span>{decisionDossier.unknowns.length}</span>
              </div>
              <div>
                <strong>Risques</strong>
                <span>{decisionDossier.risks.length}</span>
              </div>
              <div>
                <strong>Conditions</strong>
                <span>{decisionDossier.conditions.length}</span>
              </div>
            </div>
            <div className="decision-json">
              {[...decisionDossier.unknowns.slice(0, 3), ...decisionDossier.risks.slice(0, 3)].map(
                (item, index) => (
                  <pre key={index}>{JSON.stringify(item, null, 2)}</pre>
                ),
              )}
            </div>
          </div>
          <div className="detail-panel">
            <div className="panel-heading">
              <div>
                <h3>Conditions de décision</h3>
                <p>Contrôles à satisfaire avant clôture.</p>
              </div>
            </div>
            {decisionDossier.conditions.length === 0 ? (
              <p className="panel-empty">Aucune condition structurée.</p>
            ) : (
              <div className="condition-list">
                {decisionDossier.conditions.map((condition) => (
                  <div className="condition-row" key={condition.condition_id}>
                    <span className={`state-badge state-${condition.status.toLowerCase()}`}>
                      {condition.status}
                    </span>
                    <div>
                      <strong>{condition.label}</strong>
                      <small>
                        {condition.failure_consequence}
                        {condition.due_at ? ` · Échéance ${formatDate(condition.due_at)}` : ""}
                      </small>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="detail-panel">
            <div className="panel-heading">
              <div>
                <h3>Sources de preuve</h3>
                <p>Références projetées et révisées.</p>
              </div>
            </div>
            {decisionDossier.sources.length === 0 ? (
              <p className="panel-empty">Aucune source référencée.</p>
            ) : (
              <div className="source-list">
                {decisionDossier.sources.map((source) => (
                  <div
                    className="source-row"
                    key={`${source.aggregate_type}-${source.aggregate_id}`}
                  >
                    <strong>{source.aggregate_type}</strong>
                    <span>
                      {source.role} · Révision {source.aggregate_revision}
                    </span>
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
