import { useState } from "react";

import type {
  StructuredRiskProjection,
  TransitionStructuredRiskTreatmentInput,
} from "../../shared/types";

type RiskDraft = Omit<TransitionStructuredRiskTreatmentInput, "expected_revision" | "evidence_locator"> & {
  evidence_locator: string;
};

type DecisionRisksPanelProps = {
  caseId: string;
  risks: StructuredRiskProjection[];
  loading: boolean;
  transitioningRiskId: string | null;
  canManage?: boolean;
  onRefresh: () => void;
  onTransition: (
    risk: StructuredRiskProjection,
    input: Omit<TransitionStructuredRiskTreatmentInput, "expected_revision">
  ) => void;
};

const defaultDraft = (): RiskDraft => ({
  to_treatment: "MITIGATED",
  evidence_excerpt: "",
  evidence_locator: "{}",
  evidence_start_byte_offset: 0,
  evidence_end_byte_offset: 1,
  rationale: "",
});

function treatmentLabel(treatment: StructuredRiskProjection["treatment"]): string {
  return treatment === "OPEN" ? "Ouvert" : treatment === "ACCEPTED" ? "Accepté" : "Mitigé";
}

function severityLabel(severity: StructuredRiskProjection["severity"]): string {
  return { LOW: "Faible", MEDIUM: "Moyen", HIGH: "Élevé", CRITICAL: "Critique" }[severity];
}

