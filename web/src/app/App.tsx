import { useEffect, useMemo, useState } from "react";
import { createApiClient } from "../infrastructure/api";
import type {
  AssignedCase,
  DraftReport,
  FinancialCategory,
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
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const [reportId, setReportId] = useState("");
  const [draft, setDraft] = useState<DraftReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingDraft, setLoadingDraft] = useState(false);
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [showConnection, setShowConnection] = useState(false);
  const [lineForm, setLineForm] = useState({
    category: "SALES" as FinancialCategory,
    label: "",
    quantity_decimal: "1",
    unit: "forfait",
    amount_minor: "",
  });

  const api = useMemo(() => createApiClient(baseUrl, token), [baseUrl, token]);
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
  }, []);

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
      setDraft(await api.getDraft(selectedCaseId, newReportId));
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
      setDraft(await api.getDraft(selectedCaseId, reportId.trim()));
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
          <button className="nav-item active"><span className="nav-icon">▦</span>Vue d’ensemble</button>
          <button className="nav-item"><span className="nav-icon">◇</span>Mes affaires</button>
          <button className="nav-item"><span className="nav-icon">◌</span>Actions à traiter</button>
          <button className="nav-item"><span className="nav-icon">▤</span>Bibliothèque</button>
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

        <section className="hero-grid">
          <div className="hero-card"><div className="hero-copy"><span className="hero-kicker">CETTE SEMAINE</span><h2>Décider avec la<br /><strong>bonne information.</strong></h2><p>Retrouvez vos affaires actives et reprenez chaque chiffrage là où vous l’avez laissé.</p><button className="primary-button" onClick={() => document.getElementById("draft-section")?.scrollIntoView({ behavior: "smooth" })}>Ouvrir un chiffrage <span>→</span></button></div><div className="hero-orbit"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="orbit-core">AO<br /><small>V8</small></div></div></div>
          <div className="metric-stack"><div className="small-metric"><span className="metric-label">AFFAIRES ACTIVES</span><strong>{cases.length.toString().padStart(2, "0")}</strong><span className="metric-meta">dans votre périmètre</span></div><div className="small-metric"><span className="metric-label">ÉTAT DE LA CONNEXION</span><strong className={token.trim() ? "text-green" : "text-amber"}>{token.trim() ? "Prête" : "À configurer"}</strong><span className="metric-meta">{baseUrl}</span></div></div>
        </section>

        <section className="section-block"><div className="section-heading"><div><span className="section-kicker">PORTEFEUILLE</span><h2>Mes affaires</h2></div><span className="count-pill">{cases.length} visible{cases.length > 1 ? "s" : ""}</span></div><div className="case-grid">{cases.length === 0 ? <div className="empty-card"><strong>Aucune affaire chargée</strong><p>Configurez votre Bearer token puis actualisez pour charger les affaires auxquelles vous avez accès.</p><button className="secondary-button" onClick={() => setShowConnection(true)}>Configurer la connexion</button></div> : cases.map((item) => <button key={item.case_id} className={`case-card ${item.case_id === selectedCaseId ? "selected" : ""}`} onClick={() => setSelectedCaseId(item.case_id)}><div className="case-top"><span className="case-status">{item.dce_availability}</span><span className="case-arrow">↗</span></div><h3>{item.work_label}</h3><p>{item.case_id}</p><div className="case-footer"><span>{item.commercial_stage}</span><span>{item.case_lifecycle}</span></div></button>)}</div></section>

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
