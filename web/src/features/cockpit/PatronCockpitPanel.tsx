import type {
  PatronAssignment,
  PatronAssignmentInteractions,
  PatronAssignmentJournalItem,
} from "../../shared/types";

type PatronCockpitPanelProps = {
  assignments: PatronAssignment[];
  selectedAssignmentId: string;
  journal: PatronAssignmentJournalItem[];
  interactions: PatronAssignmentInteractions | null;
  onSelectAssignment: (assignment: PatronAssignment) => void;
};

export function PatronCockpitPanel({
  assignments,
  selectedAssignmentId,
  journal,
  interactions,
  onSelectAssignment,
}: PatronCockpitPanelProps) {
  return (
    <section className="section-block cockpit-section">
      <div className="section-heading">
        <div>
          <span className="section-kicker">PILOTAGE OPÉRATIONNEL</span>
          <h2>Affectations et signaux</h2>
        </div>
        <span className="count-pill">
          {assignments.length} affectation{assignments.length > 1 ? "s" : ""}
        </span>
      </div>
      {assignments.length === 0 ? (
        <div className="empty-card">
          <strong>Aucune affectation patronale visible</strong>
          <p>
            La projection est tenant-scopée et ne montre que les affectations autorisées par le
            serveur.
          </p>
        </div>
      ) : (
        <div className="assignment-grid">
          {assignments.map((assignment) => (
            <button
              key={assignment.assignment_id}
              className={`assignment-card ${
                assignment.assignment_id === selectedAssignmentId ? "selected" : ""
              }`}
              onClick={() => onSelectAssignment(assignment)}
              type="button"
            >
              <div className="case-top">
                <span className={`state-badge state-${assignment.state.toLowerCase()}`}>
                  {assignment.state}
                </span>
                <span className="case-arrow">↗</span>
              </div>
              <h3>{assignment.case_title}</h3>
              <p>{assignment.case_id}</p>
              <div className="assignment-footer">
                <span>Révision {assignment.aggregate_revision}</span>
                <span>
                  {assignment.scope_actions.length} action
                  {assignment.scope_actions.length > 1 ? "s" : ""}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
      {selectedAssignmentId && (
        <div className="assignment-detail-grid">
          <div className="detail-panel">
            <div className="panel-heading">
              <div>
                <h3>Journal de l’affectation</h3>
                <p>Historique append-only projeté par le serveur.</p>
              </div>
              <span className="rule-tag">
                {journal.length} événement{journal.length > 1 ? "s" : ""}
              </span>
            </div>
            {journal.length === 0 ? (
              <p className="panel-empty">Aucun événement journalisé.</p>
            ) : (
              <div className="timeline">
                {journal.slice(0, 6).map((entry) => (
                  <div className="timeline-row" key={entry.record_id}>
                    <span className="timeline-dot" />
                    <div>
                      <strong>{entry.event_type}</strong>
                      <small>
                        {entry.resulting_state} · Révision {entry.resulting_revision}
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
                <h3>Interactions récentes</h3>
                <p>Signaux collaborateur structurés, sans texte sensible.</p>
              </div>
              <span className="rule-tag">
                {interactions?.items.length ?? 0} signal
                {(interactions?.items.length ?? 0) > 1 ? "s" : ""}
              </span>
            </div>
            {!interactions?.items.length ? (
              <p className="panel-empty">Aucune interaction enregistrée.</p>
            ) : (
              <div className="interaction-list">
                {interactions.items.slice(0, 6).map((item) => (
                  <div className="interaction-row" key={item.record_id}>
                    <span
                      className={`interaction-kind kind-${item.operational_state.toLowerCase()}`}
                    >
                      {item.operational_state}
                    </span>
                    <div>
                      <strong>{item.kind}</strong>
                      <small>
                        {item.priority ??
                          item.reason_kind ??
                          item.clarification_kind ??
                          "Signal opérationnel"}
                      </small>
                    </div>
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
