import type { CaseDceReading, KnowledgeSearchResult } from "../../shared/types";

type Props = {
  selectedCaseId: string;
  reading: CaseDceReading | null;
  results: KnowledgeSearchResult[];
  query: string;
  loading: boolean;
  searching: boolean;
  onQueryChange: (query: string) => void;
  onLoad: () => void;
  onSearch: () => void;
  onResetSearch: () => void;
};

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Date invalide"
    : new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium" }).format(date);
}

function locatorLabel(locator: Record<string, unknown>) {
  const label = locator.label ?? locator.page ?? locator.section;
  return typeof label === "string" ? label : "Localisation source non précisée";
}

export function DceKnowledgePanel({
  selectedCaseId,
  reading,
  results,
  query,
  loading,
  searching,
  onQueryChange,
  onLoad,
  onSearch,
  onResetSearch,
}: Props) {
  return (
    <section className="section-block dce-knowledge-section" id="dce-knowledge-section">
      <div className="section-heading">
        <div>
          <span className="section-kicker">LECTURE DCE · RAG SOURCÉ</span>
          <h2>Comprendre le dossier</h2>
        </div>
        <button className="secondary-button compact-button" type="button" onClick={onLoad} disabled={!selectedCaseId || loading}>
          {loading ? "Lecture…" : "Actualiser la lecture"}
        </button>
      </div>
      <p className="section-note">Les résultats indiquent une source et un emplacement ; ils ne constituent pas une décision automatique.</p>
      {!selectedCaseId ? (
        <div className="empty-card"><strong>Sélectionnez une affaire</strong><p>La lecture DCE et la recherche knowledge restent limitées à l’affaire choisie.</p></div>
      ) : !reading && loading ? (
        <div className="empty-card"><strong>Lecture DCE en cours</strong><p>Le serveur prépare une projection minimale tenant-scoped.</p></div>
      ) : !reading ? (
        <div className="empty-card"><strong>Lecture DCE indisponible</strong><p>La projection n’est pas encore disponible pour cette affaire, ou nécessite une recette backend.</p></div>
      ) : (
        <div className="dce-knowledge-layout">
          <div className="dce-reading-panel">
            <div className="dce-reading-heading"><div><span className="section-kicker">PROJECTION DCE</span><h3>{reading.work_label}</h3></div><span className="state-badge state-monitor">{reading.dce_freshness}</span></div>
            <div className="dce-meta"><span>{reading.dce.lifecycle}</span><span>Version {reading.dce.dce_version_id}</span><span>Reçu le {formatDate(reading.dce.source_received_at)}</span></div>
            <div className="dce-counter-grid">
              <div><strong>{reading.counters.total}</strong><span>Exigences</span></div>
              <div><strong>{reading.counters.pending_human_confirmation}</strong><span>À confirmer</span></div>
              <div><strong>{reading.counters.confirmed}</strong><span>Confirmées</span></div>
              <div><strong>{reading.counters.review_required}</strong><span>À revoir</span></div>
            </div>
            <div className="requirement-list">
              <div className="subheading"><span className="section-kicker">EXIGENCES STRUCTURÉES</span><span>{reading.requirements.length} affichées</span></div>
              {reading.requirements.length === 0 ? <p className="muted-copy">Aucune exigence structurée dans cette projection.</p> : reading.requirements.slice(0, 8).map((requirement) => (
                <div className="requirement-row" key={requirement.requirement_id}><div><strong>{requirement.requirement_type}</strong><span>{requirement.document_family} · {requirement.source_locator_label}</span></div><span className={`state-badge ${requirement.confirmation_outcome === "CONFIRMED" ? "state-success" : "state-warning"}`}>{requirement.confirmation_outcome}</span></div>
              ))}
            </div>
          </div>
          <div className="knowledge-search-panel">
            <div><span className="section-kicker">RECHERCHE SOURCÉE</span><h3>Interroger le DCE</h3></div>
            <label><span>Question ou terme</span><input value={query} onChange={(event) => onQueryChange(event.target.value)} maxLength={500} placeholder="ex. délai d’exécution" /></label>
            <div className="knowledge-actions"><button className="primary-button" type="button" onClick={onSearch} disabled={searching}>{searching ? "Recherche…" : "Rechercher"}<span>→</span></button><button className="secondary-button" type="button" onClick={onResetSearch} disabled={!query && results.length === 0}>Effacer</button></div>
            <div className="knowledge-results" aria-live="polite">
              {results.length === 0 ? <p className="muted-copy">Les résultats avec score et localisation source apparaîtront ici.</p> : results.map((result) => <article className="knowledge-result" key={result.source_fragment_id}><div className="knowledge-result-top"><strong>{Math.round(result.score * 100)}%</strong><span>{result.embedding_model}</span></div><p>{locatorLabel(result.locator)}</p><small>Fragment source {result.source_fragment_id}</small></article>)}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
