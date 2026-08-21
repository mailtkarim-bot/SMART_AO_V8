import { useEffect, useMemo, useState } from "react";
import { PricingPanel } from "../features/pricing/PricingPanel";
import { usePricingImport } from "../features/pricing/usePricingImport";
import { SubmissionPanel } from "../features/submission/SubmissionPanel";
import { useSubmissionActions } from "../features/submission/useSubmissionActions";
import { useEnterpriseLibrary } from "../features/enterprise/useEnterpriseLibrary";
import { CollaboratorWizardPanel } from "../features/wizard/CollaboratorWizardPanel";
import { useCollaboratorWizard } from "../features/wizard/useCollaboratorWizard";
import { PatronCockpitPanel } from "../features/cockpit/PatronCockpitPanel";
import { PatronDecisionPanel } from "../features/decision/PatronDecisionPanel";
import { usePatronCockpit } from "../features/cockpit/usePatronCockpit";
import { FinancialDraftPanel } from "../features/draft/FinancialDraftPanel";
import { useFinancialDraft } from "../features/draft/useFinancialDraft";
import { createApiClient } from "../infrastructure/api";
import type {
  AssignedCase,
  FinancialCategory,
  PatronAction,
  PatronDecisionDossier,
  PricingScenario,
  EnterpriseDocumentKind,
  EnterpriseCapabilityKind,
} from "../shared/types";
import "./styles.css";

const CATEGORIES: Array<{ value: FinancialCategory; label: string }> = [
  { value: "SALES", label: "Ventes" },
  { value: "DIRECT_COST", label: "Coûts directs" },
  { value: "OVERHEAD", label: "Frais généraux" },
  { value: "SUBCONTRACTING", label: "Sous-traitance" },
  { value: "CONTINGENCY", label: "Provision" },
  { value: "GROSS_MARGIN", label: "Marge brute" },
  { value: "FORECAST_CASHFLOW", label: "Trésorerie prévisionnelle" },
];

const categoryLabel = (category: FinancialCategory) =>
  CATEGORIES.find((item) => item.value === category)?.label ?? category;

const formatMoney = (minor: number, currency = "EUR") =>
  new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(minor / 100);

const formatDate = (value: string) =>
  new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));

