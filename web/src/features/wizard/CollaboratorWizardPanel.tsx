import type { Dispatch, SetStateAction } from "react";

import type { CollaboratorTask, PreparationPackage } from "../../shared/types";

type WizardOutcome = "RECORDED" | "NOT_APPLICABLE" | "UNABLE_TO_COMPLETE";

type CollaboratorWizardPanelProps = {
  wizardCaseId: string;
  wizardPackageId: string;
  wizardPackage: PreparationPackage | null;
  wizardTasks: CollaboratorTask[];
  wizardTaskId: string;
  wizardResultText: string;
  wizardOutcome: WizardOutcome;
  wizardSnapshotId: string;
  wizardTransmissionId: string;
  wizardPreviewDocumentId: string | null;
  wizardPreviewContent: string | null;
  wizardDocumentBusy: boolean;
  setWizardCaseId: Dispatch<SetStateAction<string>>;
  setWizardPackageId: Dispatch<SetStateAction<string>>;
  setWizardTaskId: Dispatch<SetStateAction<string>>;
  setWizardResultText: Dispatch<SetStateAction<string>>;
  setWizardOutcome: Dispatch<SetStateAction<WizardOutcome>>;
  setWizardSnapshotId: Dispatch<SetStateAction<string>>;
  setWizardTransmissionId: Dispatch<SetStateAction<string>>;
  onLoad: () => void;
  onClaimTask: () => void;
  onRecordResult: () => void;
  onCompleteTask: () => void;
  onEvaluateReadiness: () => void;
  onGenerateDocument: () => void;
  onTransmitSnapshot: () => void;
  onPreviewDocument: (documentId: string) => void;
  onDownloadDocument: (documentId: string) => void;
};

