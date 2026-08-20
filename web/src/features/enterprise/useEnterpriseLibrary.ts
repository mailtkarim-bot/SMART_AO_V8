import { useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import type { ApiClient } from "../../infrastructure/api";
import type {
  EnterpriseCapability,
  EnterpriseCapabilityKind,
  EnterpriseCompany,
  EnterpriseDocumentKind,
} from "../../shared/types";

type Message = { tone: "success" | "error" | "warning"; text: string };
type SetMessage = Dispatch<SetStateAction<Message | null>>;

type EnterpriseCapabilityForm = {
  capability_kind: EnterpriseCapabilityKind;
  name: string;
  summary: string;
};

type EnterpriseCapabilityVersionForm = {
  capability_id: string;
  expected_revision: string;
  title: string;
  description: string;
  valid_from: string;
  valid_until: string;
  usage_scope: string;
};

type EnterpriseCompanyForm = {
  legal_name: string;
  trade_name: string;
  siren: string;
  siret: string;
  vat_number: string;
  address_line1: string;
  postal_code: string;
  city: string;
  country_code: string;
};

type EnterpriseDocumentForm = {
  document_kind: EnterpriseDocumentKind;
  document_label: string;
  expires_at: string;
};

type EnterpriseVerificationOutcome = "VALIDATED" | "REJECTED";
type EnterpriseVerificationReason =
  | "DOCUMENT_ACCEPTED"
  | "DOCUMENT_ILLEGIBLE"
  | "DOCUMENT_EXPIRED"
  | "DOCUMENT_MISMATCH"
  | "DOCUMENT_DUPLICATE";

export function useEnterpriseLibrary(api: ApiClient, setMessage: SetMessage) {
  const [enterpriseCompany, setEnterpriseCompany] = useState<EnterpriseCompany | null>(null);
  const [enterpriseCapabilities, setEnterpriseCapabilities] = useState<EnterpriseCapability[]>([]);
  const [enterpriseCapabilityForm, setEnterpriseCapabilityForm] = useState<EnterpriseCapabilityForm>({
    capability_kind: "QUALIFICATION",
    name: "",
    summary: "",
  });
  const [enterpriseCapabilityVersionForm, setEnterpriseCapabilityVersionForm] =
    useState<EnterpriseCapabilityVersionForm>({
      capability_id: "",
      expected_revision: "0",
      title: "",
      description: "",
      valid_from: "",
      valid_until: "",
      usage_scope: "",
    });
  const [enterpriseCompanyForm, setEnterpriseCompanyForm] = useState<EnterpriseCompanyForm>({
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
  const [enterpriseDocumentForm, setEnterpriseDocumentForm] = useState<EnterpriseDocumentForm>({
    document_kind: "KBIS",
    document_label: "",
    expires_at: "",
  });
  const [enterpriseFile, setEnterpriseFile] = useState<File | null>(null);
  const [enterpriseUploading, setEnterpriseUploading] = useState(false);
  const [enterpriseVerificationDocumentId, setEnterpriseVerificationDocumentId] = useState("");
  const [enterpriseVerificationOutcome, setEnterpriseVerificationOutcome] =
    useState<EnterpriseVerificationOutcome>("VALIDATED");
  const [enterpriseVerificationReason, setEnterpriseVerificationReason] =
    useState<EnterpriseVerificationReason>("DOCUMENT_ACCEPTED");

  async function refreshEnterpriseCompany() {
    try {
      const company = await api.getEnterpriseCompany();
      setEnterpriseCompany(company);
      setEnterpriseCapabilities((await api.listEnterpriseCapabilities(company.company_id)).capabilities);
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
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Impossible de créer la fiche entreprise.",
      });
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
      setEnterpriseCapabilityForm((current) => ({ ...current, name: "", summary: "" }));
      await refreshEnterpriseCompany();
      setMessage({ tone: "success", text: "Capacité entreprise créée et journalisée." });
    } catch (error) {
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Impossible de créer la capacité.",
      });
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
      setEnterpriseCapabilityVersionForm((current) => ({
        ...current,
        title: "",
        description: "",
        valid_from: "",
        valid_until: "",
        usage_scope: "",
      }));
      await refreshEnterpriseCompany();
      setMessage({ tone: "success", text: "Version de capacité ajoutée avec ses preuves validées." });
    } catch (error) {
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Impossible d’ajouter la version.",
      });
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
      setEnterpriseDocumentForm((current) => ({ ...current, document_label: "" }));
      setMessage({ tone: "success", text: "Document contrôlé, enregistré et prêt pour vérification humaine." });
      await refreshEnterpriseCompany();
    } catch (error) {
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "L’upload entreprise a échoué.",
      });
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
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "La vérification de la pièce a échoué.",
      });
    }
  }

  return {
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
  };
}
