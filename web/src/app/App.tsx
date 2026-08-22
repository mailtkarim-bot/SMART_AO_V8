import { useEffect, useState } from "react";
import { PricingPanel } from "../features/pricing/PricingPanel";
import { usePricingImport } from "../features/pricing/usePricingImport";
import { SubmissionPanel } from "../features/submission/SubmissionPanel";
import { useSubmissionActions } from "../features/submission/useSubmissionActions";
import { EnterpriseLibraryPanel } from "../features/enterprise/EnterpriseLibraryPanel";
import { useEnterpriseLibrary } from "../features/enterprise/useEnterpriseLibrary";
import { CollaboratorWizardPanel } from "../features/wizard/CollaboratorWizardPanel";
import { useCollaboratorWizard } from "../features/wizard/useCollaboratorWizard";
import { PatronCockpitPanel } from "../features/cockpit/PatronCockpitPanel";
import { PatronDecisionPanel } from "../features/decision/PatronDecisionPanel";
import { usePatronCockpit } from "../features/cockpit/usePatronCockpit";
import { FinancialDraftPanel } from "../features/draft/FinancialDraftPanel";
import { useFinancialDraft } from "../features/draft/useFinancialDraft";
import { useAuthentication } from "../features/auth/useAuthentication";
import { useBackendReadiness } from "../features/connection/useBackendReadiness";
import {
  assertRuntimeApiUrl,
  resolveApiBaseUrl,
} from "../infrastructure/runtimeConfig";
import type {
  AssignedCase,
  FinancialCategory,
  PatronAction,
  PatronDecisionDossier,
  PricingScenario,
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
  const [baseUrl, setBaseUrl] = useState(() =>
    resolveApiBaseUrl(
      import.meta.env.VITE_API_BASE_URL,
      window.location.protocol,
      window.location.origin,
    ),
  );
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [tenantId, setTenantId] = useState("");
  const [cases, setCases] = useState<AssignedCase[]>([]);
  const [actions, setActions] = useState<PatronAction[]>([]);
  const [scenarios, setScenarios] = useState<PricingScenario[]>([]);
  const [decisionDossier, setDecisionDossier] = useState<PatronDecisionDossier | null>(null);
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ tone: "success" | "error" | "warning"; text: string } | null>(null);
  const [showConnection, setShowConnection] = useState(false);
  const [activeNav, setActiveNav] = useState("overview");
  const {
    accessToken,
    currentActor,
    isRestoring,
    isAuthenticated,
    api,
    login,
    logout,
  } = useAuthentication(baseUrl);
  const {
    backendReadiness,
    backendReadinessState,
    checkBackendReadiness,
  } = useBackendReadiness(api);
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
    if (!accessToken.trim()) return;
    void refreshCases();
    void refreshAssignments();
    void refreshActions();
    void refreshEnterpriseCompany();
  }, [accessToken]);

  useEffect(() => {
    if (!selectedCaseId || !accessToken.trim()) return;
    void refreshScenarios(selectedCaseId);
    void refreshDecisionDossier(selectedCaseId);
  }, [selectedCaseId, accessToken]);

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
    } catch (error) {
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Impossible de charger les actions.",
      });
    }
  }

  async function refreshScenarios(caseId: string) {
    try {
      setScenarios(await api.listPricingScenarios(caseId));
    } catch (error) {
      setMessage({
        tone: "error",
        text:
          error instanceof Error
            ? error.message
            : "Impossible de charger les scénarios de chiffrage.",
      });
    }
  }

  async function refreshDecisionDossier(caseId: string) {
    try {
      setDecisionDossier(await api.getDecisionDossier(caseId));
    } catch (error) {
      setDecisionDossier(null);
      // 404 = pas encore de dossier de décision pour cette affaire : état normal.
      if ((error as { status?: number }).status === 404) return;
      setMessage({
        tone: "error",
        text:
          error instanceof Error
            ? error.message
            : "Impossible de charger le dossier de décision.",
      });
    }
  }

  function navigateTo(sectionId: string, navKey: string) {
    setActiveNav(navKey);
    document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function saveConnection(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const normalizedBaseUrl = assertRuntimeApiUrl(
        baseUrl,
        window.location.protocol,
        window.location.origin,
      );
      if (normalizedBaseUrl !== baseUrl) {
        setBaseUrl(normalizedBaseUrl);
        setMessage({ tone: "warning", text: "URL API enregistrée. Validez de nouveau la connexion avec cette origine." });
        return;
      }
      await checkBackendReadiness();
      await login({ email: loginEmail, password: loginPassword, tenant_id: tenantId });
      setLoginPassword("");
      setShowConnection(false);
      setMessage({ tone: "success", text: "Connexion sécurisée active." });
    } catch (error) {
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Connexion impossible.",
      });
    }
  }

  async function signOut() {
    try {
      await logout();
      setMessage({ tone: "success", text: "Session fermée." });
    } catch (error) {
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Impossible de fermer la session.",
      });
    }
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
          <button className="nav-item" onClick={() => setShowConnection(true)}><span className="nav-icon">⚙</span>{isAuthenticated ? "Session" : "Connexion"}</button>
          {isAuthenticated && <button className="nav-item" onClick={() => void signOut()}><span className="nav-icon">↪</span>Se déconnecter</button>}
          <div className="operator-card"><div className="avatar">{currentActor?.actor_kind === "COLLABORATEUR" ? "CO" : "PA"}</div><div><strong>{currentActor?.actor_kind ?? "Utilisateur non connecté"}</strong><span>{currentActor ? `Membership ${currentActor.membership_state}` : "Authentification requise"}</span></div></div>
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

        <EnterpriseLibraryPanel
          enterpriseCompany={enterpriseCompany}
          enterpriseCapabilities={enterpriseCapabilities}
          enterpriseCapabilityForm={enterpriseCapabilityForm}
          enterpriseCapabilityVersionForm={enterpriseCapabilityVersionForm}
          enterpriseCompanyForm={enterpriseCompanyForm}
          enterpriseDocumentForm={enterpriseDocumentForm}
          enterpriseFile={enterpriseFile}
          enterpriseUploading={enterpriseUploading}
          enterpriseVerificationDocumentId={enterpriseVerificationDocumentId}
          enterpriseVerificationOutcome={enterpriseVerificationOutcome}
          enterpriseVerificationReason={enterpriseVerificationReason}
          setEnterpriseCapabilityForm={setEnterpriseCapabilityForm}
          setEnterpriseCapabilityVersionForm={setEnterpriseCapabilityVersionForm}
          setEnterpriseCompanyForm={setEnterpriseCompanyForm}
          setEnterpriseDocumentForm={setEnterpriseDocumentForm}
          setEnterpriseFile={setEnterpriseFile}
          setEnterpriseVerificationDocumentId={setEnterpriseVerificationDocumentId}
          setEnterpriseVerificationOutcome={setEnterpriseVerificationOutcome}
          setEnterpriseVerificationReason={setEnterpriseVerificationReason}
          formatDate={formatDate}
          onCreateCompany={() => void createEnterpriseCompany()}
          onCreateCapability={() => void createEnterpriseCapability()}
          onAddCapabilityVersion={() => void addEnterpriseCapabilityVersion()}
          onUploadDocument={() => void uploadEnterpriseDocument()}
          onVerifyDocument={() => void verifyEnterpriseDocument()}
        />

        <section className="section-block" id="pricing-section">
          <PricingPanel
            scenarios={scenarios}
            formatMoney={formatMoney}
            selectedCaseId={selectedCaseId}
            reportId={reportId}
            pricingImportBatchId={pricingImport.pricingImportBatchId}
            pricingImportBatchRevision={pricingImport.pricingImportBatchRevision}
            pricingImportReportRevision={pricingImport.pricingImportReportRevision}
            pricingImportState={pricingImport.pricingImportState}
            pricingImportPreview={pricingImport.pricingImportPreview}
            pricingImportReloadState={pricingImport.pricingImportReloadState}
            pricingImportUploading={pricingImport.pricingImportUploading}
            pricingImportLoading={pricingImport.pricingImportLoading}
            pricingImportSubmitting={pricingImport.pricingImportSubmitting}
            setPricingImportBatchId={pricingImport.setPricingImportBatchId}
            setPricingImportBatchRevision={pricingImport.setPricingImportBatchRevision}
            setPricingImportReportRevision={pricingImport.setPricingImportReportRevision}
            onPreview={(file) => void pricingImport.previewPricingImport(file)}
            onReload={() => void pricingImport.reloadPricingImport()}
            onCommit={() => void pricingImport.commitPricingImport()}
          />
        </section>

        <section className="hero-grid" id="preparation-section">
          <div className="hero-card"><div className="hero-copy"><span className="hero-kicker">CETTE SEMAINE</span><h2>Décider avec la<br /><strong>bonne information.</strong></h2><p>Retrouvez vos affaires actives et reprenez chaque chiffrage là où vous l’avez laissé.</p><button className="primary-button" onClick={() => document.getElementById("draft-section")?.scrollIntoView({ behavior: "smooth" })}>Ouvrir un chiffrage <span>→</span></button></div><div className="hero-orbit"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="orbit-core">AO<br /><small>V8</small></div></div></div>
          <div className="metric-stack"><div className="small-metric"><span className="metric-label">AFFAIRES ACTIVES</span><strong>{cases.length.toString().padStart(2, "0")}</strong><span className="metric-meta">dans votre périmètre</span></div><div className="small-metric"><span className="metric-label">ÉTAT DE LA CONNEXION</span><strong className={isAuthenticated ? "text-green" : "text-amber"}>{isAuthenticated ? "Prête" : isRestoring ? "Restauration…" : "À configurer"}</strong><span className="metric-meta">{baseUrl}</span></div></div>
        </section>

        <section className="section-block" id="review-section"><div className="section-heading"><div><span className="section-kicker">PORTEFEUILLE</span><h2>Mes affaires</h2></div><span className="count-pill">{cases.length} visible{cases.length > 1 ? "s" : ""}</span></div><div className="case-grid">{cases.length === 0 ? <div className="empty-card"><strong>Aucune affaire chargée</strong><p>Connectez-vous avec votre compte pour charger les affaires auxquelles vous avez accès.</p><button className="secondary-button" onClick={() => setShowConnection(true)}>Configurer la connexion</button></div> : cases.map((item) => <button key={item.case_id} className={`case-card ${item.case_id === selectedCaseId ? "selected" : ""}`} onClick={() => setSelectedCaseId(item.case_id)}><div className="case-top"><span className="case-status">{item.dce_availability}</span><span className="case-arrow">↗</span></div><h3>{item.work_label}</h3><p>{item.case_id}</p><div className="case-footer"><span>{item.commercial_stage}</span><span>{item.case_lifecycle}</span></div></button>)}</div></section>

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

      {showConnection && <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) setShowConnection(false); }}><form className="connection-modal" role="dialog" aria-modal="true" aria-labelledby="connection-modal-title" onSubmit={saveConnection}><div className="modal-top"><div><span className="section-kicker">CONFIGURATION</span><h2 id="connection-modal-title">Connexion au backend</h2></div><button type="button" className="close-button" onClick={() => setShowConnection(false)}>×</button></div><p>La session utilise un cookie de renouvellement HttpOnly et un jeton d’accès conservé uniquement en mémoire.</p><label><span>URL API</span><input required value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} /></label><div className={`readiness-indicator readiness-${backendReadinessState}`} role="status"><strong>{backendReadinessState === "checking" ? "Vérification en cours…" : backendReadinessState === "ready" ? "Backend prêt" : backendReadinessState === "not_ready" ? "Backend non prêt" : backendReadinessState === "error" ? "Backend inaccessible" : "Backend non vérifié"}</strong>{backendReadiness && <small>PostgreSQL : {backendReadiness.checks.database} · ClamAV : {backendReadiness.checks.clamav}</small>}</div><label><span>Email</span><input required type="email" autoComplete="username" value={loginEmail} onChange={(event) => setLoginEmail(event.target.value)} /></label><label><span>Tenant ID</span><input required value={tenantId} onChange={(event) => setTenantId(event.target.value)} /></label><label><span>Mot de passe</span><input required type="password" autoComplete="current-password" value={loginPassword} onChange={(event) => setLoginPassword(event.target.value)} /></label><button className="primary-button" type="submit">Se connecter <span>→</span></button></form></div>}
    </div>
  );
}

export default App;
