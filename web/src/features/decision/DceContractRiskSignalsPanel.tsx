import { useState } from "react";

import type {
  DceContractRiskSignal,
  RegisterStructuredRiskInput,
  StructuredRiskLikelihood,
  StructuredRiskSeverity,
} from "../../shared/types";

type SignalDraft = {
  title: string;
  statement: string;
  severity: StructuredRiskSeverity;
  likelihood: StructuredRiskLikelihood;
  sourceExcerpt: string;
  sourceLocator: string;
  dueAt: string;
};

type DceContractRiskSignalsPanelProps = {
  caseId: string;
  signals: DceContractRiskSignal[];
  loading: boolean;
  registeringObservationId: string | null;
  canManage?: boolean;
  onRefresh: () => void;
  onRegister: (signal: DceContractRiskSignal, input: RegisterStructuredRiskInput) => void;
};

const defaultTitles: Record<DceContractRiskSignal["requirement_kind"], string> = {
  CCAP_PENALTIES: "Pénalités contractuelles",
  CCAP_RETENTION_GUARANTEE: "Retenue de garantie",
  CCAP_GUARANTEE: "Cautionnement ou garantie financière",
  CCAP_INSURANCE: "Assurances contractuelles",
  CCTP_VARIANTS: "Variantes ou options techniques",
  CCAP_SUBCONTRACTING: "Sous-traitance",
  CCAP_QUALIFICATIONS: "Qualifications professionnelles",
};

const defaultDraft = (signal: DceContractRiskSignal): SignalDraft => ({
  title: defaultTitles[signal.requirement_kind],
  statement: "",
  severity: signal.directive === "REQUIRED_SIGNAL" ? "HIGH" : "MEDIUM",
  likelihood: "POSSIBLE",
  sourceExcerpt: "",
  sourceLocator: signal.source_locator_label,
  dueAt: "",
});

