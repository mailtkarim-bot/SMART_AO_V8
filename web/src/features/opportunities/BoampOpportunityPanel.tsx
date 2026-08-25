import type {
  BoampObservation,
  BoampQualificationDecision,
  BoampQualificationForm,
  BoampQualificationReason,
} from "../../shared/types";

type Props = {
  observations: BoampObservation[];
  selectedObservationId: string;
  qualificationForm: BoampQualificationForm;
  loading: boolean;
  qualifying: boolean;
  onRefresh: () => void;
  onSelect: (observationId: string) => void;
  onDecisionChange: (decision: BoampQualificationDecision) => void;
  onReasonChange: (reason: BoampQualificationReason) => void;
  onQualify: () => void;
};

const decisions: Array<{ value: BoampQualificationDecision; label: string }> = [
  { value: "QUALIFIED", label: "À qualifier" },
  { value: "REJECTED", label: "Écarter" },
  { value: "SNOOZED", label: "Mettre en attente" },
];

const reasons: Array<{ value: BoampQualificationReason; label: string }> = [
  { value: "RELEVANT_PUBLIC_SIGNAL", label: "Signal public pertinent" },
  { value: "NOT_RELEVANT", label: "Hors périmètre" },
  { value: "INSUFFICIENT_PUBLIC_DATA", label: "Données publiques insuffisantes" },
  { value: "EXPIRED", label: "Échéance dépassée" },
];

function formatDate(value: string | null) {
  if (!value) return "Non précisée";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? "Date invalide"
    : new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium" }).format(parsed);
}

function selectedItem(observations: BoampObservation[], selectedId: string) {
  return observations.find((item) => item.observation_id === selectedId) ?? null;
}

export function BoampOpportunityPanel({
  observations,
  selectedObservationId,
  qualificationForm,
  loading,
  qualifying,
  onRefresh,
  onSelect,
  onDecisionChange,
  onReasonChange,
  onQualify,
}: Props) {
  const selected = selectedItem(observations, selectedObservationId);

  return (
    <section className="section-block boamp-section" id="boamp-section">
      <div className="section-heading">
        <div>
          <span className="section-kicker">VEILLE PUBLIQUE</span>
          <h2>Opportunités BOAMP</h2>
        </div>
        <div className="section-actions">
          <span className="count-pill">{observations.length} visible{observations.length > 1 ? "s" : ""}</span>
          <button className="secondary-button compact-button" type="button" onClick={onRefresh} disabled={loading}>
            {loading ? "Chargement…" : "Actualiser"}
          </button>
        </div>
      </div>
      <p className="section-note">Lecture patronale de signaux publics. Aucune donnée financière ni conversion automatique en affaire.</p>
      {observations.length === 0 ? (
        <div className="empty-card">
          <strong>Aucune opportunité BOAMP disponible</strong>
          <p>Les observations ingérées et autorisées apparaîtront ici, dans le périmètre du tenant courant.</p>
        </div>
      ) : (
        <div className="boamp-layout">
          <div className="boamp-list" aria-label="Opportunités BOAMP">
            {observations.map((item) => (
              <button
                className={`boamp-item ${item.observation_id === selectedObservationId ? "selected" : ""}`}
                key={item.observation_id}
                type="button"
                onClick={() => onSelect(item.observation_id)}
              >
                <span className="boamp-item-top">
                  <span className="state-badge state-monitor">Score {item.score}</span>
                  <span className="boamp-deadline">{formatDate(item.response_deadline)}</span>
                </span>
                <strong>{item.title ?? "Titre non communiqué"}</strong>
                <span>{item.department_codes.join(", ") || "Département non précisé"}</span>
              </button>
            ))}
          </div>
          <div className="boamp-detail">
            {selected ? (
              <>
                <div className="boamp-detail-heading">
                  <div>
                    <span className="section-kicker">OBSERVATION PUBLIQUE</span>
                    <h3>{selected.title ?? "Titre non communiqué"}</h3>
                  </div>
                  <span className="score-emphasis">{selected.score}<small>/100</small></span>
                </div>
                <dl className="boamp-facts">
                  <div><dt>Avis source</dt><dd>{selected.source_notice_id}</dd></div>
                  <div><dt>Publication</dt><dd>{formatDate(selected.publication_date)}</dd></div>
                  <div><dt>Réponse avant</dt><dd>{formatDate(selected.response_deadline)}</dd></div>
                  <div><dt>Départements</dt><dd>{selected.department_codes.join(", ") || "Non précisés"}</dd></div>
                  <div><dt>Types de marché</dt><dd>{selected.market_types.join(", ") || "Non précisés"}</dd></div>
                  <div><dt>Statut public</dt><dd>{selected.source_status ?? "Non précisé"}</dd></div>
                </dl>
                <div className="boamp-qualification">
                  <div><span className="section-kicker">DÉCISION HUMAINE</span><h3>Qualifier cette observation</h3></div>
                  <label><span>Décision</span><select value={qualificationForm.decision} onChange={(event) => onDecisionChange(event.target.value as BoampQualificationDecision)}>{decisions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
                  <label><span>Motif</span><select value={qualificationForm.reason_code} onChange={(event) => onReasonChange(event.target.value as BoampQualificationReason)}>{reasons.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
                  <button className="primary-button" type="button" onClick={onQualify} disabled={qualifying}>{qualifying ? "Enregistrement…" : "Enregistrer la qualification"}<span>→</span></button>
                </div>
              </>
            ) : (
              <div className="empty-card"><strong>Sélectionnez une observation</strong><p>La projection détaillée et la qualification humaine resteront limitées au tenant courant.</p></div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
