import type { Dispatch, SetStateAction } from "react";

import type {
  EnterpriseCapability,
  EnterpriseCompany,
  EnterpriseDocumentKind,
} from "../../shared/types";
import type {
  EnterpriseCapabilityForm,
  EnterpriseCapabilityVersionForm,
  EnterpriseCompanyForm,
  EnterpriseDocumentForm,
  EnterpriseVerificationOutcome,
  EnterpriseVerificationReason,
} from "./useEnterpriseLibrary";

type EnterpriseLibraryPanelProps = {
  enterpriseCompany: EnterpriseCompany | null;
  enterpriseCapabilities: EnterpriseCapability[];
  enterpriseCapabilityForm: EnterpriseCapabilityForm;
  enterpriseCapabilityVersionForm: EnterpriseCapabilityVersionForm;
  enterpriseCompanyForm: EnterpriseCompanyForm;
  enterpriseDocumentForm: EnterpriseDocumentForm;
  enterpriseFile: File | null;
  enterpriseUploading: boolean;
  enterpriseVerificationDocumentId: string;
  enterpriseVerificationOutcome: EnterpriseVerificationOutcome;
  enterpriseVerificationReason: EnterpriseVerificationReason;
  setEnterpriseCapabilityForm: Dispatch<SetStateAction<EnterpriseCapabilityForm>>;
  setEnterpriseCapabilityVersionForm: Dispatch<SetStateAction<EnterpriseCapabilityVersionForm>>;
  setEnterpriseCompanyForm: Dispatch<SetStateAction<EnterpriseCompanyForm>>;
  setEnterpriseDocumentForm: Dispatch<SetStateAction<EnterpriseDocumentForm>>;
  setEnterpriseFile: Dispatch<SetStateAction<File | null>>;
  setEnterpriseVerificationDocumentId: Dispatch<SetStateAction<string>>;
  setEnterpriseVerificationOutcome: Dispatch<SetStateAction<EnterpriseVerificationOutcome>>;
  setEnterpriseVerificationReason: Dispatch<SetStateAction<EnterpriseVerificationReason>>;
  formatDate: (value: string) => string;
  onCreateCompany: () => void;
  onCreateCapability: () => void;
  onAddCapabilityVersion: () => void;
  onUploadDocument: () => void;
  onVerifyDocument: () => void;
};