export function DceContractRiskSignalsPanel({
  caseId,
  signals,
  loading,
  registeringObservationId,
  canManage = false,
  onRefresh,
  onRegister,
}: DceContractRiskSignalsPanelProps) {
  const [drafts, setDrafts] = useState<Record<string, SignalDraft>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  function draftFor(signal: DceContractRiskSignal): SignalDraft {
    return drafts[signal.observation_id] ?? defaultDraft(signal);
  }

  function updateDraft(signal: DceContractRiskSignal, patch: Partial<SignalDraft>) {
    setDrafts((current) => ({
      ...current,
      [signal.observation_id]: { ...draftFor(signal), ...patch },
    }));
    setErrors((current) => ({ ...current, [signal.observation_id]: "" }));
  }

  function submit(signal: DceContractRiskSignal) {
    const draft = draftFor(signal);
    if (!draft.title.trim() || !draft.statement.trim() || !draft.sourceExcerpt.trim()) {
      setErrors((current) => ({
        ...current,
        [signal.observation_id]: "Le titre, la formulation et l’extrait de preuve sont obligatoires.",
      }));
      return;
    }
    setErrors((current) => ({ ...current, [signal.observation_id]: "" }));
    onRegister(signal, {
      risk_id: crypto.randomUUID(),
      dce_version_id: signal.dce_version_id,
      source_fragment_id: signal.fragment_id,
      category: signal.document_family,
      risk_code: signal.requirement_kind,
      title: draft.title.trim(),
      statement: draft.statement.trim(),
      severity: draft.severity,
      likelihood: draft.likelihood,
      source_excerpt: draft.sourceExcerpt.trim(),
      source_locator: { label: draft.sourceLocator.trim() || signal.source_locator_label },
      start_byte_offset: signal.start_byte_offset,
      end_byte_offset: signal.end_byte_offset,
      due_at: draft.dueAt ? new Date(`${draft.dueAt}T00:00:00Z`).toISOString() : null,
    });
  }

  return (
    <section className="section-block decision-section" id="dce-contract-risk-signals-section">
      <div className="section-heading">
        <div>
          <span className="section-kicker">DÉTECTION CCAP / CCTP</span>
          <h2>Transformer les signaux en risques suivis</h2>
        </div>
        <div className="top-actions">
          <span className="count-pill">{signals.length} signal{signals.length > 1 ? "s" : ""}</span>
          <button className="secondary-button" type="button" onClick={onRefresh} disabled={!caseId || loading}>
            {loading ? "Chargement…" : "Actualiser"}
          </button>
        </div>
      </div>
      {!caseId ? (
        <div className="empty-card"><strong>Aucune affaire sélectionnée</strong><p>Sélectionnez une affaire pour lire les signaux contractuels.</p></div>
      ) : signals.length === 0 && !loading ? (
        <div className="empty-card"><strong>Aucun signal à examiner</strong><p>L’analyse DCE ne fournit actuellement aucun signal CCAP/CCTP en attente de revue.</p></div>
      ) : (
        <div className="decision-grid">
          {signals.map((signal) => {
            const draft = draftFor(signal);
            const busy = registeringObservationId === signal.observation_id;
            return (
              <article className="detail-panel" key={signal.observation_id}>
                <div className="panel-heading">
                  <div>
                    <h3>{signal.requirement_kind}</h3>
                    <p>{signal.document_family} · {signal.source_locator_label} · règle {signal.rule_version}</p>
                  </div>
                  <span className="state-badge state-warning">À examiner</span>
                </div>
                <div className="decision-facts">
                  <span><small>Directive</small><strong>{signal.directive}</strong></span>
                  <span><small>Début</small><strong>{signal.start_byte_offset}</strong></span>
                  <span><small>Fin</small><strong>{signal.end_byte_offset}</strong></span>
                </div>
                {canManage ? (
                  <form className="decision-form" onSubmit={(event) => { event.preventDefault(); submit(signal); }}>
                    <h4>Revue humaine</h4>
                    <label>Titre du risque
                      <input value={draft.title} maxLength={240} onChange={(event) => updateDraft(signal, { title: event.target.value })} required />
                    </label>
                    <label>Formulation du risque
                      <textarea value={draft.statement} maxLength={4000} rows={3} onChange={(event) => updateDraft(signal, { statement: event.target.value })} required />
                    </label>
                    <div className="decision-facts">
                      <label>Gravité
                        <select value={draft.severity} onChange={(event) => updateDraft(signal, { severity: event.target.value as StructuredRiskSeverity })}>
                          <option value="LOW">Faible</option><option value="MEDIUM">Moyenne</option><option value="HIGH">Élevée</option><option value="CRITICAL">Critique</option>
                        </select>
                      </label>
                      <label>Probabilité
                        <select value={draft.likelihood} onChange={(event) => updateDraft(signal, { likelihood: event.target.value as StructuredRiskLikelihood })}>
                          <option value="RARE">Rare</option><option value="POSSIBLE">Possible</option><option value="LIKELY">Probable</option><option value="ALMOST_CERTAIN">Quasi certaine</option>
                        </select>
                      </label>
                    </div>
                    <label>Extrait de preuve source
                      <textarea value={draft.sourceExcerpt} maxLength={2000} rows={3} onChange={(event) => updateDraft(signal, { sourceExcerpt: event.target.value })} required />
                    </label>
                    <label>Échéance (facultative)
                      <input type="date" value={draft.dueAt} onChange={(event) => updateDraft(signal, { dueAt: event.target.value })} />
                    </label>
                    {errors[signal.observation_id] && <p className="form-error" role="alert">{errors[signal.observation_id]}</p>}
                    <button className="primary-button" type="submit" disabled={busy}>{busy ? "Enregistrement…" : "Enregistrer le risque"}</button>
                  </form>
                ) : (
                  <p className="panel-empty">Lecture seule : la promotion en risque structuré est réservée au patron administrateur.</p>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
