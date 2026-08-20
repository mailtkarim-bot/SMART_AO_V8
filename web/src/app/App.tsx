import { useEffect, useMemo, useState } from "react";
import { PricingPanel } from "../features/pricing/PricingPanel";
import { usePricingImport } from "../features/pricing/usePricingImport";
import { SubmissionPanel } from "../features/submission/SubmissionPanel";
import { useSubmissionActions } from "../features/submission/useSubmissionActions";
import { createApiClient } from "../infrastructure/api";
import type {
  AssignedCase,
  DraftReport,
  FinancialCategory,
  PatronAssignment,
  PatronAssignmentInteractions,
  PatronAssignmentJournalItem,
  PatronAction,
  PatronDecisionDossier,
  PricingScenario,
  EnterpriseCompany,
  EnterpriseDocumentKind,
  EnterpriseCapability,
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
  const [assignments, setAssignments] = useState<PatronAssignment[]>([]);
  const [selectedAssignmentId, setSelectedAssignmentId] = useState("");
  const [journal, setJournal] = useState<PatronAssignmentJournalItem[]>([]);
  const [interactions, setInteractions] = useState<PatronAssignmentInteractions | null>(null);
  const [actions, setActions] = useState<PatronAction[]>([]);
  const [scenarios, setScenarios] = useState<PricingScenario[]>([]);
  const [decisionDossier, setDecisionDossier] = useState<PatronDecisionDossier | null>(null);
  const [enterpriseCompany, setEnterpriseCompany] = useState<EnterpriseCompany | null>(null);
  const [enterpriseCapabilities, setEnterpriseCapabilities] = useState<EnterpriseCapability[]>([]);
  const [enterpriseCapabilityForm, setEnterpriseCapabilityForm] = useState({
    capability_kind: "QUALIFICATION" as EnterpriseCapabilityKind,
    name: "",
    summary: "",
  });
  const [enterpriseCapabilityVersionForm, setEnterpriseCapabilityVersionForm] = useState({
    capability_id: "",
    expected_revision: "0",
    title: "",
    description: "",
    valid_from: "",
    valid_until: "",
    usage_scope: "",
  });
  const [enterpriseCompanyForm, setEnterpriseCompanyForm] = useState({
    legal_name: "",
    trade_name: "",
    siren: "",
    siret: "",
    vat_number: "",
    address_line1: "",
    postal_code: "",
    city: "",
    country_code: "FR",
  });
  const [enterpriseDocumentForm, setEnterpriseDocumentForm] = useState({
    document_kind: "KBIS" as EnterpriseDocumentKind,
    document_label: "",
    expires_at: "",
  });
  const [enterpriseFile, setEnterpriseFile] = useState<File | null>(null);
  const [enterpriseUploading, setEnterpriseUploading] = useState(false);
  const [enterpriseVerificationDocumentId, setEnterpriseVerificationDocumentId] = useState("");
  const [enterpriseVerificationOutcome, setEnterpriseVerificationOutcome] = useState<"VALIDATED" | "REJECTED">("VALIDATED");
  const [enterpriseVerificationReason, setEnterpriseVerificationReason] = useState<
    "DOCUMENT_ACCEPTED" | "DOCUMENT_ILLEGIBLE" | "DOCUMENT_EXPIRED" | "DOCUMENT_MISMATCH" | "DOCUMENT_DUPLICATE"
  >("DOCUMENT_ACCEPTED");
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const [reportId, setReportId] = useState("");
  const [draft, setDraft] = useState<DraftReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingDraft, setLoadingDraft] = useState(false);
  const [message, setMessage] = useState<{ tone: "success" | "error" | "warning"; text: string } | null>(null);
  const [showConnection, setShowConnection] = useState(false);
  const [activeNav, setActiveNav] = useState("overview");
  const [wizardCaseId, setWizardCaseId] = useState("");
  const [wizardPackageId, setWizardPackageId] = useState("");
  const [wizardPackage, setWizardPackage] = useState<import("../shared/types").PreparationPackage | null>(null);
  const [wizardTasks, setWizardTasks] = useState<import("../shared/types").CollaboratorTask[]>([]);
  const [wizardTaskId, setWizardTaskId] = useState("");
  const [wizardResultText, setWizardResultText] = useState("");
  const [wizardOutcome, setWizardOutcome] = useState<"RECORDED" | "NOT_APPLICABLE" | "UNABLE_TO_COMPLETE">("RECORDED");
  const [wizardSnapshotId, setWizardSnapshotId] = useState("");
  const [wizardTransmissionId, setWizardTransmissionId] = useState("");
  const [lineForm, setLineForm] = useState({
    category: "SALES" as FinancialCategory,
    label: "",
    quantity_decimal: "1",
    unit: "forfait",
    amount_minor: "",
  });
  const api = useMemo(() => createApiClient(baseUrl, token), [baseUrl, token]);
  const pricingImport = usePricingImport(api, setMessage, reportId, selectedCaseId, loadDraft);
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

  async function refreshEnterpriseCompany() {
    if (!token.trim()) return;
    try {
      const company = await api.getEnterpriseCompany();
      setEnterpriseCompany(company);
      setEnterpriseCapabilities((await api.listEnterpriseCapabilities(company.company_id)).capabilities);
      if (!enterpriseCapabilityVersionForm.capability_id && company.company_id) {
        setEnterpriseCapabilityVersionForm((current) => ({ ...current, capability_id: "" }));
      }
    } catch {
      setEnterpriseCompany(null);
      setEnterpriseCapabilities([]);
    }
  }

  async function createEnterpriseCompany() {
    if (!enterpriseCompanyForm.legal_name.trim()) {
      setMessage({ tone: "error", text: "Renseignez au minimum la raison sociale de l’entreprise." });
      return;
    }
    try {
      await api.createEnterpriseCompany({
        ...enterpriseCompanyForm,
        trade_name: enterpriseCompanyForm.trade_name || undefined,
      });
      await refreshEnterpriseCompany();
      setMessage({ tone: "success", text: "Fiche entreprise créée dans le périmètre patronal." });
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Impossible de créer la fiche entreprise." });
    }
  }

  async function createEnterpriseCapability() {
    if (!enterpriseCompany || !enterpriseCapabilityForm.name.trim() || !enterpriseCapabilityForm.summary.trim()) {
      setMessage({ tone: "error", text: "Renseignez le nom et le résumé de la capacité." });
      return;
    }
    try {
      await api.createEnterpriseCapability(enterpriseCompany.company_id, {
        ...enterpriseCapabilityForm,
        name: enterpriseCapabilityForm.name.trim(),
        summary: enterpriseCapabilityForm.summary.trim(),
      });
      setEnterpriseCapabilityForm({ ...enterpriseCapabilityForm, name: "", summary: "" });
      await refreshEnterpriseCompany();
      setMessage({ tone: "success", text: "Capacité entreprise créée et journalisée." });
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Impossible de créer la capacité." });
    }
  }

  async function addEnterpriseCapabilityVersion() {
    const capability = enterpriseCapabilities.find(
      (item) => item.capability_id === enterpriseCapabilityVersionForm.capability_id,
    );
    if (
      !capability ||
      !enterpriseCapabilityVersionForm.title.trim() ||
      !enterpriseCapabilityVersionForm.description.trim() ||
      !enterpriseCapabilityVersionForm.valid_from ||
      !enterpriseCapabilityVersionForm.usage_scope.trim()
    ) {
      setMessage({ tone: "error", text: "Sélectionnez une capacité et renseignez sa version." });
      return;
    }
    try {
      await api.addEnterpriseCapabilityVersion(capability.capability_id, {
        expected_revision: capability.aggregate_revision,
        title: enterpriseCapabilityVersionForm.title.trim(),
        description: enterpriseCapabilityVersionForm.description.trim(),
        valid_from: new Date(`${enterpriseCapabilityVersionForm.valid_from}T00:00:00Z`).toISOString(),
        valid_until: enterpriseCapabilityVersionForm.valid_until
          ? new Date(`${enterpriseCapabilityVersionForm.valid_until}T23:59:59Z`).toISOString()
          : undefined,
        usage_scope: enterpriseCapabilityVersionForm.usage_scope.trim(),
        proof_document_ids: enterpriseCompany?.documents
          .filter((document) => document.verification_status === "VALIDATED")
          .map((document) => document.document_id),
      });
      setEnterpriseCapabilityVersionForm({ ...enterpriseCapabilityVersionForm, title: "", description: "", valid_from: "", valid_until: "", usage_scope: "" });
      await refreshEnterpriseCompany();
      setMessage({ tone: "success", text: "Version de capacité ajoutée avec ses preuves validées." });
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Impossible d’ajouter la version." });
    }
  }

  async function uploadEnterpriseDocument() {
    if (
      !enterpriseCompany ||
      !enterpriseFile ||
      !enterpriseDocumentForm.document_label.trim() ||
      !enterpriseDocumentForm.expires_at
    ) {
      setMessage({ tone: "error", text: "Renseignez le document, son libellé et sa date d’expiration." });
      return;
    }
    setEnterpriseUploading(true);
    try {
      const prepared = await api.prepareEnterpriseDocumentUpload(enterpriseCompany.company_id, {
        document_kind: enterpriseDocumentForm.document_kind,
        document_label: enterpriseDocumentForm.document_label.trim(),
        original_filename: enterpriseFile.name,
        expected_byte_size: enterpriseFile.size,
        expires_at: new Date(`${enterpriseDocumentForm.expires_at}T23:59:59Z`).toISOString(),
      });
      const uploadReference = prepared.aggregate_refs.find(
        (reference) => reference.aggregate_type === "EnterpriseDocumentUpload",
      );
      if (!uploadReference?.aggregate_id) throw new Error("Le serveur n’a pas retourné l’upload opaque.");
      await api.uploadEnterpriseDocumentContent(enterpriseCompany.company_id, uploadReference.aggregate_id, enterpriseFile);
      setEnterpriseFile(null);
      setEnterpriseDocumentForm({ ...enterpriseDocumentForm, document_label: "" });
      setMessage({ tone: "success", text: "Document contrôlé, enregistré et prêt pour vérification humaine." });
      await refreshEnterpriseCompany();
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "L’upload entreprise a échoué." });
    } finally {
      setEnterpriseUploading(false);
    }
  }

  async function verifyEnterpriseDocument() {
    const document = enterpriseCompany?.documents.find(
      (item) => item.document_id === enterpriseVerificationDocumentId,
    );
    if (!enterpriseCompany || !document) {
      setMessage({ tone: "error", text: "Sélectionnez une pièce à vérifier." });
      return;
    }
    const reason = enterpriseVerificationOutcome === "VALIDATED"
      ? "DOCUMENT_ACCEPTED"
      : enterpriseVerificationReason === "DOCUMENT_ACCEPTED"
        ? "DOCUMENT_ILLEGIBLE"
        : enterpriseVerificationReason;
    try {
      await api.verifyEnterpriseDocument(enterpriseCompany.company_id, document.document_id, {
        expected_verification_revision: document.verification_revision,
        outcome: enterpriseVerificationOutcome,
        reason_code: reason,
      });
      setMessage({
        tone: "success",
        text: enterpriseVerificationOutcome === "VALIDATED"
          ? "Pièce validée humainement et journalisée."
          : "Pièce rejetée humainement et journalisée.",
      });
      setEnterpriseVerificationDocumentId("");
      await refreshEnterpriseCompany();
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "La vérification de la pièce a échoué." });
    }
  }

  async function refreshAssignments() {
    try {
      const result = await api.listPatronAssignments();
      setAssignments(result.items);
      const first = result.items[0];
      if (first && !selectedAssignmentId) {
        setSelectedAssignmentId(first.assignment_id);
        await loadAssignmentDetails(first.assignment_id);
      }
    } catch (error) {
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Impossible de charger le cockpit patron.",
      });
    }
  }

  async function loadAssignmentDetails(assignmentId: string) {
    try {
      const [journalResult, interactionsResult] = await Promise.all([
        api.getAssignmentJournal(assignmentId),
        api.getAssignmentInteractions(assignmentId),
      ]);
      setJournal(journalResult.items);
      setInteractions(interactionsResult);
    } catch (error) {
      setJournal([]);
      setInteractions(null);
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Impossible de charger le journal patron.",
      });
    }
  }

  async function selectAssignment(assignment: PatronAssignment) {
    setSelectedAssignmentId(assignment.assignment_id);
    setSelectedCaseId(assignment.case_id);
    await Promise.all([loadAssignmentDetails(assignment.assignment_id), refreshScenarios(assignment.case_id)]);
  }

  async function loadCollaboratorWizard() {
    if (!wizardPackageId.trim() || !wizardCaseId.trim()) {
      setMessage({ tone: "error", text: "Renseignez l’affaire et le package de préparation collaborateur." });
      return;
    }
    try {
      const [packageResult, taskResult] = await Promise.all([
        api.getCollaboratorPreparation(wizardPackageId.trim()),
        api.listCollaboratorTasks(wizardCaseId.trim()),
      ]);
      setWizardPackage(packageResult);
      setWizardTasks(taskResult.tasks);
      if (!wizardTaskId && taskResult.tasks[0]) setWizardTaskId(taskResult.tasks[0].task_id);
      setMessage({ tone: "success", text: "Wizard collaborateur chargé depuis les projections serveur." });
    } catch (error) {
      setWizardPackage(null);
      setWizardTasks([]);
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Impossible de charger le wizard collaborateur." });
    }
  }

  async function refreshCollaboratorWizard() {
    if (wizardPackageId.trim() && wizardCaseId.trim()) await loadCollaboratorWizard();
  }

  async function evaluateWizardReadiness() {
    if (!wizardPackage) return;
    try {
      await api.evaluatePreparationReadiness(wizardPackage.case_id, {
        package_id: wizardPackage.package_id,
        assignment_id: wizardPackage.assignment_id,
        dce_version_id: wizardPackage.dce_version_id,
        expected_revision: wizardPackage.aggregate_revision,
      });
      setMessage({ tone: "success", text: "Complétude recalculée. Les blocages restent opposables au serveur." });
      await refreshCollaboratorWizard();
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "La vérification de complétude a échoué." });
    }
  }

  async function generateWizardDocument() {
    if (!wizardPackage?.latest_readiness) return;
    try {
      await api.generateTechnicalDocument(wizardPackage.package_id, {
        expected_revision: wizardPackage.aggregate_revision,
        readiness_revision: wizardPackage.latest_readiness.revision,
      });
      setMessage({ tone: "success", text: "Génération documentaire demandée avec contrôle de complétude." });
      await refreshCollaboratorWizard();
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "La génération documentaire a échoué." });
    }
  }

  async function claimWizardTask() {
    const task = wizardTasks.find((item) => item.task_id === wizardTaskId);
    if (!task) return;
    try {
      await api.claimCollaboratorTask(task.task_id, task.aggregate_revision);
      setMessage({ tone: "success", text: "Tâche prise en charge." });
      await refreshCollaboratorWizard();
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "La prise en charge a échoué." });
    }
  }

  async function recordWizardTaskResult() {
    const task = wizardTasks.find((item) => item.task_id === wizardTaskId);
    if (!task || !wizardResultText.trim()) return;
    try {
      await api.recordCollaboratorTaskResult(task.task_id, {
        expected_revision: task.aggregate_revision,
        result_text: wizardResultText.trim(),
        outcome: wizardOutcome,
      });
      setWizardResultText("");
      setMessage({ tone: "success", text: "Résultat structuré enregistré." });
      await refreshCollaboratorWizard();
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Le résultat n’a pas été enregistré." });
    }
  }

  async function completeWizardTask() {
    const task = wizardTasks.find((item) => item.task_id === wizardTaskId);
    if (!task) return;
    try {
      await api.completeCollaboratorTask(task.task_id, task.aggregate_revision);
      setMessage({ tone: "success", text: "Tâche clôturée avec révision optimiste." });
      await refreshCollaboratorWizard();
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "La clôture de la tâche a échoué." });
    }
  }

  async function transmitWizardSnapshot() {
    if (!wizardPackage || !wizardSnapshotId.trim() || !wizardTransmissionId.trim()) return;
    try {
      await api.transmitPreparationSnapshot(wizardPackage.package_id, {
        snapshot_id: wizardSnapshotId.trim(),
        transmission_id: wizardTransmissionId.trim(),
        expected_package_revision: wizardPackage.aggregate_revision,
      });
      setMessage({ tone: "success", text: "Snapshot transmis au patron. Aucun dépôt externe n’est effectué par cette action." });
      await refreshCollaboratorWizard();
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "La transmission du snapshot a échoué." });
    }
  }



  async function createDraft() {
    if (!selectedCaseId) {
      setMessage({ tone: "error", text: "Sélectionnez une affaire avant de créer un brouillon." });
      return;
    }
    setLoadingDraft(true);
    setMessage(null);
    try {
      const receipt = await api.createDraft(selectedCaseId);
      const newReportId = receipt.aggregate_refs[0]?.aggregate_id;
      if (!newReportId) throw new Error("Le serveur n’a pas retourné l’identifiant du brouillon.");
      setReportId(newReportId);
      const loadedDraft = await api.getDraft(selectedCaseId, newReportId);
      setDraft(loadedDraft);
      pricingImport.setPricingImportReportRevision(String(loadedDraft.aggregate_revision));
      setMessage({ tone: "success", text: receipt.replayed ? "Brouillon existant rechargé." : "Nouveau brouillon créé." });
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Impossible de créer le brouillon." });
    } finally {
      setLoadingDraft(false);
    }
  }

  async function loadDraft() {
    if (!selectedCaseId || !reportId.trim()) {
      setMessage({ tone: "error", text: "Sélectionnez une affaire et renseignez l’identifiant du brouillon." });
      return;
    }
    setLoadingDraft(true);
    setMessage(null);
    try {
      const loadedDraft = await api.getDraft(selectedCaseId, reportId.trim());
      setDraft(loadedDraft);
      pricingImport.setPricingImportReportRevision(String(loadedDraft.aggregate_revision));
      setMessage({ tone: "success", text: "Brouillon chargé en lecture seule contrôlée." });
    } catch (error) {
      setDraft(null);
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Impossible de charger le brouillon." });
    } finally {
      setLoadingDraft(false);
    }
  }

  async function submitLine(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft || !selectedCaseId) return;
    const amount = Number(lineForm.amount_minor);
    if (!Number.isInteger(amount)) {
      setMessage({ tone: "error", text: "Le montant doit être exprimé en centimes entiers." });
      return;
    }
    try {
      const receipt = await api.addLine(selectedCaseId, draft.report_id, {
        ...lineForm,
        amount_minor: amount,
        expected_revision: draft.aggregate_revision,
      });
      setMessage({ tone: "success", text: receipt.replayed ? "Ajout rejoué sans doublon." : "Ligne ajoutée au brouillon." });
      setLineForm({ ...lineForm, label: "", amount_minor: "" });
      await loadDraft();
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "L’ajout de la ligne a échoué." });
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

        <section className="section-block wizard-section" id="collaborator-wizard-section">
          <div className="section-heading"><div><span className="section-kicker">PARCOURS COLLABORATEUR</span><h2>Wizard de préparation</h2></div><span className="count-pill">{wizardPackage?.state ?? "À charger"}</span></div>
          <div className="wizard-toolbar"><label><span>Identifiant de l’affaire</span><input value={wizardCaseId} onChange={(event) => setWizardCaseId(event.target.value)} placeholder="UUID de l’affaire" /></label><label><span>Identifiant du package</span><input value={wizardPackageId} onChange={(event) => setWizardPackageId(event.target.value)} placeholder="UUID de préparation" /></label><button className="primary-button" type="button" onClick={() => void loadCollaboratorWizard()}>Charger le wizard <span>→</span></button></div>
          {!wizardPackage ? <div className="empty-card"><strong>Le wizard est prêt à être chargé</strong><p>Les projections de préparation et les tâches sont lues dans le périmètre collaborateur autorisé. Aucune donnée financière n’est exposée ici.</p></div> : <div className="wizard-body">
            <div className="wizard-steps"><div className="wizard-step complete"><span>1</span><strong>Tâches</strong><small>{wizardTasks.filter((task) => task.state === "COMPLETED").length}/{wizardTasks.length} terminées</small></div><div className={`wizard-step ${wizardPackage.latest_readiness ? "complete" : ""}`}><span>2</span><strong>Complétude</strong><small>{wizardPackage.latest_readiness?.state ?? "À vérifier"}</small></div><div className={`wizard-step ${wizardPackage.generated_documents.length ? "complete" : ""}`}><span>3</span><strong>Document</strong><small>{wizardPackage.generated_documents.length ? "Généré" : "À générer"}</small></div><div className="wizard-step"><span>4</span><strong>Transmission</strong><small>Contrôle patron</small></div></div>
            <div className="wizard-grid"><div className="detail-panel"><div className="panel-heading"><div><h3>Tâches de l’affaire</h3><p>Chaque résultat est structuré, révisé et traçable.</p></div><span className="rule-tag">{wizardTasks.length} tâche{wizardTasks.length > 1 ? "s" : ""}</span></div>{wizardTasks.length === 0 ? <p className="panel-empty">Aucune tâche projetée.</p> : <div className="wizard-task-list">{wizardTasks.map((task) => <button type="button" className={`wizard-task ${task.task_id === wizardTaskId ? "selected" : ""}`} key={task.task_id} onClick={() => setWizardTaskId(task.task_id)}><div><strong>{task.title}</strong><small>{task.task_kind} · {task.priority} · Révision {task.aggregate_revision}</small></div><span className={`state-badge state-${task.state.toLowerCase()}`}>{task.state}</span></button>)}</div>}{wizardTaskId && <div className="wizard-task-actions"><button className="secondary-button" type="button" onClick={() => void claimWizardTask()}>Prendre en charge</button><label><span>Résultat</span><textarea rows={2} value={wizardResultText} onChange={(event) => setWizardResultText(event.target.value)} placeholder="Constat ou preuve structurée, sans donnée financière" /></label><label><span>Issue</span><select value={wizardOutcome} onChange={(event) => setWizardOutcome(event.target.value as "RECORDED" | "NOT_APPLICABLE" | "UNABLE_TO_COMPLETE")}><option value="RECORDED">Enregistré</option><option value="NOT_APPLICABLE">Non applicable</option><option value="UNABLE_TO_COMPLETE">Impossible à compléter</option></select></label><div className="wizard-action-row"><button className="primary-button" type="button" onClick={() => void recordWizardTaskResult()}>Enregistrer le résultat</button><button className="secondary-button" type="button" onClick={() => void completeWizardTask()}>Clôturer</button></div></div>}</div>
              <div className="detail-panel"><div className="panel-heading"><div><h3>Complétude et production</h3><p>La readiness est recalculée côté serveur avant toute génération.</p></div></div><div className="wizard-action-row"><button className="primary-button" type="button" onClick={() => void evaluateWizardReadiness()}>Vérifier la complétude</button><button className="secondary-button" type="button" disabled={!wizardPackage.latest_readiness} onClick={() => void generateWizardDocument()}>Générer la réponse technique</button></div>{wizardPackage.latest_readiness ? <div className="readiness-card"><div className="case-top"><strong>{wizardPackage.latest_readiness.state}</strong><span>Révision {wizardPackage.latest_readiness.revision}</span></div><p>{wizardPackage.latest_readiness.checked_task_count} tâche(s) et {wizardPackage.latest_readiness.checked_requirement_count} exigence(s) contrôlée(s).</p>{wizardPackage.latest_readiness.blocker_codes.length > 0 && <div className="code-list"><strong>Blocages</strong>{wizardPackage.latest_readiness.blocker_codes.map((code) => <span key={code}>{code}</span>)}</div>}{wizardPackage.latest_readiness.warning_codes.length > 0 && <div className="code-list warning"><strong>Avertissements</strong>{wizardPackage.latest_readiness.warning_codes.map((code) => <span key={code}>{code}</span>)}</div>}</div> : <p className="panel-empty">La complétude n’a pas encore été vérifiée.</p>}{wizardPackage.generated_documents.length > 0 && <div className="document-list">{wizardPackage.generated_documents.map((document) => <div className="document-row" key={document.document_id}><strong>{document.document_kind}</strong><span>v{document.version} · {document.state}</span></div>)}</div>}</div>
              <div className="detail-panel wizard-transmission"><div className="panel-heading"><div><h3>Transmettre au patron</h3><p>Cette transmission ne dépose jamais le dossier sur un portail externe.</p></div></div><label><span>Snapshot préparé</span><input value={wizardSnapshotId} onChange={(event) => setWizardSnapshotId(event.target.value)} placeholder="UUID du snapshot" /></label><label><span>Identifiant de transmission</span><input value={wizardTransmissionId} onChange={(event) => setWizardTransmissionId(event.target.value)} placeholder="UUID de transmission" /></label><button className="primary-button" type="button" onClick={() => void transmitWizardSnapshot()}>Transmettre au patron <span>→</span></button><small className="invariant-note">Sortie : contexte non financier, blocages et preuves structurées uniquement.</small></div>
            </div>
          </div>}
        </section>

        <section className="section-block cockpit-section">
          <div className="section-heading"><div><span className="section-kicker">PILOTAGE OPÉRATIONNEL</span><h2>Affectations et signaux</h2></div><span className="count-pill">{assignments.length} affectation{assignments.length > 1 ? "s" : ""}</span></div>
          {assignments.length === 0 ? <div className="empty-card"><strong>Aucune affectation patronale visible</strong><p>La projection est tenant-scopée et ne montre que les affectations autorisées par le serveur.</p></div> : <div className="assignment-grid">{assignments.map((assignment) => <button key={assignment.assignment_id} className={`assignment-card ${assignment.assignment_id === selectedAssignmentId ? "selected" : ""}`} onClick={() => void selectAssignment(assignment)}><div className="case-top"><span className={`state-badge state-${assignment.state.toLowerCase()}`}>{assignment.state}</span><span className="case-arrow">↗</span></div><h3>{assignment.case_title}</h3><p>{assignment.case_id}</p><div className="assignment-footer"><span>Révision {assignment.aggregate_revision}</span><span>{assignment.scope_actions.length} action{assignment.scope_actions.length > 1 ? "s" : ""}</span></div></button>)}</div>}
          {selectedAssignmentId && <div className="assignment-detail-grid"><div className="detail-panel"><div className="panel-heading"><div><h3>Journal de l’affectation</h3><p>Historique append-only projeté par le serveur.</p></div><span className="rule-tag">{journal.length} événement{journal.length > 1 ? "s" : ""}</span></div>{journal.length === 0 ? <p className="panel-empty">Aucun événement journalisé.</p> : <div className="timeline">{journal.slice(0, 6).map((entry) => <div className="timeline-row" key={entry.record_id}><span className="timeline-dot" /><div><strong>{entry.event_type}</strong><small>{entry.resulting_state} · Révision {entry.resulting_revision}</small></div></div>)}</div>}</div><div className="detail-panel"><div className="panel-heading"><div><h3>Interactions récentes</h3><p>Signaux collaborateur structurés, sans texte sensible.</p></div><span className="rule-tag">{interactions?.items.length ?? 0} signal{(interactions?.items.length ?? 0) > 1 ? "s" : ""}</span></div>{!interactions?.items.length ? <p className="panel-empty">Aucune interaction enregistrée.</p> : <div className="interaction-list">{interactions.items.slice(0, 6).map((item) => <div className="interaction-row" key={item.record_id}><span className={`interaction-kind kind-${item.operational_state.toLowerCase()}`}>{item.operational_state}</span><div><strong>{item.kind}</strong><small>{item.priority ?? item.reason_kind ?? item.clarification_kind ?? "Signal opérationnel"}</small></div></div>)}</div>}</div></div>}
        </section>

        <section className="section-block decision-section" id="decision-section">
          <div className="section-heading"><div><span className="section-kicker">DOSSIER DE DÉCISION</span><h2>Décider sur des faits contrôlés</h2></div><span className="count-pill">{decisionDossier?.validity ?? "À charger"}</span></div>
          {!decisionDossier ? <div className="empty-card"><strong>Aucun dossier de décision disponible</strong><p>Sélectionnez une affaire et actualisez pour projeter le contexte, les inconnus, les risques et les conditions autorisées.</p></div> : <div className="decision-grid">
            <div className="detail-panel decision-summary"><div className="panel-heading"><div><h3>{decisionDossier.decision_type}</h3><p>Affaire {decisionDossier.case_id}</p></div><span className="state-badge state-active">{decisionDossier.outcome}</span></div><div className="decision-facts"><span><small>Cycle</small><strong>{decisionDossier.lifecycle}</strong></span><span><small>Contexte</small><strong>{decisionDossier.context_status}</strong></span><span><small>Validité</small><strong>{decisionDossier.validity}</strong></span></div>{decisionDossier.final_justification && <blockquote>{decisionDossier.final_justification}</blockquote>}</div>
            <div className="detail-panel"><div className="panel-heading"><div><h3>Points de vigilance</h3><p>Les éléments restent issus du read model serveur.</p></div></div><div className="decision-list"><div><strong>Inconnus</strong><span>{decisionDossier.unknowns.length}</span></div><div><strong>Risques</strong><span>{decisionDossier.risks.length}</span></div><div><strong>Conditions</strong><span>{decisionDossier.conditions.length}</span></div></div><div className="decision-json">{[...decisionDossier.unknowns.slice(0, 3), ...decisionDossier.risks.slice(0, 3)].map((item, index) => <pre key={index}>{JSON.stringify(item, null, 2)}</pre>)}</div></div>
            <div className="detail-panel"><div className="panel-heading"><div><h3>Conditions de décision</h3><p>Contrôles à satisfaire avant clôture.</p></div></div>{decisionDossier.conditions.length === 0 ? <p className="panel-empty">Aucune condition structurée.</p> : <div className="condition-list">{decisionDossier.conditions.map((condition) => <div className="condition-row" key={condition.condition_id}><span className={`state-badge state-${condition.status.toLowerCase()}`}>{condition.status}</span><div><strong>{condition.label}</strong><small>{condition.failure_consequence}{condition.due_at ? ` · Échéance ${formatDate(condition.due_at)}` : ""}</small></div></div>)}</div>}</div>
            <div className="detail-panel"><div className="panel-heading"><div><h3>Sources de preuve</h3><p>Références projetées et révisées.</p></div></div>{decisionDossier.sources.length === 0 ? <p className="panel-empty">Aucune source référencée.</p> : <div className="source-list">{decisionDossier.sources.map((source) => <div className="source-row" key={`${source.aggregate_type}-${source.aggregate_id}`}><strong>{source.aggregate_type}</strong><span>{source.role} · Révision {source.aggregate_revision}</span></div>)}</div>}</div>
          </div>}
        </section>

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

        <section className="section-block draft-section" id="draft-section"><div className="section-heading"><div><span className="section-kicker">CHIFFRAGE PRIVÉ</span><h2>Brouillon financier</h2></div>{draft && <span className="draft-status"><span className="status-dot" />DRAFT · Révision {draft.aggregate_revision}</span>}</div><div className="draft-toolbar"><label><span>Affaire sélectionnée</span><select value={selectedCaseId} onChange={(event) => setSelectedCaseId(event.target.value)}><option value="">Choisir une affaire</option>{cases.map((item) => <option key={item.case_id} value={item.case_id}>{item.work_label}</option>)}</select></label><label className="report-input"><span>Identifiant du brouillon</span><input value={reportId} onChange={(event) => setReportId(event.target.value)} placeholder="UUID du snapshot DRAFT" /></label><div className="draft-actions"><button className="secondary-button" onClick={() => void createDraft()} disabled={loadingDraft}>+ Nouveau brouillon</button><button className="primary-button load-button" onClick={() => void loadDraft()} disabled={loadingDraft}>{loadingDraft ? "Chargement…" : "Lire le brouillon"}<span>→</span></button></div></div>
          {draft ? <><div className="summary-grid">{summaryCards.map((card) => <div className={`summary-card ${card.accent}`} key={card.label}><span>{card.label}</span><strong>{card.value}</strong><small>{card.label === "Marge brute" ? `${(draft.summary.gross_margin_rate_bps / 100).toFixed(1)} % du chiffre d’affaires` : `Révision ${draft.aggregate_revision}`}</small></div>)}</div><div className="draft-panel"><div className="panel-heading"><div><h3>Lignes du brouillon</h3><p>Les montants restent visibles uniquement dans cet espace patron.</p></div><span className="rule-tag">Règleset v{draft.ruleset_version}</span></div><div className="line-table-wrap"><table><thead><tr><th>Catégorie</th><th>Libellé</th><th>Quantité</th><th>Unité</th><th className="amount-column">Montant</th></tr></thead><tbody>{draft.lines.length === 0 ? <tr><td colSpan={5} className="table-empty">Aucune ligne. Ajoutez le premier poste du chiffrage.</td></tr> : draft.lines.map((line) => <tr key={line.line_id}><td><span className="category-badge">{categoryLabel(line.category)}</span></td><td><strong>{line.label}</strong></td><td>{line.quantity_decimal}</td><td>{line.unit}</td><td className="amount-column">{formatMoney(line.amount_minor, line.currency_code)}</td></tr>)}</tbody></table></div><form className="add-line-form" onSubmit={submitLine}><div className="form-title"><span className="plus-mark">+</span><div><strong>Ajouter une ligne</strong><small>La révision courante sera appliquée automatiquement.</small></div></div><label><span>Catégorie</span><select value={lineForm.category} onChange={(event) => setLineForm({ ...lineForm, category: event.target.value as FinancialCategory })}>{CATEGORIES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label><label><span>Libellé</span><input required value={lineForm.label} onChange={(event) => setLineForm({ ...lineForm, label: event.target.value })} placeholder="Ex. étude technique" /></label><label><span>Quantité</span><input required value={lineForm.quantity_decimal} onChange={(event) => setLineForm({ ...lineForm, quantity_decimal: event.target.value })} /></label><label><span>Unité</span><input required value={lineForm.unit} onChange={(event) => setLineForm({ ...lineForm, unit: event.target.value })} /></label><label><span>Montant (centimes)</span><input required type="number" step="1" value={lineForm.amount_minor} onChange={(event) => setLineForm({ ...lineForm, amount_minor: event.target.value })} placeholder="125000" /></label><button className="primary-button add-button" type="submit">Ajouter <span>→</span></button></form><div className="last-updated">Dernière lecture serveur : {formatDate(draft.calculated_at)} · Aucun cache local du montant</div></div></> : <div className="empty-draft"><div className="empty-icon">◫</div><div><strong>Sélectionnez un brouillon pour commencer.</strong><p>La lecture est tenant-scopée et ne montre que les snapshots DRAFT autorisés par le serveur.</p></div></div>}
        </section>

        <footer className="footer"><span>SMART_AO V8</span><span>Architecture sécurisée · Tenant-scoped · Auditée</span><span>API {baseUrl}</span></footer>
      </main>

      {showConnection && <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) setShowConnection(false); }}><form className="connection-modal" onSubmit={saveConnection}><div className="modal-top"><div><span className="section-kicker">CONFIGURATION</span><h2>Connexion au backend</h2></div><button type="button" className="close-button" onClick={() => setShowConnection(false)}>×</button></div><p>Le token est conservé uniquement dans le stockage local de ce navigateur. Il n’est jamais envoyé ailleurs que vers l’URL configurée.</p><label><span>URL API</span><input required value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} /></label><label><span>Bearer token</span><textarea required rows={4} value={token} onChange={(event) => setToken(event.target.value)} placeholder="eyJhbGciOiJIUzI1NiIs…" /></label><button className="primary-button" type="submit">Enregistrer et charger <span>→</span></button></form></div>}
    </div>
  );
}

export default App;