export function CollaboratorWizardPanel({
  wizardCaseId,
  wizardPackageId,
  wizardPackage,
  wizardTasks,
  wizardTaskId,
  wizardResultText,
  wizardOutcome,
  wizardSnapshotId,
  wizardTransmissionId,
  setWizardCaseId,
  setWizardPackageId,
  setWizardTaskId,
  setWizardResultText,
  setWizardOutcome,
  setWizardSnapshotId,
  setWizardTransmissionId,
  wizardPreviewDocumentId,
  wizardPreviewContent,
  wizardDocumentBusy,
  onLoad,
  onClaimTask,
  onRecordResult,
  onCompleteTask,
  onEvaluateReadiness,
  onGenerateDocument,
  onTransmitSnapshot,
  onPreviewDocument,
  onDownloadDocument,
}: CollaboratorWizardPanelProps) {
  return (
    <section className="section-block wizard-section" id="collaborator-wizard-section">
      <div className="section-heading">
        <div>
          <span className="section-kicker">PARCOURS COLLABORATEUR</span>
          <h2>Wizard de préparation</h2>
        </div>
        <span className="count-pill">{wizardPackage?.state ?? "À charger"}</span>
      </div>
      <div className="wizard-toolbar">
        <label>
          <span>Identifiant de l’affaire</span>
          <input
            value={wizardCaseId}
            onChange={(event) => setWizardCaseId(event.target.value)}
            placeholder="UUID de l’affaire"
          />
        </label>
        <label>
          <span>Identifiant du package</span>
          <input
            value={wizardPackageId}
            onChange={(event) => setWizardPackageId(event.target.value)}
            placeholder="UUID de préparation"
          />
        </label>
        <button className="primary-button" type="button" onClick={onLoad}>
          Charger le wizard <span>→</span>
        </button>
      </div>
      {!wizardPackage ? (
        <div className="empty-card">
          <strong>Le wizard est prêt à être chargé</strong>
          <p>
            Les projections de préparation et les tâches sont lues dans le périmètre collaborateur
            autorisé. Aucune donnée financière n’est exposée ici.
          </p>
        </div>
      ) : (
        <div className="wizard-body">
          <div className="wizard-steps">
            <div className="wizard-step complete">
              <span>1</span>
              <strong>Tâches</strong>
              <small>
                {wizardTasks.filter((task) => task.state === "COMPLETED").length}/
                {wizardTasks.length} terminées
              </small>
            </div>
            <div className={`wizard-step ${wizardPackage.latest_readiness ? "complete" : ""}`}>
              <span>2</span>
              <strong>Complétude</strong>
              <small>{wizardPackage.latest_readiness?.state ?? "À vérifier"}</small>
            </div>
            <div
              className={`wizard-step ${
                wizardPackage.generated_documents.length ? "complete" : ""
              }`}
            >
              <span>3</span>
              <strong>Document</strong>
              <small>{wizardPackage.generated_documents.length ? "Généré" : "À générer"}</small>
            </div>
            <div className="wizard-step">
              <span>4</span>
              <strong>Transmission</strong>
              <small>Contrôle patron</small>
            </div>
          </div>
          <div className="wizard-grid">
            <div className="detail-panel">
              <div className="panel-heading">
                <div>
                  <h3>Tâches de l’affaire</h3>
                  <p>Chaque résultat est structuré, révisé et traçable.</p>
                </div>
                <span className="rule-tag">
                  {wizardTasks.length} tâche{wizardTasks.length > 1 ? "s" : ""}
                </span>
              </div>
              {wizardTasks.length === 0 ? (
                <p className="panel-empty">Aucune tâche projetée.</p>
              ) : (
                <div className="wizard-task-list">
                  {wizardTasks.map((task) => (
                    <button
                      type="button"
                      className={`wizard-task ${task.task_id === wizardTaskId ? "selected" : ""}`}
                      key={task.task_id}
                      onClick={() => setWizardTaskId(task.task_id)}
                    >
                      <div>
                        <strong>{task.title}</strong>
                        <small>
                          {task.task_kind} · {task.priority} · Révision {task.aggregate_revision}
                        </small>
                      </div>
                      <span className={`state-badge state-${task.state.toLowerCase()}`}>
                        {task.state}
                      </span>
                    </button>
                  ))}
                </div>
              )}
              {wizardTaskId && (
                <div className="wizard-task-actions">
                  <button className="secondary-button" type="button" onClick={onClaimTask}>
                    Prendre en charge
                  </button>
                  <label>
                    <span>Résultat</span>
                    <textarea
                      rows={2}
                      value={wizardResultText}
                      onChange={(event) => setWizardResultText(event.target.value)}
                      placeholder="Constat ou preuve structurée, sans donnée financière"
                    />
                  </label>
                  <label>
                    <span>Issue</span>
                    <select
                      value={wizardOutcome}
                      onChange={(event) =>
                        setWizardOutcome(event.target.value as WizardOutcome)
                      }
                    >
                      <option value="RECORDED">Enregistré</option>
                      <option value="NOT_APPLICABLE">Non applicable</option>
                      <option value="UNABLE_TO_COMPLETE">Impossible à compléter</option>
                    </select>
                  </label>
                  <div className="wizard-action-row">
                    <button className="primary-button" type="button" onClick={onRecordResult}>
                      Enregistrer le résultat
                    </button>
                    <button className="secondary-button" type="button" onClick={onCompleteTask}>
                      Clôturer
                    </button>
                  </div>
                </div>
              )}
            </div>
            <div className="detail-panel">
              <div className="panel-heading">
                <div>
                  <h3>Complétude et production</h3>
                  <p>La readiness est recalculée côté serveur avant toute génération.</p>
                </div>
              </div>
              <div className="wizard-action-row">
                <button className="primary-button" type="button" onClick={onEvaluateReadiness}>
                  Vérifier la complétude
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  disabled={!wizardPackage.latest_readiness}
                  onClick={onGenerateDocument}
                >
                  Générer la réponse technique
                </button>
              </div>
              {wizardPackage.latest_readiness ? (
                <div className="readiness-card">
                  <div className="case-top">
                    <strong>{wizardPackage.latest_readiness.state}</strong>
                    <span>Révision {wizardPackage.latest_readiness.revision}</span>
                  </div>
                  <p>
                    {wizardPackage.latest_readiness.checked_task_count} tâche(s) et {" "}
                    {wizardPackage.latest_readiness.checked_requirement_count} exigence(s)
                    contrôlée(s).
                  </p>
                  {wizardPackage.latest_readiness.blocker_codes.length > 0 && (
                    <div className="code-list">
                      <strong>Blocages</strong>
                      {wizardPackage.latest_readiness.blocker_codes.map((code) => (
                        <span key={code}>{code}</span>
                      ))}
                    </div>
                  )}
                  {wizardPackage.latest_readiness.warning_codes.length > 0 && (
                    <div className="code-list warning">
                      <strong>Avertissements</strong>
                      {wizardPackage.latest_readiness.warning_codes.map((code) => (
                        <span key={code}>{code}</span>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <p className="panel-empty">La complétude n’a pas encore été vérifiée.</p>
              )}
              {wizardPackage.generated_documents.length > 0 && (
                <div className="document-list">
                  {wizardPackage.generated_documents.map((document) => (
                    <div className="document-row" key={document.document_id}>
                      <div>
                        <strong>{document.document_kind}</strong>
                        <span>
                          v{document.version} · {document.state}
                        </span>
                      </div>
                      <div className="wizard-action-row">
                        <button
                          className="secondary-button"
                          type="button"
                          disabled={wizardDocumentBusy}
                          onClick={() => onPreviewDocument(document.document_id)}
                        >
                          {wizardPreviewDocumentId === document.document_id ? "Actualiser l’aperçu" : "Aperçu"}
                        </button>
                        <button
                          className="secondary-button"
                          type="button"
                          disabled={wizardDocumentBusy}
                          onClick={() => onDownloadDocument(document.document_id)}
                        >
                          Télécharger
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {wizardPreviewContent !== null && (
                <div className="document-preview" aria-live="polite">
                  <div className="panel-heading">
                    <div>
                      <h3>Aperçu du document sélectionné</h3>
                      <p>Contenu relu depuis le stockage privé ; aucun lien public n’est créé.</p>
                    </div>
                  </div>
                  <pre>{wizardPreviewContent}</pre>
                </div>
              )}
            </div>
            <div className="detail-panel wizard-transmission">
              <div className="panel-heading">
                <div>
                  <h3>Transmettre au patron</h3>
                  <p>Cette transmission ne dépose jamais le dossier sur un portail externe.</p>
                </div>
              </div>
              <label>
                <span>Snapshot préparé</span>
                <input
                  value={wizardSnapshotId}
                  onChange={(event) => setWizardSnapshotId(event.target.value)}
                  placeholder="UUID du snapshot"
                />
              </label>
              <label>
                <span>Identifiant de transmission</span>
                <input
                  value={wizardTransmissionId}
                  onChange={(event) => setWizardTransmissionId(event.target.value)}
                  placeholder="UUID de transmission"
                />
              </label>
              <button className="primary-button" type="button" onClick={onTransmitSnapshot}>
                Transmettre au patron <span>→</span>
              </button>
              <small className="invariant-note">
                Sortie : contexte non financier, blocages et preuves structurées uniquement.
              </small>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
