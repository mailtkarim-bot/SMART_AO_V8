import { useState } from "react";

import type {
  CollaboratorTaskWorkflow,
  CreateInformationRequestInput,
  DeclareTaskBlockerInput,
  RecordInformationResponseInput,
  ResolveTaskBlockerInput,
} from "../../shared/types";

type TaskWorkflowPanelProps = {
  taskId: string;
  workflow: CollaboratorTaskWorkflow | null;
  onLoad: () => void;
  onCreateRequest: (input: CreateInformationRequestInput) => void;
  onRecordResponse: (requestId: string, input: RecordInformationResponseInput) => void;
  onDeclareBlocker: (input: DeclareTaskBlockerInput) => void;
  onResolveBlocker: (blockerId: string, input: ResolveTaskBlockerInput) => void;
};

const requestKinds: CreateInformationRequestInput["request_kind"][] = [
  "MISSING_SOURCE",
  "CLARIFICATION",
  "OWNER_CONFIRMATION",
  "DEADLINE_CONFIRMATION",
];
const priorities: CreateInformationRequestInput["priority"][] = ["LOW", "NORMAL", "HIGH", "CRITICAL"];
const blockerKinds: DeclareTaskBlockerInput["blocker_kind"][] = [
  "MISSING_INFORMATION",
  "EXTERNAL_DEPENDENCY",
  "SOURCE_CONFLICT",
  "REVIEW_REQUIRED",
];
const owners: DeclareTaskBlockerInput["resolution_owner"][] = [
  "COLLABORATEUR",
  "PATRON_ADMIN",
  "EXTERNAL_PARTY",
];

