import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { EnterpriseCapability, EnterpriseCompany } from "../../shared/types";
import { EnterpriseLibraryPanel } from "./EnterpriseLibraryPanel";

const company: EnterpriseCompany = {
  company_id: "company-1",
  aggregate_revision: 4,
  legal_name: "Bâtir Durable SAS",
  trade_name: "Bâtir Durable",
  siren: "123456789",
  siret: "12345678900010",
  vat_number: "FR12123456789",
  address_line1: "1 rue des Travaux",
  postal_code: "75001",
  city: "Paris",
  country_code: "FR",
  documents: [
    {
      document_id: "document-1",
      document_kind: "KBIS",
      document_label: "Kbis 2026",
      issued_at: "2026-01-01T00:00:00Z",
      expires_at: "2027-01-01T00:00:00Z",
      verification_status: "VALIDATED",
      verification_revision: 2,
    },
  ],
};

const capability: EnterpriseCapability = {
  capability_id: "capability-1",
  company_id: "company-1",
  aggregate_revision: 3,
  capability_kind: "QUALIFICATION",
  name: "Qualification travaux publics",
  summary: "Travaux de réhabilitation",
  state: "ACTIVE",
  versions: [],
};

function renderPanel(
  overrides: Partial<React.ComponentProps<typeof EnterpriseLibraryPanel>> = {},
) {
  const props: React.ComponentProps<typeof EnterpriseLibraryPanel> = {
    enterpriseCompany: null,
    enterpriseCapabilities: [],
    enterpriseCapabilityForm: { capability_kind: "QUALIFICATION", name: "", summary: "" },
    enterpriseCapabilityVersionForm: {
      capability_id: "",
      expected_revision: "0",
      title: "",
      description: "",
      valid_from: "",
      valid_until: "",
      usage_scope: "",
    },
    enterpriseCompanyForm: {
      legal_name: "",
      trade_name: "",
      siren: "",
      siret: "",
      vat_number: "",
      address_line1: "",
      postal_code: "",
      city: "",
      country_code: "FR",
    },
    enterpriseDocumentForm: { document_kind: "KBIS", document_label: "", expires_at: "" },
    enterpriseFile: null,
    enterpriseUploading: false,
    enterpriseVerificationDocumentId: "",
    enterpriseVerificationOutcome: "VALIDATED",
    enterpriseVerificationReason: "DOCUMENT_ACCEPTED",
    setEnterpriseCapabilityForm: vi.fn(),
    setEnterpriseCapabilityVersionForm: vi.fn(),
    setEnterpriseCompanyForm: vi.fn(),
    setEnterpriseDocumentForm: vi.fn(),
    setEnterpriseFile: vi.fn(),
    setEnterpriseVerificationDocumentId: vi.fn(),
    setEnterpriseVerificationOutcome: vi.fn(),
    setEnterpriseVerificationReason: vi.fn(),
    formatDate: () => "1 janvier 2026",
    onCreateCompany: vi.fn(),
    onCreateCapability: vi.fn(),
    onAddCapabilityVersion: vi.fn(),
    onUploadDocument: vi.fn(),
    onVerifyDocument: vi.fn(),
    ...overrides,
  };
  return render(<EnterpriseLibraryPanel {...props} />);
}

describe("EnterpriseLibraryPanel", () => {
  it("renders the patron-only company creation state", () => {
    const onCreateCompany = vi.fn();
    renderPanel({ onCreateCompany });

    expect(screen.getByRole("heading", { name: "Créer la fiche entreprise" })).toBeInTheDocument();
    expect(screen.getByText("PATRON")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Créer la fiche entreprise/ }));
    expect(onCreateCompany).toHaveBeenCalledTimes(1);
  });

  it("renders validated documents and capabilities without financial fields", () => {
    renderPanel({ enterpriseCompany: company, enterpriseCapabilities: [capability] });

    expect(screen.getByText("Bâtir Durable SAS")).toBeInTheDocument();
    expect(screen.getByText("KBIS · Kbis 2026")).toBeInTheDocument();
    expect(screen.getAllByText("VALIDATED")).toHaveLength(2);
    expect(screen.getByText("QUALIFICATION · Qualification travaux publics")).toBeInTheDocument();
    expect(screen.getByText(/Le binaire est envoyé uniquement vers la quarantaine privée/)).toBeInTheDocument();
    expect(screen.queryByText(/marge|prix de vente|coût direct/i)).not.toBeInTheDocument();
  });

  it("delegates human verification and keeps upload disabled until a file exists", () => {
    const onVerifyDocument = vi.fn();
    renderPanel({
      enterpriseCompany: company,
      enterpriseVerificationDocumentId: "document-1",
      onVerifyDocument,
    });

    fireEvent.click(screen.getByRole("button", { name: /Enregistrer la décision/ }));
    expect(onVerifyDocument).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: /Téléverser et enregistrer/ })).toBeDisabled();
    expect(screen.getByText(/vérification humaine reste une action séparée/)).toBeInTheDocument();
  });
});