export function DecisionRisksPanel({
  caseId,
  risks,
  loading,
  transitioningRiskId,
  canManage = false,
  onRefresh,
  onTransition,
}: DecisionRisksPanelProps) {
  const [drafts, setDrafts] = useState<Record<string, RiskDraft>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  function draftFor(riskId: string): RiskDraft {
    return drafts[riskId] ?? defaultDraft();
  }

  function updateDraft(riskId: string, patch: Partial<RiskDraft>) {
    setDrafts((current) => ({ ...current, [riskId]: { ...draftFor(riskId), ...patch } }));
    setErrors((current) => ({ ...current, [riskId]: "" }));
  }

  function submit(risk: StructuredRiskProjection) {
    const draft = draftFor(risk.risk_id);
    try {
      const locator = JSON.parse(draft.evidence_locator) as Record<string, unknown>;
      if (!locator || Array.isArray(locator) || typeof locator !== "object") {
        throw new Error("Le locator doit être un objet JSON.");
      }
      if (draft.evidence_end_byte_offset <= draft.evidence_start_byte_offset) {
        throw new Error("La fin de preuve doit être strictement supérieure au début.");
      }
      if (!draft.evidence_excerpt.trim() || !draft.rationale.trim()) {
        throw new Error("La preuve et la justification sont obligatoires.");
      }
      setErrors((current) => ({ ...current, [risk.risk_id]: "" }));
      onTransition(risk, {
        to_treatment: draft.to_treatment,
        evidence_excerpt: draft.evidence_excerpt.trim(),
        evidence_locator: locator,
        evidence_start_byte_offset: draft.evidence_start_byte_offset,
        evidence_end_byte_offset: draft.evidence_end_byte_offset,
        rationale: draft.rationale.trim(),
      });
    } catch (error) {
      setErrors((current) => ({
        ...current,
        [risk.risk_id]: error instanceof Error ? error.message : "Preuve invalide.",
      }));
    }
  }

  return (
    <section className="section-block decision-section" id="decision-risks-section">
      <div className="section-heading">
        <div>
          <span className="section-kicker">REGISTRE DE RISQUES</span>
          <h2>Traiter les risques sur preuve</h2>
        </div>
        <div className="top-actions">
          <span className="count-pill">{risks.length} risque{risks.length > 1 ? "s" : ""}</span>
          <button className="secondary-button" type="button" onClick={onRefresh} disabled={!caseId || loading}>
            {loading ? "Chargement…" : "Actualiser"}
          </button>
        </div>
      </div>

      {!caseId ? (
        <div className="empty-card"><strong>Aucune affaire sélectionnée</strong><p>Sélectionnez une affaire pour afficher les risques référencés.</p></div>
      ) : risks.length === 0 && !loading ? (
        <div className="empty-card"><strong>Aucun risque structuré référencé</strong><p>Les risques apparaissent ici lorsqu’ils sont enregistrés et référencés dans le contexte Decision gelé.</p></div>
      ) : (
        <div className="decision-grid">
          {risks.map((risk) => {
            const draft = draftFor(risk.risk_id);
            const busy = transitioningRiskId === risk.risk_id;
            return (
              <article className="detail-panel" key={risk.risk_id}>
                <div className="panel-heading">
                  <div>
                    <h3>{risk.risk_code} · {risk.title}</h3>
                    <p>{risk.category} · {risk.risk_id.slice(0, 8)} · révision {risk.revision}</p>
                  </div>
                  <span className={`state-badge state-${risk.treatment.toLowerCase()}`}>{treatmentLabel(risk.treatment)}</span>
                </div>
                <div className="decision-facts">
                  <span><small>Gravité</small><strong>{severityLabel(risk.severity)}</strong></span>
                  <span><small>Probabilité</small><strong>{risk.likelihood}</strong></span>
                  <span><small>Échéance</small><strong>{risk.due_at ? new Date(risk.due_at).toLocaleDateString("fr-FR") : "Non fixée"}</strong></span>
                </div>
                {risk.latest_treatment_evidence && (
                  <blockquote>
                    <strong>Dernier traitement</strong><br />
                    {risk.latest_treatment_evidence.rationale}<br />
                    <small>{risk.latest_treatment_evidence.excerpt}</small>
                  </blockquote>
                )}
                {canManage && risk.treatment === "OPEN" ? (
                  <form className="decision-form" onSubmit={(event) => { event.preventDefault(); submit(risk); }}>
                    <h4>Enregistrer le traitement</h4>
                    <label>Décision
                      <select value={draft.to_treatment} onChange={(event) => updateDraft(risk.risk_id, { to_treatment: event.target.value as "ACCEPTED" | "MITIGATED" })}>
                        <option value="MITIGATED">Mitigé</option>
                        <option value="ACCEPTED">Accepté</option>
                      </select>
                    </label>
                    <label>Extrait de preuve
                      <textarea value={draft.evidence_excerpt} onChange={(event) => updateDraft(risk.risk_id, { evidence_excerpt: event.target.value })} maxLength={2000} rows={3} required />
                    </label>
                    <label>Locator JSON
                      <input value={draft.evidence_locator} onChange={(event) => updateDraft(risk.risk_id, { evidence_locator: event.target.value })} aria-label={`Locator de preuve ${risk.risk_code}`} spellCheck={false} />
                    </label>
                    <div className="decision-facts">
                      <label>Début byte<input type="number" min={0} value={draft.evidence_start_byte_offset} onChange={(event) => updateDraft(risk.risk_id, { evidence_start_byte_offset: Number(event.target.value) })} /></label>
                      <label>Fin byte<input type="number" min={1} value={draft.evidence_end_byte_offset} onChange={(event) => updateDraft(risk.risk_id, { evidence_end_byte_offset: Number(event.target.value) })} /></label>
                    </div>
                    <label>Justification
                      <textarea value={draft.rationale} onChange={(event) => updateDraft(risk.risk_id, { rationale: event.target.value })} maxLength={2000} rows={3} required />
                    </label>
                    {errors[risk.risk_id] && <p className="form-error" role="alert">{errors[risk.risk_id]}</p>}
                    <button className="primary-button" type="submit" disabled={busy}>{busy ? "Enregistrement…" : "Enregistrer le traitement"}</button>
                  </form>
                ) : (
                  <p className="panel-empty">{risk.treatment === "OPEN" ? "Lecture seule : le traitement est réservé au patron administrateur." : "Traitement finalisé ; une nouvelle transition n’est pas autorisée depuis cet état."}</p>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