export function TaskWorkflowPanel({
  taskId,
  workflow,
  onLoad,
  onCreateRequest,
  onRecordResponse,
  onDeclareBlocker,
  onResolveBlocker,
}: TaskWorkflowPanelProps) {
  const [request, setRequest] = useState<CreateInformationRequestInput>({
    expected_task_revision: 0,
    request_kind: "CLARIFICATION",
    subject: "",
    question: "",
    requested_object: "",
    reason: "",
    priority: "NORMAL",
    due_at: null,
  });
  const [blocker, setBlocker] = useState<DeclareTaskBlockerInput>({
    expected_revision: 0,
    blocker_kind: "MISSING_INFORMATION",
    description: "",
    source_locator: null,
    resolution_owner: "COLLABORATEUR",
  });
  const [responseRequestId, setResponseRequestId] = useState<string | null>(null);
  const [responseText, setResponseText] = useState("");
  const [responseOutcome, setResponseOutcome] = useState<RecordInformationResponseInput["outcome"]>("ANSWERED");
  const [responseSource, setResponseSource] = useState("");
  const [resolutionBlockerId, setResolutionBlockerId] = useState<string | null>(null);
  const [resolutionNote, setResolutionNote] = useState("");

  function submitRequest(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!request.subject.trim() || !request.question.trim() || !request.requested_object.trim() || !request.reason.trim()) return;
    onCreateRequest({
      ...request,
      subject: request.subject.trim(),
      question: request.question.trim(),
      requested_object: request.requested_object.trim(),
      reason: request.reason.trim(),
      due_at: request.due_at || null,
    });
    setRequest((current) => ({ ...current, subject: "", question: "", requested_object: "", reason: "" }));
  }

  function submitBlocker(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!blocker.description.trim()) return;
    onDeclareBlocker({
      ...blocker,
      description: blocker.description.trim(),
      source_locator: blocker.source_locator?.trim() || null,
    });
    setBlocker((current) => ({ ...current, description: "", source_locator: null }));
  }

  function submitResponse(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!responseRequestId || !responseText.trim()) return;
    const item = workflow?.information_requests.find((candidate) => candidate.request_id === responseRequestId);
    if (!item) return;
    onRecordResponse(responseRequestId, {
      expected_revision: item.aggregate_revision,
      response_text: responseText.trim(),
      source_locator: responseSource.trim() || null,
      outcome: responseOutcome,
    });
    setResponseText("");
    setResponseSource("");
    setResponseRequestId(null);
  }

  function submitResolution(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!resolutionBlockerId || !resolutionNote.trim()) return;
    const item = workflow?.blockers.find((candidate) => candidate.blocker_id === resolutionBlockerId);
    if (!item) return;
    onResolveBlocker(resolutionBlockerId, {
      expected_revision: item.task_revision,
      resolution_note: resolutionNote.trim(),
    });
    setResolutionNote("");
    setResolutionBlockerId(null);
  }

  return (
    <div className="detail-panel task-workflow-panel">
      <div className="panel-heading">
        <div>
          <h3>Demandes et bloqueurs</h3>
          <p>Les demandes sont traçables et les bloqueurs restent opposables au serveur.</p>
        </div>
        <button className="secondary-button" type="button" disabled={!taskId} onClick={onLoad}>
          Actualiser le workflow
        </button>
      </div>
      {!taskId ? (
        <p className="panel-empty">Sélectionnez une tâche pour charger son workflow.</p>
      ) : !workflow ? (
        <p className="panel-empty">Le workflow de la tâche n’est pas encore chargé.</p>
      ) : (
        <>
          <div className="workflow-summary">
            <span>État tâche : <strong>{workflow.state}</strong></span>
            <span>Révision : <strong>{workflow.aggregate_revision}</strong></span>
            <span>{workflow.information_requests.length} demande(s)</span>
            <span>{workflow.blockers.filter((item) => item.state === "OPEN").length} bloqueur(s) ouvert(s)</span>
          </div>
          <div className="workflow-lists">
            <div>
              <h4>Demandes d’information</h4>
              {workflow.information_requests.length === 0 ? <p className="panel-empty">Aucune demande.</p> : workflow.information_requests.map((item) => (
                <article className="workflow-item" key={item.request_id}>
                  <div className="workflow-item-top"><strong>{item.subject}</strong><span className="state-badge">{item.state}</span></div>
                  <small>{item.request_kind} · {item.priority} · Révision {item.aggregate_revision}</small>
                  <p>{item.question}</p>
                  {item.responses.map((response) => <div className="workflow-response" key={response.response_id}><strong>{response.outcome}</strong><span>{response.response_text}</span></div>)}
                  {item.state === "OPEN" && <button className="secondary-button" type="button" onClick={() => setResponseRequestId(item.request_id)}>Répondre</button>}
                </article>
              ))}
            </div>
            <div>
              <h4>Bloqueurs</h4>
              {workflow.blockers.length === 0 ? <p className="panel-empty">Aucun bloqueur.</p> : workflow.blockers.map((item) => (
                <article className="workflow-item" key={item.blocker_id}>
                  <div className="workflow-item-top"><strong>{item.blocker_kind}</strong><span className="state-badge">{item.state}</span></div>
                  <small>Résolution : {item.resolution_owner} · Révision tâche {item.task_revision}</small>
                  <p>{item.description}</p>
                  {item.resolution_note && <div className="workflow-response"><strong>Résolution</strong><span>{item.resolution_note}</span></div>}
                  {item.state === "OPEN" && <button className="secondary-button" type="button" onClick={() => setResolutionBlockerId(item.blocker_id)}>Résoudre</button>}
                </article>
              ))}
            </div>
          </div>
        </>
      )}
      {workflow && responseRequestId && <form className="workflow-form" onSubmit={submitResponse}><h4>Répondre à la demande</h4><textarea required rows={3} value={responseText} onChange={(event) => setResponseText(event.target.value)} placeholder="Réponse structurée" /><input value={responseSource} onChange={(event) => setResponseSource(event.target.value)} placeholder="Référence source facultative" /><select value={responseOutcome} onChange={(event) => setResponseOutcome(event.target.value as RecordInformationResponseInput["outcome"])}><option value="ANSWERED">Répondue</option><option value="NOT_AVAILABLE">Non disponible</option><option value="NEEDS_CLARIFICATION">Clarification nécessaire</option></select><button className="primary-button" type="submit">Enregistrer la réponse</button></form>}
      {workflow && resolutionBlockerId && <form className="workflow-form" onSubmit={submitResolution}><h4>Résoudre le bloqueur</h4><textarea required rows={3} value={resolutionNote} onChange={(event) => setResolutionNote(event.target.value)} placeholder="Note de résolution" /><button className="primary-button" type="submit">Confirmer la résolution</button></form>}
      {taskId && <div className="workflow-create-grid"><form className="workflow-form" onSubmit={submitRequest}><h4>Créer une demande</h4><select value={request.request_kind} onChange={(event) => setRequest({ ...request, request_kind: event.target.value as CreateInformationRequestInput["request_kind"] })}>{requestKinds.map((kind) => <option key={kind} value={kind}>{kind}</option>)}</select><input required value={request.subject} onChange={(event) => setRequest({ ...request, subject: event.target.value })} placeholder="Objet" /><textarea required rows={2} value={request.question} onChange={(event) => setRequest({ ...request, question: event.target.value })} placeholder="Question" /><input required value={request.requested_object} onChange={(event) => setRequest({ ...request, requested_object: event.target.value })} placeholder="Objet demandé" /><textarea required rows={2} value={request.reason} onChange={(event) => setRequest({ ...request, reason: event.target.value })} placeholder="Motif" /><select value={request.priority} onChange={(event) => setRequest({ ...request, priority: event.target.value as CreateInformationRequestInput["priority"] })}>{priorities.map((priority) => <option key={priority} value={priority}>{priority}</option>)}</select><button className="primary-button" type="submit">Créer la demande</button></form><form className="workflow-form" onSubmit={submitBlocker}><h4>Déclarer un bloqueur</h4><select value={blocker.blocker_kind} onChange={(event) => setBlocker({ ...blocker, blocker_kind: event.target.value as DeclareTaskBlockerInput["blocker_kind"] })}>{blockerKinds.map((kind) => <option key={kind} value={kind}>{kind}</option>)}</select><textarea required rows={3} value={blocker.description} onChange={(event) => setBlocker({ ...blocker, description: event.target.value })} placeholder="Description du bloqueur" /><input value={blocker.source_locator ?? ""} onChange={(event) => setBlocker({ ...blocker, source_locator: event.target.value })} placeholder="Référence source facultative" /><select value={blocker.resolution_owner} onChange={(event) => setBlocker({ ...blocker, resolution_owner: event.target.value as DeclareTaskBlockerInput["resolution_owner"] })}>{owners.map((owner) => <option key={owner} value={owner}>{owner}</option>)}</select><button className="primary-button" type="submit">Déclarer le bloqueur</button></form></div>}
    </div>
  );
}