function App() {
  const [baseUrl, setBaseUrl] = useState(
    () => localStorage.getItem("smart-ao-api-url") ?? "http://localhost:8000",
  );
  const [token, setToken] = useState(
    () => localStorage.getItem("smart-ao-token") ?? "",
  );
  const [cases, setCases] = useState<AssignedCase[]>([]);
  const [actions, setActions] = useState<PatronAction[]>([]);
  const [scenarios, setScenarios] = useState<PricingScenario[]>([]);
  const [decisionDossier, setDecisionDossier] = useState<PatronDecisionDossier | null>(null);
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ tone: "success" | "error" | "warning"; text: string } | null>(null);
  const [showConnection, setShowConnection] = useState(false);
  const [activeNav, setActiveNav] = useState("overview");
  const api = useMemo(() => createApiClient(baseUrl, token), [baseUrl, token]);
  const {
    enterpriseCompany,
    enterpriseCapabilities,
    enterpriseCapabilityForm,
    enterpriseCapabilityVersionForm,
    enterpriseCompanyForm,
    enterpriseDocumentForm,
    enterpriseFile,
    enterpriseUploading,
    enterpriseVerificationDocumentId,
    enterpriseVerificationOutcome,
    enterpriseVerificationReason,
    setEnterpriseCapabilityForm,
    setEnterpriseCapabilityVersionForm,
    setEnterpriseCompanyForm,
    setEnterpriseDocumentForm,
    setEnterpriseFile,
    setEnterpriseVerificationDocumentId,
    setEnterpriseVerificationOutcome,
    setEnterpriseVerificationReason,
    refreshEnterpriseCompany,
    createEnterpriseCompany,
    createEnterpriseCapability,
    addEnterpriseCapabilityVersion,
    uploadEnterpriseDocument,
    verifyEnterpriseDocument,
  } = useEnterpriseLibrary(api, setMessage);
  const {
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
    loadCollaboratorWizard,
    evaluateWizardReadiness,
    generateWizardDocument,
    claimWizardTask,
    recordWizardTaskResult,
    completeWizardTask,
    transmitWizardSnapshot,
  } = useCollaboratorWizard(api, setMessage);
  const financialDraft = useFinancialDraft(api, setMessage, selectedCaseId);
  const cockpit = usePatronCockpit(api, setMessage, async (caseId) => {
    setSelectedCaseId(caseId);
    await refreshScenarios(caseId);
  });
  const {
    assignments,
    selectedAssignmentId,
    journal,
    interactions,
    refreshAssignments,
    selectAssignment,
  } = cockpit;
  const pricingImport = usePricingImport(
    api,
    setMessage,
    financialDraft.reportId,
    selectedCaseId,
    financialDraft.loadDraft,
  );
  const {
    reportId,
    draft,
    loadingDraft,
    lineForm,
    setReportId,
    setLineForm,
    createDraft,
    loadDraft,
    submitLine,
  } = financialDraft;
  const submissionActions = useSubmissionActions(api, setMessage);
  const summaryCards = draft
    ? [
        { label: "Ventes", value: formatMoney(draft.summary.sales_total_minor, draft.currency_code), accent: "blue" },
        { label: "Coûts directs", value: formatMoney(draft.summary.direct_cost_total_minor, draft.currency_code), accent: "amber" },
        { label: "Marge brute", value: formatMoney(draft.summary.gross_margin_minor, draft.currency_code), accent: "green" },
        { label: "Trésorerie", value: formatMoney(draft.summary.forecast_cashflow_minor, draft.currency_code), accent: "violet" },
      ]
    : [];

  useEffect(() => {
    if (!token.trim()) return;
    void refreshCases();
    void refreshAssignments();
    void refreshActions();
    void refreshEnterpriseCompany();
  }, []);

  useEffect(() => {
    if (!selectedCaseId || !token.trim()) return;
    void refreshScenarios(selectedCaseId);
    void refreshDecisionDossier(selectedCaseId);
  }, [selectedCaseId, token]);

  async function refreshCases() {
    setLoading(true);
    setMessage(null);
    try {
      const result = await api.listAssignedCases();
      setCases(result);
      if (!selectedCaseId && result[0]) setSelectedCaseId(result[0].case_id);
      setMessage({ tone: "success", text: `${result.length} affaire${result.length > 1 ? "s" : ""} chargée${result.length > 1 ? "s" : ""}.` });
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Impossible de charger les affaires." });
    } finally {
      setLoading(false);
    }
  }

  async function refreshActions() {
    try {
      const result = await api.listPatronActions();
      setActions(result.items);
    } catch {
      setActions([]);
    }
  }

  async function refreshScenarios(caseId: string) {
    try {
      setScenarios(await api.listPricingScenarios(caseId));
    } catch {
      setScenarios([]);
    }
  }

  async function refreshDecisionDossier(caseId: string) {
    try {
      setDecisionDossier(await api.getDecisionDossier(caseId));
    } catch {
      setDecisionDossier(null);
    }
  }

  function navigateTo(sectionId: string, navKey: string) {
    setActiveNav(navKey);
    document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function saveConnection(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    localStorage.setItem("smart-ao-api-url", baseUrl);
    localStorage.setItem("smart-ao-token", token);
    setShowConnection(false);
    setMessage({ tone: "success", text: "Connexion enregistrée dans ce navigateur." });
    void refreshCases();
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">S</span><span>SMART_AO <em>V8</em></span></div>
        <div className="workspace-label">ESPACE PATRON</div>
        <nav className="nav-list" aria-label="Navigation principale">
          <button className={`nav-item ${activeNav === "overview" ? "active" : ""}`} onClick={() => navigateTo("overview-section", "overview")}><span className="nav-icon">▦</span>Vue d’ensemble</button>
          <button className={`nav-item ${activeNav === "preparation" ? "active" : ""}`} onClick={() => navigateTo("preparation-section", "preparation")}><span className="nav-icon">◇</span>Préparation</button>
          <button className={`nav-item ${activeNav === "review" ? "active" : ""}`} onClick={() => navigateTo("review-section", "review")}><span className="nav-icon">◌</span>Revue</button>
          <button className={`nav-item ${activeNav === "wizard" ? "active" : ""}`} onClick={() => navigateTo("collaborator-wizard-section", "wizard")}><span className="nav-icon">⌁</span>Wizard collaborateur</button>
          <button className={`nav-item ${activeNav === "library" ? "active" : ""}`} onClick={() => navigateTo("library-section", "library")}><span className="nav-icon">▤</span>Bibliothèque</button>
          <button className={`nav-item ${activeNav === "decision" ? "active" : ""}`} onClick={() => navigateTo("decision-section", "decision")}><span className="nav-icon">◇</span>Décision</button>
          <button className={`nav-item ${activeNav === "submission" ? "active" : ""}`} onClick={() => navigateTo("submission-section", "submission")}><span className="nav-icon">↗</span>Dépôt</button>
        </nav>
        <div className="sidebar-bottom">
          <button className="nav-item" onClick={() => setShowConnection(true)}><span className="nav-icon">⚙</span>Connexion API</button>
          <div className="operator-card"><div className="avatar">PA</div><div><strong>Patron administrateur</strong><span>Accès financier contrôlé</span></div></div>
        </div>
      </aside>

      <main className="content">
        <header className="topbar">
          <div><div className="eyebrow">PILOTAGE DES RÉPONSES</div><h1>Vue d’ensemble</h1><p className="lede">Une lecture claire de vos affaires, de vos alertes et de vos chiffrages en cours.</p></div>
          <div className="top-actions"><div className="secure-pill"><span className="status-dot" />Données confidentielles</div><button className="refresh-button" onClick={() => void refreshCases()} disabled={loading}><span>↻</span> Actualiser</button></div>
        </header>

        {message && <div className={`notice ${message.tone}`} role="status"><span>{message.tone === "success" ? "✓" : "!"}</span>{message.text}</div>}

        <section className="section-block command-center-section" id="overview-section">
          <div className="section-heading"><div><span className="section-kicker">COMMAND CENTER</span><h2>Actions à traiter</h2></div><span className="count-pill">{actions.length} ouverte{actions.length > 1 ? "s" : ""}</span></div>
          {actions.length === 0 ? <div className="empty-card"><strong>Aucune action patronale ouverte</strong><p>Les transmissions et contrôles autorisés alimenteront cette file tenant-scopée.</p></div> : <div className="action-grid">{actions.slice(0, 6).map((action) => <article className="action-card" key={action.action_id}><div className="case-top"><span className={`state-badge state-${action.severity.toLowerCase()}`}>{action.severity}</span><span className="rule-tag">{action.state}</span></div><h3>{action.title}</h3><p>{action.why_now}</p><small>{action.recommended_action}</small></article>)}</div>}
        </section>

        <section className="section-block" id="library-section">
          <div className="section-heading"><div><span className="section-kicker">BIBLIOTHÈQUE PATRONALE</span><h2>Entreprise & prix privés</h2></div><span className="count-pill">{enterpriseCompany?.documents.length ?? 0} pièce{(enterpriseCompany?.documents.length ?? 0) > 1 ? "s" : ""}</span></div>
          {!enterpriseCompany ? <div className="detail-panel enterprise-company-panel"><div className="panel-heading"><div><h3>Créer la fiche entreprise</h3><p>La société légale est tenant-scopée et reste accessible au patron uniquement.</p></div><span className="rule-tag">PATRON</span></div><div className="enterprise-form-grid"><label><span>Raison sociale</span><input required value={enterpriseCompanyForm.legal_name} onChange={(event) => setEnterpriseCompanyForm({ ...enterpriseCompanyForm, legal_name: event.target.value })} placeholder="Entreprise BTP" /></label><label><span>Nom commercial</span><input value={enterpriseCompanyForm.trade_name} onChange={(event) => setEnterpriseCompanyForm({ ...enterpriseCompanyForm, trade_name: event.target.value })} placeholder="Optionnel" /></label><label><span>SIREN</span><input required pattern="[0-9]{9}" value={enterpriseCompanyForm.siren} onChange={(event) => setEnterpriseCompanyForm({ ...enterpriseCompanyForm, siren: event.target.value })} placeholder="9 chiffres" /></label><label><span>SIRET</span><input required pattern="[0-9]{14}" value={enterpriseCompanyForm.siret} onChange={(event) => setEnterpriseCompanyForm({ ...enterpriseCompanyForm, siret: event.target.value })} placeholder="14 chiffres" /></label><label><span>TVA intracommunautaire</span><input required value={enterpriseCompanyForm.vat_number} onChange={(event) => setEnterpriseCompanyForm({ ...enterpriseCompanyForm, vat_number: event.target.value.toUpperCase() })} placeholder="FR..." /></label><label><span>Adresse</span><input required value={enterpriseCompanyForm.address_line1} onChange={(event) => setEnterpriseCompanyForm({ ...enterpriseCompanyForm, address_line1: event.target.value })} /></label><label><span>Code postal</span><input required value={enterpriseCompanyForm.postal_code} onChange={(event) => setEnterpriseCompanyForm({ ...enterpriseCompanyForm, postal_code: event.target.value })} /></label><label><span>Ville</span><input required value={enterpriseCompanyForm.city} onChange={(event) => setEnterpriseCompanyForm({ ...enterpriseCompanyForm, city: event.target.value })} /></label><label><span>Pays</span><input required pattern="[A-Z]{2}" maxLength={2} value={enterpriseCompanyForm.country_code} onChange={(event) => setEnterpriseCompanyForm({ ...enterpriseCompanyForm, country_code: event.target.value.toUpperCase() })} /></label></div><button className="primary-button" type="button" onClick={() => void createEnterpriseCompany()}>Créer la fiche entreprise <span>→</span></button></div> : <div className="enterprise-library-grid"><div className="detail-panel enterprise-company-panel"><div className="panel-heading"><div><h3>{enterpriseCompany.legal_name}</h3><p>{enterpriseCompany.trade_name ?? "Fiche légale patronale"}</p></div><span className="state-badge state-active">RÉVISION {enterpriseCompany.aggregate_revision}</span></div><div className="enterprise-facts"><span><small>SIREN</small><strong>{enterpriseCompany.siren}</strong></span><span><small>SIRET</small><strong>{enterpriseCompany.siret}</strong></span><span><small>TVA</small><strong>{enterpriseCompany.vat_number}</strong></span><span><small>Adresse</small><strong>{enterpriseCompany.address_line1}, {enterpriseCompany.postal_code} {enterpriseCompany.city}</strong></span></div></div><div className="detail-panel enterprise-company-panel"><div className="panel-heading"><div><h3>Pièces de l’entreprise</h3><p>Documents versionnés, statuts de vérification et dates de validité.</p></div><span className="rule-tag">{enterpriseCompany.documents.length} pièce{enterpriseCompany.documents.length > 1 ? "s" : ""}</span></div>{enterpriseCompany.documents.length === 0 ? <p className="panel-empty">Aucune pièce enregistrée. Le parcours d’upload privé reste piloté par les routes sécurisées.</p> : <div className="enterprise-document-list">{enterpriseCompany.documents.map((document) => <div className="enterprise-document-row" key={document.document_id}><div><strong>{document.document_kind} · {document.document_label}</strong><small>Émis le {formatDate(document.issued_at)}{document.expires_at ? ` · Expire le ${formatDate(document.expires_at)}` : ""}</small></div><span className={`state-badge state-${document.verification_status.toLowerCase()}`}>{document.verification_status}</span><button className="secondary-button document-review-button" type="button" onClick={() => setEnterpriseVerificationDocumentId(document.document_id)}>Vérifier</button></div>)}</div>}</div></div>}
          {enterpriseCompany && <div className="detail-panel enterprise-capability-panel"><div className="panel-heading"><div><h3>Passeport capacités & références</h3><p>Qualifications, références, équipes et moyens restent dans le périmètre patronal.</p></div><span className="rule-tag">{enterpriseCapabilities.length} capacité{enterpriseCapabilities.length > 1 ? "s" : ""}</span></div><div className="enterprise-capability-grid"><label><span>Type</span><select value={enterpriseCapabilityForm.capability_kind} onChange={(event) => setEnterpriseCapabilityForm({ ...enterpriseCapabilityForm, capability_kind: event.target.value as EnterpriseCapabilityKind })}><option value="QUALIFICATION">Qualification</option><option value="REFERENCE">Référence</option><option value="EQUIPMENT">Équipement</option><option value="TEAM">Équipe</option><option value="METHOD">Méthode</option></select></label><label><span>Nom</span><input value={enterpriseCapabilityForm.name} onChange={(event) => setEnterpriseCapabilityForm({ ...enterpriseCapabilityForm, name: event.target.value })} placeholder="Certification travaux publics" /></label><label><span>Résumé</span><input value={enterpriseCapabilityForm.summary} onChange={(event) => setEnterpriseCapabilityForm({ ...enterpriseCapabilityForm, summary: event.target.value })} placeholder="Qualification et périmètre" /></label><button className="primary-button" type="button" onClick={() => void createEnterpriseCapability()}>Créer la capacité <span>→</span></button></div>{enterpriseCapabilities.length > 0 && <div className="enterprise-capability-list">{enterpriseCapabilities.map((capability) => <div className="enterprise-capability-row" key={capability.capability_id}><div><strong>{capability.capability_kind} · {capability.name}</strong><small>{capability.summary} · Révision {capability.aggregate_revision} · {capability.versions.length} version{capability.versions.length > 1 ? "s" : ""}</small></div><span className={`state-badge state-${capability.state.toLowerCase()}`}>{capability.state}</span></div>)}</div>}<div className="enterprise-version-grid"><label><span>Capacité à versionner</span><select value={enterpriseCapabilityVersionForm.capability_id} onChange={(event) => { const capability = enterpriseCapabilities.find((item) => item.capability_id === event.target.value); setEnterpriseCapabilityVersionForm({ ...enterpriseCapabilityVersionForm, capability_id: event.target.value, expected_revision: String(capability?.aggregate_revision ?? 0) }); }}><option value="">Sélectionner</option>{enterpriseCapabilities.map((capability) => <option key={capability.capability_id} value={capability.capability_id}>{capability.name} · v{capability.aggregate_revision}</option>)}</select></label><label><span>Titre de version</span><input value={enterpriseCapabilityVersionForm.title} onChange={(event) => setEnterpriseCapabilityVersionForm({ ...enterpriseCapabilityVersionForm, title: event.target.value })} placeholder="Référence chantier 2026" /></label><label><span>Valide à partir du</span><input type="date" value={enterpriseCapabilityVersionForm.valid_from} onChange={(event) => setEnterpriseCapabilityVersionForm({ ...enterpriseCapabilityVersionForm, valid_from: event.target.value })} /></label><label><span>Valide jusqu’au</span><input type="date" value={enterpriseCapabilityVersionForm.valid_until} onChange={(event) => setEnterpriseCapabilityVersionForm({ ...enterpriseCapabilityVersionForm, valid_until: event.target.value })} /></label><label><span>Périmètre d’usage</span><input value={enterpriseCapabilityVersionForm.usage_scope} onChange={(event) => setEnterpriseCapabilityVersionForm({ ...enterpriseCapabilityVersionForm, usage_scope: event.target.value })} placeholder="Dossier de candidature BTP" /></label><label><span>Description</span><textarea rows={2} value={enterpriseCapabilityVersionForm.description} onChange={(event) => setEnterpriseCapabilityVersionForm({ ...enterpriseCapabilityVersionForm, description: event.target.value })} placeholder="Preuve, contexte et limites d’usage" /></label><button className="secondary-button" type="button" onClick={() => void addEnterpriseCapabilityVersion()}>Ajouter la version</button></div><small className="invariant-note">Seules les pièces au statut <strong>VALIDATED</strong> sont automatiquement proposées comme preuves.</small></div>}
          {enterpriseCompany && enterpriseVerificationDocumentId && <div className="detail-panel enterprise-verification-panel"><div className="panel-heading"><div><h3>Vérifier une pièce</h3><p>La décision humaine est append-only et porte sur la révision serveur affichée.</p></div><span className="rule-tag">RÉVISION {enterpriseCompany.documents.find((document) => document.document_id === enterpriseVerificationDocumentId)?.verification_revision ?? 0}</span></div><div className="enterprise-verification-grid"><label><span>Décision</span><select value={enterpriseVerificationOutcome} onChange={(event) => { const outcome = event.target.value as "VALIDATED" | "REJECTED"; setEnterpriseVerificationOutcome(outcome); setEnterpriseVerificationReason(outcome === "VALIDATED" ? "DOCUMENT_ACCEPTED" : "DOCUMENT_ILLEGIBLE"); }}><option value="VALIDATED">Valider</option><option value="REJECTED">Rejeter</option></select></label><label><span>Motif</span><select value={enterpriseVerificationReason} disabled={enterpriseVerificationOutcome === "VALIDATED"} onChange={(event) => setEnterpriseVerificationReason(event.target.value as "DOCUMENT_ACCEPTED" | "DOCUMENT_ILLEGIBLE" | "DOCUMENT_EXPIRED" | "DOCUMENT_MISMATCH" | "DOCUMENT_DUPLICATE")}><option value="DOCUMENT_ACCEPTED">Document accepté</option><option value="DOCUMENT_ILLEGIBLE">Document illisible</option><option value="DOCUMENT_EXPIRED">Document expiré</option><option value="DOCUMENT_MISMATCH">Document incohérent</option><option value="DOCUMENT_DUPLICATE">Document dupliqué</option></select></label><button className="primary-button" type="button" onClick={() => void verifyEnterpriseDocument()}>Enregistrer la décision <span>→</span></button></div></div>}
          {enterpriseCompany && <div className="detail-panel enterprise-upload-panel"><div className="panel-heading"><div><h3>Ajouter une pièce</h3><p>Le binaire est envoyé uniquement vers la quarantaine privée ; le serveur calcule hash, MIME et verdict ClamAV.</p></div><span className="secure-pill"><span className="status-dot" />CONFIDENTIEL</span></div><div className="enterprise-upload-grid"><label><span>Type de pièce</span><select value={enterpriseDocumentForm.document_kind} onChange={(event) => setEnterpriseDocumentForm({ ...enterpriseDocumentForm, document_kind: event.target.value as EnterpriseDocumentKind })}><option value="KBIS">Kbis</option><option value="INSURANCE">Assurance</option><option value="RIB">RIB</option></select></label><label><span>Libellé</span><input required value={enterpriseDocumentForm.document_label} onChange={(event) => setEnterpriseDocumentForm({ ...enterpriseDocumentForm, document_label: event.target.value })} placeholder="Kbis 2026" /></label><label><span>Expiration</span><input required type="date" value={enterpriseDocumentForm.expires_at} onChange={(event) => setEnterpriseDocumentForm({ ...enterpriseDocumentForm, expires_at: event.target.value })} /></label><label><span>Fichier</span><input required type="file" accept=".pdf,.docx,.xlsx,.txt" onChange={(event) => setEnterpriseFile(event.target.files?.[0] ?? null)} /></label></div><button className="primary-button" type="button" onClick={() => void uploadEnterpriseDocument()} disabled={enterpriseUploading || !enterpriseFile}>{enterpriseUploading ? "Contrôle en cours…" : "Téléverser et enregistrer"}<span>→</span></button><small className="invariant-note">Après CLEAN, le document est créé en statut <strong>PENDING</strong> ; la vérification humaine reste une action séparée.</small></div>}
          <PricingPanel
            scenarios={scenarios}
            formatMoney={formatMoney}
            selectedCaseId={selectedCaseId}
            reportId={reportId}
            pricingImportBatchId={pricingImport.pricingImportBatchId}
            pricingImportBatchRevision={pricingImport.pricingImportBatchRevision}
            pricingImportReportRevision={pricingImport.pricingImportReportRevision}
            pricingImportState={pricingImport.pricingImportState}
            pricingImportReloadState={pricingImport.pricingImportReloadState}
            pricingImportSubmitting={pricingImport.pricingImportSubmitting}
            setPricingImportBatchId={pricingImport.setPricingImportBatchId}
            setPricingImportBatchRevision={pricingImport.setPricingImportBatchRevision}
            setPricingImportReportRevision={pricingImport.setPricingImportReportRevision}
            onCommit={() => void pricingImport.commitPricingImport()}
          />
        </section>

        <section className="hero-grid" id="preparation-section">
          <div className="hero-card"><div className="hero-copy"><span className="hero-kicker">CETTE SEMAINE</span><h2>Décider avec la<br /><strong>bonne information.</strong></h2><p>Retrouvez vos affaires actives et reprenez chaque chiffrage là où vous l’avez laissé.</p><button className="primary-button" onClick={() => document.getElementById("draft-section")?.scrollIntoView({ behavior: "smooth" })}>Ouvrir un chiffrage <span>→</span></button></div><div className="hero-orbit"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="orbit-core">AO<br /><small>V8</small></div></div></div>
          <div className="metric-stack"><div className="small-metric"><span className="metric-label">AFFAIRES ACTIVES</span><strong>{cases.length.toString().padStart(2, "0")}</strong><span className="metric-meta">dans votre périmètre</span></div><div className="small-metric"><span className="metric-label">ÉTAT DE LA CONNEXION</span><strong className={token.trim() ? "text-green" : "text-amber"}>{token.trim() ? "Prête" : "À configurer"}</strong><span className="metric-meta">{baseUrl}</span></div></div>
        </section>

        <section className="section-block" id="review-section"><div className="section-heading"><div><span className="section-kicker">PORTEFEUILLE</span><h2>Mes affaires</h2></div><span className="count-pill">{cases.length} visible{cases.length > 1 ? "s" : ""}</span></div><div className="case-grid">{cases.length === 0 ? <div className="empty-card"><strong>Aucune affaire chargée</strong><p>Configurez votre Bearer token puis actualisez pour charger les affaires auxquelles vous avez accès.</p><button className="secondary-button" onClick={() => setShowConnection(true)}>Configurer la connexion</button></div> : cases.map((item) => <button key={item.case_id} className={`case-card ${item.case_id === selectedCaseId ? "selected" : ""}`} onClick={() => setSelectedCaseId(item.case_id)}><div className="case-top"><span className="case-status">{item.dce_availability}</span><span className="case-arrow">↗</span></div><h3>{item.work_label}</h3><p>{item.case_id}</p><div className="case-footer"><span>{item.commercial_stage}</span><span>{item.case_lifecycle}</span></div></button>)}</div></section>

        <CollaboratorWizardPanel
          wizardCaseId={wizardCaseId}
          wizardPackageId={wizardPackageId}
          wizardPackage={wizardPackage}
          wizardTasks={wizardTasks}
          wizardTaskId={wizardTaskId}
          wizardResultText={wizardResultText}
          wizardOutcome={wizardOutcome}
          wizardSnapshotId={wizardSnapshotId}
          wizardTransmissionId={wizardTransmissionId}
          setWizardCaseId={setWizardCaseId}
          setWizardPackageId={setWizardPackageId}
          setWizardTaskId={setWizardTaskId}
          setWizardResultText={setWizardResultText}
          setWizardOutcome={setWizardOutcome}
          setWizardSnapshotId={setWizardSnapshotId}
          setWizardTransmissionId={setWizardTransmissionId}
          onLoad={() => void loadCollaboratorWizard()}
          onClaimTask={() => void claimWizardTask()}
          onRecordResult={() => void recordWizardTaskResult()}
          onCompleteTask={() => void completeWizardTask()}
          onEvaluateReadiness={() => void evaluateWizardReadiness()}
          onGenerateDocument={() => void generateWizardDocument()}
          onTransmitSnapshot={() => void transmitWizardSnapshot()}
        />

        <PatronCockpitPanel
          assignments={assignments}
          selectedAssignmentId={selectedAssignmentId}
          journal={journal}
          interactions={interactions}
          onSelectAssignment={(assignment) => void selectAssignment(assignment)}
        />

        <PatronDecisionPanel decisionDossier={decisionDossier} formatDate={formatDate} />

        <SubmissionPanel
          preparationPackageId={submissionActions.preparationPackageId}
          preparationRevision={submissionActions.preparationRevision}
          submissionPackageId={submissionActions.submissionPackageId}
          submissionExported={submissionActions.submissionExported}
          evidenceForm={submissionActions.evidenceForm}
          setPreparationPackageId={submissionActions.setPreparationPackageId}
          setPreparationRevision={submissionActions.setPreparationRevision}
          setSubmissionPackageId={submissionActions.setSubmissionPackageId}
          setEvidenceForm={submissionActions.setEvidenceForm}
          onPrepare={() => void submissionActions.prepareSubmissionPackage()}
          onExport={() => void submissionActions.exportSubmissionPackage()}
          onRecordEvidence={() => void submissionActions.recordSubmissionEvidence()}
        />

        <FinancialDraftPanel
          cases={cases}
          selectedCaseId={selectedCaseId}
          setSelectedCaseId={setSelectedCaseId}
          reportId={reportId}
          setReportId={setReportId}
          draft={draft}
          loadingDraft={loadingDraft}
          lineForm={lineForm}
          setLineForm={setLineForm}
          summaryCards={summaryCards}
          createDraft={() => void createDraft()}
          loadDraft={() => void loadDraft()}
          submitLine={submitLine}
          formatMoney={formatMoney}
          formatDate={formatDate}
          categoryLabel={categoryLabel}
        />

        <footer className="footer"><span>SMART_AO V8</span><span>Architecture sécurisée · Tenant-scoped · Auditée</span><span>API {baseUrl}</span></footer>
      </main>

      {showConnection && <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) setShowConnection(false); }}><form className="connection-modal" onSubmit={saveConnection}><div className="modal-top"><div><span className="section-kicker">CONFIGURATION</span><h2>Connexion au backend</h2></div><button type="button" className="close-button" onClick={() => setShowConnection(false)}>×</button></div><p>Le token est conservé uniquement dans le stockage local de ce navigateur. Il n’est jamais envoyé ailleurs que vers l’URL configurée.</p><label><span>URL API</span><input required value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} /></label><label><span>Bearer token</span><textarea required rows={4} value={token} onChange={(event) => setToken(event.target.value)} placeholder="eyJhbGciOiJIUzI1NiIs…" /></label><button className="primary-button" type="submit">Enregistrer et charger <span>→</span></button></form></div>}
    </div>
  );
}

export default App;