export function EnterpriseLibraryPanel({
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
  formatDate,
  onCreateCompany,
  onCreateCapability,
  onAddCapabilityVersion,
  onUploadDocument,
  onVerifyDocument,
}: EnterpriseLibraryPanelProps) {
  return (
    <section className="section-block" id="library-section">
      <div className="section-heading">
        <div>
          <span className="section-kicker">BIBLIOTHÈQUE PATRONALE</span>
          <h2>Entreprise & prix privés</h2>
        </div>
        <span className="count-pill">
          {enterpriseCompany?.documents.length ?? 0} pièce
          {(enterpriseCompany?.documents.length ?? 0) > 1 ? "s" : ""}
        </span>
      </div>
      {!enterpriseCompany ? (
        <div className="detail-panel enterprise-company-panel">
          <div className="panel-heading">
            <div>
              <h3>Créer la fiche entreprise</h3>
              <p>La société légale est tenant-scopée et reste accessible au patron uniquement.</p>
            </div>
            <span className="rule-tag">PATRON</span>
          </div>
          <div className="enterprise-form-grid">
            <label>
              <span>Raison sociale</span>
              <input
                required
                value={enterpriseCompanyForm.legal_name}
                onChange={(event) =>
                  setEnterpriseCompanyForm({ ...enterpriseCompanyForm, legal_name: event.target.value })
                }
                placeholder="Entreprise BTP"
              />
            </label>
            <label>
              <span>Nom commercial</span>
              <input
                value={enterpriseCompanyForm.trade_name}
                onChange={(event) =>
                  setEnterpriseCompanyForm({ ...enterpriseCompanyForm, trade_name: event.target.value })
                }
                placeholder="Optionnel"
              />
            </label>
            <label>
              <span>SIREN</span>
              <input
                required
                pattern="[0-9]{9}"
                value={enterpriseCompanyForm.siren}
                onChange={(event) =>
                  setEnterpriseCompanyForm({ ...enterpriseCompanyForm, siren: event.target.value })
                }
                placeholder="9 chiffres"
              />
            </label>
            <label>
              <span>SIRET</span>
              <input
                required
                pattern="[0-9]{14}"
                value={enterpriseCompanyForm.siret}
                onChange={(event) =>
                  setEnterpriseCompanyForm({ ...enterpriseCompanyForm, siret: event.target.value })
                }
                placeholder="14 chiffres"
              />
            </label>
            <label>
              <span>TVA intracommunautaire</span>
              <input
                required
                value={enterpriseCompanyForm.vat_number}
                onChange={(event) =>
                  setEnterpriseCompanyForm({
                    ...enterpriseCompanyForm,
                    vat_number: event.target.value.toUpperCase(),
                  })
                }
                placeholder="FR..."
              />
            </label>
            <label>
              <span>Adresse</span>
              <input
                required
                value={enterpriseCompanyForm.address_line1}
                onChange={(event) =>
                  setEnterpriseCompanyForm({ ...enterpriseCompanyForm, address_line1: event.target.value })
                }
              />
            </label>
            <label>
              <span>Code postal</span>
              <input
                required
                value={enterpriseCompanyForm.postal_code}
                onChange={(event) =>
                  setEnterpriseCompanyForm({ ...enterpriseCompanyForm, postal_code: event.target.value })
                }
              />
            </label>
            <label>
              <span>Ville</span>
              <input
                required
                value={enterpriseCompanyForm.city}
                onChange={(event) =>
                  setEnterpriseCompanyForm({ ...enterpriseCompanyForm, city: event.target.value })
                }
              />
            </label>
            <label>
              <span>Pays</span>
              <input
                required
                pattern="[A-Z]{2}"
                maxLength={2}
                value={enterpriseCompanyForm.country_code}
                onChange={(event) =>
                  setEnterpriseCompanyForm({
                    ...enterpriseCompanyForm,
                    country_code: event.target.value.toUpperCase(),
                  })
                }
              />
            </label>
          </div>
          <button className="primary-button" type="button" onClick={onCreateCompany}>
            Créer la fiche entreprise <span>→</span>
          </button>
        </div>
      ) : (
        <div className="enterprise-library-grid">
          <div className="detail-panel enterprise-company-panel">
            <div className="panel-heading">
              <div>
                <h3>{enterpriseCompany.legal_name}</h3>
                <p>{enterpriseCompany.trade_name ?? "Fiche légale patronale"}</p>
              </div>
              <span className="state-badge state-active">
                RÉVISION {enterpriseCompany.aggregate_revision}
              </span>
            </div>
            <div className="enterprise-facts">
              <span><small>SIREN</small><strong>{enterpriseCompany.siren}</strong></span>
              <span><small>SIRET</small><strong>{enterpriseCompany.siret}</strong></span>
              <span><small>TVA</small><strong>{enterpriseCompany.vat_number}</strong></span>
              <span>
                <small>Adresse</small>
                <strong>
                  {enterpriseCompany.address_line1}, {enterpriseCompany.postal_code}{" "}
                  {enterpriseCompany.city}
                </strong>
              </span>
            </div>
          </div>
          <div className="detail-panel enterprise-company-panel">
            <div className="panel-heading">
              <div>
                <h3>Pièces de l’entreprise</h3>
                <p>Documents versionnés, statuts de vérification et dates de validité.</p>
              </div>
              <span className="rule-tag">
                {enterpriseCompany.documents.length} pièce
                {enterpriseCompany.documents.length > 1 ? "s" : ""}
              </span>
            </div>
            {enterpriseCompany.documents.length === 0 ? (
              <p className="panel-empty">
                Aucune pièce enregistrée. Le parcours d’upload privé reste piloté par les routes
                sécurisées.
              </p>
            ) : (
              <div className="enterprise-document-list">
                {enterpriseCompany.documents.map((document) => (
                  <div className="enterprise-document-row" key={document.document_id}>
                    <div>
                      <strong>{document.document_kind} · {document.document_label}</strong>
                      <small>
                        Émis le {formatDate(document.issued_at)}
                        {document.expires_at ? ` · Expire le ${formatDate(document.expires_at)}` : ""}
                      </small>
                    </div>
                    <span className={`state-badge state-${document.verification_status.toLowerCase()}`}>
                      {document.verification_status}
                    </span>
                    <button
                      className="secondary-button document-review-button"
                      type="button"
                      onClick={() => setEnterpriseVerificationDocumentId(document.document_id)}
                    >
                      Vérifier
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
      {enterpriseCompany && (
        <>
          <div className="detail-panel enterprise-capability-panel">
            <div className="panel-heading">
              <div>
                <h3>Passeport capacités & références</h3>
                <p>Qualifications, références, équipes et moyens restent dans le périmètre patronal.</p>
              </div>
              <span className="rule-tag">
                {enterpriseCapabilities.length} capacité
                {enterpriseCapabilities.length > 1 ? "s" : ""}
              </span>
            </div>
            <div className="enterprise-capability-grid">
              <label>
                <span>Type</span>
                <select
                  value={enterpriseCapabilityForm.capability_kind}
                  onChange={(event) =>
                    setEnterpriseCapabilityForm({
                      ...enterpriseCapabilityForm,
                      capability_kind: event.target.value as EnterpriseCapabilityForm["capability_kind"],
                    })
                  }
                >
                  <option value="QUALIFICATION">Qualification</option>
                  <option value="REFERENCE">Référence</option>
                  <option value="EQUIPMENT">Équipement</option>
                  <option value="TEAM">Équipe</option>
                  <option value="METHOD">Méthode</option>
                </select>
              </label>
              <label>
                <span>Nom</span>
                <input
                  value={enterpriseCapabilityForm.name}
                  onChange={(event) =>
                    setEnterpriseCapabilityForm({ ...enterpriseCapabilityForm, name: event.target.value })
                  }
                  placeholder="Certification travaux publics"
                />
              </label>
              <label>
                <span>Résumé</span>
                <input
                  value={enterpriseCapabilityForm.summary}
                  onChange={(event) =>
                    setEnterpriseCapabilityForm({ ...enterpriseCapabilityForm, summary: event.target.value })
                  }
                  placeholder="Qualification et périmètre"
                />
              </label>
              <button className="primary-button" type="button" onClick={onCreateCapability}>
                Créer la capacité <span>→</span>
              </button>
            </div>
            {enterpriseCapabilities.length > 0 && (
              <div className="enterprise-capability-list">
                {enterpriseCapabilities.map((capability) => (
                  <div className="enterprise-capability-row" key={capability.capability_id}>
                    <div>
                      <strong>{capability.capability_kind} · {capability.name}</strong>
                      <small>
                        {capability.summary} · Révision {capability.aggregate_revision} ·{" "}
                        {capability.versions.length} version{capability.versions.length > 1 ? "s" : ""}
                      </small>
                    </div>
                    <span className={`state-badge state-${capability.state.toLowerCase()}`}>
                      {capability.state}
                    </span>
                  </div>
                ))}
              </div>
            )}
            <div className="enterprise-version-grid">
              <label>
                <span>Capacité à versionner</span>
                <select
                  value={enterpriseCapabilityVersionForm.capability_id}
                  onChange={(event) => {
                    const capability = enterpriseCapabilities.find(
                      (item) => item.capability_id === event.target.value,
                    );
                    setEnterpriseCapabilityVersionForm({
                      ...enterpriseCapabilityVersionForm,
                      capability_id: event.target.value,
                      expected_revision: String(capability?.aggregate_revision ?? 0),
                    });
                  }}
                >
                  <option value="">Sélectionner</option>
                  {enterpriseCapabilities.map((capability) => (
                    <option key={capability.capability_id} value={capability.capability_id}>
                      {capability.name} · v{capability.aggregate_revision}
                    </option>
                  ))}
                </select>
              </label>
              <label><span>Titre de version</span><input value={enterpriseCapabilityVersionForm.title} onChange={(event) => setEnterpriseCapabilityVersionForm({ ...enterpriseCapabilityVersionForm, title: event.target.value })} placeholder="Référence chantier 2026" /></label>
              <label><span>Valide à partir du</span><input type="date" value={enterpriseCapabilityVersionForm.valid_from} onChange={(event) => setEnterpriseCapabilityVersionForm({ ...enterpriseCapabilityVersionForm, valid_from: event.target.value })} /></label>
              <label><span>Valide jusqu’au</span><input type="date" value={enterpriseCapabilityVersionForm.valid_until} onChange={(event) => setEnterpriseCapabilityVersionForm({ ...enterpriseCapabilityVersionForm, valid_until: event.target.value })} /></label>
              <label><span>Périmètre d’usage</span><input value={enterpriseCapabilityVersionForm.usage_scope} onChange={(event) => setEnterpriseCapabilityVersionForm({ ...enterpriseCapabilityVersionForm, usage_scope: event.target.value })} placeholder="Dossier de candidature BTP" /></label>
              <label><span>Description</span><textarea rows={2} value={enterpriseCapabilityVersionForm.description} onChange={(event) => setEnterpriseCapabilityVersionForm({ ...enterpriseCapabilityVersionForm, description: event.target.value })} placeholder="Preuve, contexte et limites d’usage" /></label>
              <button className="secondary-button" type="button" onClick={onAddCapabilityVersion}>Ajouter la version</button>
            </div>
            <small className="invariant-note">
              Seules les pièces au statut <strong>VALIDATED</strong> sont automatiquement proposées comme preuves.
            </small>
          </div>
          {enterpriseVerificationDocumentId && (
            <div className="detail-panel enterprise-verification-panel">
              <div className="panel-heading">
                <div>
                  <h3>Vérifier une pièce</h3>
                  <p>La décision humaine est append-only et porte sur la révision serveur affichée.</p>
                </div>
                <span className="rule-tag">
                  RÉVISION {enterpriseCompany.documents.find((document) => document.document_id === enterpriseVerificationDocumentId)?.verification_revision ?? 0}
                </span>
              </div>
              <div className="enterprise-verification-grid">
                <label>
                  <span>Décision</span>
                  <select
                    value={enterpriseVerificationOutcome}
                    onChange={(event) => {
                      const outcome = event.target.value as EnterpriseVerificationOutcome;
                      setEnterpriseVerificationOutcome(outcome);
                      setEnterpriseVerificationReason(
                        outcome === "VALIDATED" ? "DOCUMENT_ACCEPTED" : "DOCUMENT_ILLEGIBLE",
                      );
                    }}
                  >
                    <option value="VALIDATED">Valider</option>
                    <option value="REJECTED">Rejeter</option>
                  </select>
                </label>
                <label>
                  <span>Motif</span>
                  <select
                    value={enterpriseVerificationReason}
                    disabled={enterpriseVerificationOutcome === "VALIDATED"}
                    onChange={(event) =>
                      setEnterpriseVerificationReason(event.target.value as EnterpriseVerificationReason)
                    }
                  >
                    <option value="DOCUMENT_ACCEPTED">Document accepté</option>
                    <option value="DOCUMENT_ILLEGIBLE">Document illisible</option>
                    <option value="DOCUMENT_EXPIRED">Document expiré</option>
                    <option value="DOCUMENT_MISMATCH">Document incohérent</option>
                    <option value="DOCUMENT_DUPLICATE">Document dupliqué</option>
                  </select>
                </label>
                <button className="primary-button" type="button" onClick={onVerifyDocument}>
                  Enregistrer la décision <span>→</span>
                </button>
              </div>
            </div>
          )}
          <div className="detail-panel enterprise-upload-panel">
            <div className="panel-heading">
              <div>
                <h3>Ajouter une pièce</h3>
                <p>Le binaire est envoyé uniquement vers la quarantaine privée ; le serveur calcule hash, MIME et verdict ClamAV.</p>
              </div>
              <span className="secure-pill"><span className="status-dot" />CONFIDENTIEL</span>
            </div>
            <div className="enterprise-upload-grid">
              <label>
                <span>Type de pièce</span>
                <select
                  value={enterpriseDocumentForm.document_kind}
                  onChange={(event) =>
                    setEnterpriseDocumentForm({
                      ...enterpriseDocumentForm,
                      document_kind: event.target.value as EnterpriseDocumentKind,
                    })
                  }
                >
                  <option value="KBIS">Kbis</option>
                  <option value="INSURANCE">Assurance</option>
                  <option value="RIB">RIB</option>
                </select>
              </label>
              <label><span>Libellé</span><input required value={enterpriseDocumentForm.document_label} onChange={(event) => setEnterpriseDocumentForm({ ...enterpriseDocumentForm, document_label: event.target.value })} placeholder="Kbis 2026" /></label>
              <label><span>Expiration</span><input required type="date" value={enterpriseDocumentForm.expires_at} onChange={(event) => setEnterpriseDocumentForm({ ...enterpriseDocumentForm, expires_at: event.target.value })} /></label>
              <label><span>Fichier</span><input required type="file" accept=".pdf,.docx,.xlsx,.txt" onChange={(event) => setEnterpriseFile(event.target.files?.[0] ?? null)} /></label>
            </div>
            <button className="primary-button" type="button" onClick={onUploadDocument} disabled={enterpriseUploading || !enterpriseFile}>
              {enterpriseUploading ? "Contrôle en cours…" : "Téléverser et enregistrer"}<span>→</span>
            </button>
            <small className="invariant-note">Après CLEAN, le document est créé en statut <strong>PENDING</strong> ; la vérification humaine reste une action séparée.</small>
          </div>
        </>
      )}
    </section>
  );
}
