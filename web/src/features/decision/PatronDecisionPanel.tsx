import { useState } from "react";
import type {
  FreezeDecisionContextRequest,
  PatronDecisionDossier,
  ResolveDecisionConditionRequest,
} from "../../shared/types";

type PatronDecisionPanelProps = {
  decisionDossier: PatronDecisionDossier | null;
  formatDate: (value: string) => string;
  canManage?: boolean;
  onCreateDecision?: () => void;
  onFreezeContext?: (input: FreezeDecisionContextRequest) => void;
  onResolveCondition?: (conditionId: string, input: ResolveDecisionConditionRequest) => void;
};

const emptyReferences = "[]";

export function PatronDecisionPanel({
  decisionDossier,
  formatDate,
  canManage = false,
  onCreateDecision,
  onFreezeContext,
  onResolveCondition,
}: PatronDecisionPanelProps) {
  const [contextId, setContextId] = useState("");
  const [rationale, setRationale] = useState("");
  const [referencesJson, setReferencesJson] = useState(emptyReferences);
  const [referenceError, setReferenceError] = useState<string | null>(null);
  const [resolutionValues, setResolutionValues] = useState<
    Record<string, { targetStatus: "SATISFIED" | "FAILED"; evidence: string; reason: string }>
  >({});

  function submitFreeze() {
    if (!decisionDossier || !onFreezeContext || !contextId.trim() || !rationale.trim()) return;
    try {
      const references = JSON.parse(referencesJson) as FreezeDecisionContextRequest["references"];
      if (!Array.isArray(references) || references.length === 0) {
        throw new Error("Au moins une référence est obligatoire.");
      }
      setReferenceError(null);
      onFreezeContext({
        context_id: contextId.trim(),
        expected_revision: decisionDossier.aggregate_revision,
        rationale: rationale.trim(),
        references,
      });
    } catch (error) {
      setReferenceError(error instanceof Error ? error.message : "Références JSON invalides.");
    }
  }

  function submitResolution(conditionId: string) {
    const values = resolutionValues[conditionId];
    if (!decisionDossier || !onResolveCondition || !values) return;
    onResolveCondition(conditionId, {
      expected_revision: decisionDossier.aggregate_revision,
      target_status: values.targetStatus,
      evidence_reference: values.targetStatus === "SATISFIED" ? values.evidence.trim() : undefined,
      failure_reason: values.targetStatus === "FAILED" ? values.reason.trim() : undefined,
    });
  }

  function updateResolution(
    conditionId: string,
    patch: Partial<{ targetStatus: "SATISFIED" | "FAILED"; evidence: string; reason: string }>,
  ) {
    setResolutionValues((current) => {
      const existing = current[conditionId] ?? {
        targetStatus: "SATISFIED" as const,
        evidence: "",
        reason: "",
      };
      return {
        ...current,
        [conditionId]: { ...existing, ...patch },
      };
    });
  }

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
          {canManage && onCreateDecision && (
            <button className="primary-button" onClick={onCreateDecision}>
              Créer le brouillon Decision
            </button>
          )}
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
                <small>Révision</small>
                <strong>{decisionDossier.aggregate_revision}</strong>
              </span>
              <span>
                <small>Validité</small>
                <strong>{decisionDossier.validity}</strong>
              </span>
            </div>
            {decisionDossier.final_justification && <blockquote>{decisionDossier.final_justification}</blockquote>}
            {canManage && decisionDossier.lifecycle === "DRAFT" && onFreezeContext && (
              <div className="decision-form">
                <h4>Geler le contexte vérifié</h4>
                <p>
                  Les références sont validées côté serveur. Utilisez des identifiants issus des
                  lectures DCE et Case, jamais des valeurs inventées.
                </p>
                <label>
                  Identifiant du contexte
                  <input value={contextId} onChange={(event) => setContextId(event.target.value)} placeholder="UUID du contexte préparé" />
                </label>
                <label>
                  Justification
                  <textarea value={rationale} onChange={(event) => setRationale(event.target.value)} rows={3} />
                </label>
                <label>
                  Références JSON vérifiables
                  <textarea value={referencesJson} onChange={(event) => setReferencesJson(event.target.value)} rows={5} spellCheck={false} />
                </label>
                {referenceError && <p className="form-error" role="alert">{referenceError}</p>}
                <button className="primary-button" onClick={submitFreeze} disabled={!contextId.trim() || !rationale.trim()}>
                  Geler le contexte
                </button>
              </div>
            )}
            {!canManage && <p className="panel-empty">Lecture seule : la validation Decision est réservée au patron administrateur.</p>}
          </div>
          <div className="detail-panel">
            <div className="panel-heading">
              <div>
                <h3>Points de vigilance</h3>
                <p>Les éléments restent issus du read model serveur.</p>
              </div>
            </div>
            <div className="decision-list">
              <div><strong>Inconnus</strong><span>{decisionDossier.unknowns.length}</span></div>
              <div><strong>Risques</strong><span>{decisionDossier.risks.length}</span></div>
              <div><strong>Conditions</strong><span>{decisionDossier.conditions.length}</span></div>
            </div>
            <div className="decision-json">
              {[...decisionDossier.unknowns.slice(0, 3), ...decisionDossier.risks.slice(0, 3)].map((item, index) => (
                <pre key={index}>{JSON.stringify(item, null, 2)}</pre>
              ))}
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
                {decisionDossier.conditions.map((condition) => {
                  const values = resolutionValues[condition.condition_id] ?? {
                    targetStatus: "SATISFIED" as const,
                    evidence: "",
                    reason: "",
                  };
                  return (
                    <div className="condition-row" key={condition.condition_id}>
                      <span className={`state-badge state-${condition.status.toLowerCase()}`}>{condition.status}</span>
                      <div>
                        <strong>{condition.label}</strong>
                        <small>{condition.failure_consequence}{condition.due_at ? ` · Échéance ${formatDate(condition.due_at)}` : ""}</small>
                        {canManage && condition.status === "OPEN" && onResolveCondition && (
                          <div className="decision-form condition-form">
                            <select value={values.targetStatus} onChange={(event) => updateResolution(condition.condition_id, { targetStatus: event.target.value as "SATISFIED" | "FAILED" })}>
                              <option value="SATISFIED">Satisfaite</option>
                              <option value="FAILED">Échouée</option>
                            </select>
                            {values.targetStatus === "SATISFIED" ? (
                              <input value={values.evidence} onChange={(event) => updateResolution(condition.condition_id, { evidence: event.target.value })} placeholder="Référence de preuve" />
                            ) : (
                              <input value={values.reason} onChange={(event) => updateResolution(condition.condition_id, { reason: event.target.value })} placeholder="Motif d’échec" />
                            )}
                            <button className="secondary-button" onClick={() => submitResolution(condition.condition_id)}>
                              Enregistrer
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
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
                  <div className="source-row" key={`${source.aggregate_type}-${source.aggregate_id}`}>
                    <strong>{source.aggregate_type}</strong>
                    <span>{source.role} · Révision {source.aggregate_revision}</span>
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
