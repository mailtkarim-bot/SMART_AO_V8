import type { Dispatch, SetStateAction } from "react";
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ApiClient } from "../../infrastructure/api";
import type {
  EnterpriseCapability,
  EnterpriseCompany,
  EnterpriseReceipt,
} from "../../shared/types";
import { useEnterpriseLibrary } from "./useEnterpriseLibrary";

type HookMessage = { tone: "success" | "error" | "warning"; text: string };
type EnterpriseApi = Pick<
  ApiClient,
  | "getEnterpriseCompany"
  | "listEnterpriseCapabilities"
  | "createEnterpriseCompany"
  | "createEnterpriseCapability"
  | "addEnterpriseCapabilityVersion"
  | "prepareEnterpriseDocumentUpload"
  | "uploadEnterpriseDocumentContent"
  | "verifyEnterpriseDocument"
>;

const receipt = (aggregateType: string, aggregateId: string): EnterpriseReceipt => ({
  status: "SUCCEEDED",
  command_id: "command-enterprise-1",
  idempotency_key: "idempotency-enterprise-1",
  result_code: "ENTERPRISE_UPDATED",
  aggregate_refs: [
    {
      aggregate_type: aggregateType,
      aggregate_id: aggregateId,
      aggregate_revision: 2,
    },
  ],
  event_ids: ["event-enterprise-1"],
  replayed: false,
});

const company = (): EnterpriseCompany => ({
  company_id: "company-1",
  aggregate_revision: 4,
  legal_name: "Bâtir Durable",
  trade_name: "Bâtir Durable Construction",
  siren: "123456789",
  siret: "12345678900011",
  vat_number: "FR12123456789",
  address_line1: "1 rue du chantier",
  postal_code: "75001",
  city: "Paris",
  country_code: "FR",
  documents: [
    {
      document_id: "document-validated",
      document_kind: "KBIS",
      document_label: "Kbis validé",
      issued_at: "2026-01-01T00:00:00Z",
      expires_at: "2027-01-01T00:00:00Z",
      verification_status: "VALIDATED",
      verification_revision: 3,
    },
    {
      document_id: "document-pending",
      document_kind: "RIB",
      document_label: "RIB en attente",
      issued_at: "2026-01-01T00:00:00Z",
      expires_at: null,
      verification_status: "PENDING",
      verification_revision: 1,
    },
  ],
});

const capability = (): EnterpriseCapability => ({
  capability_id: "capability-1",
  company_id: "company-1",
  aggregate_revision: 5,
  capability_kind: "QUALIFICATION",
  name: "Travaux publics",
  summary: "Qualification VRD",
  state: "ACTIVE",
  versions: [],
});

function renderEnterpriseHook(
  api: EnterpriseApi,
  setMessage: Dispatch<SetStateAction<HookMessage | null>>,
) {
  return renderHook(() => useEnterpriseLibrary(api as ApiClient, setMessage));
}

describe("useEnterpriseLibrary", () => {
  it("rejects capability creation without a company or complete fields", async () => {
    const api = {
      getEnterpriseCompany: vi.fn(),
      listEnterpriseCapabilities: vi.fn(),
      createEnterpriseCompany: vi.fn(),
      createEnterpriseCapability: vi.fn(),
      addEnterpriseCapabilityVersion: vi.fn(),
      prepareEnterpriseDocumentUpload: vi.fn(),
      uploadEnterpriseDocumentContent: vi.fn(),
      verifyEnterpriseDocument: vi.fn(),
    } satisfies EnterpriseApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderEnterpriseHook(api, setMessage);

    await act(async () => {
      await result.current.createEnterpriseCapability();
    });

    expect(api.createEnterpriseCapability).not.toHaveBeenCalled();
    expect(setMessage).toHaveBeenCalledWith({
      tone: "error",
      text: "Renseignez le nom et le résumé de la capacité.",
    });
  });

  it("creates the company with optional trade name normalized and reloads the library", async () => {
    const api = {
      getEnterpriseCompany: vi.fn().mockResolvedValue(company()),
      listEnterpriseCapabilities: vi.fn().mockResolvedValue({ capabilities: [] }),
      createEnterpriseCompany: vi.fn().mockResolvedValue(receipt("EnterpriseCompany", "company-1")),
      createEnterpriseCapability: vi.fn(),
      addEnterpriseCapabilityVersion: vi.fn(),
      prepareEnterpriseDocumentUpload: vi.fn(),
      uploadEnterpriseDocumentContent: vi.fn(),
      verifyEnterpriseDocument: vi.fn(),
    } satisfies EnterpriseApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderEnterpriseHook(api, setMessage);

    act(() => {
      result.current.setEnterpriseCompanyForm((current) => ({
        ...current,
        legal_name: "  Bâtir Durable  ",
        trade_name: "",
        siren: "123456789",
        siret: "12345678900011",
        vat_number: "FR12123456789",
        address_line1: "1 rue du chantier",
        postal_code: "75001",
        city: "Paris",
      }));
    });
    await act(async () => {
      await result.current.createEnterpriseCompany();
    });

    expect(api.createEnterpriseCompany).toHaveBeenCalledWith({
      legal_name: "  Bâtir Durable  ",
      trade_name: undefined,
      siren: "123456789",
      siret: "12345678900011",
      vat_number: "FR12123456789",
      address_line1: "1 rue du chantier",
      postal_code: "75001",
      city: "Paris",
      country_code: "FR",
    });
    expect(result.current.enterpriseCompany?.company_id).toBe("company-1");
    expect(setMessage).toHaveBeenLastCalledWith({
      tone: "success",
      text: "Fiche entreprise créée dans le périmètre patronal.",
    });
  });

  it("versions a capability using only validated documents as proofs", async () => {
    const api = {
      getEnterpriseCompany: vi.fn().mockResolvedValue(company()),
      listEnterpriseCapabilities: vi.fn().mockResolvedValue({ capabilities: [capability()] }),
      createEnterpriseCompany: vi.fn(),
      createEnterpriseCapability: vi.fn(),
      addEnterpriseCapabilityVersion: vi.fn().mockResolvedValue(receipt("EnterpriseCapability", "capability-1")),
      prepareEnterpriseDocumentUpload: vi.fn(),
      uploadEnterpriseDocumentContent: vi.fn(),
      verifyEnterpriseDocument: vi.fn(),
    } satisfies EnterpriseApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderEnterpriseHook(api, setMessage);

    await act(async () => {
      await result.current.refreshEnterpriseCompany();
    });
    act(() => {
      result.current.setEnterpriseCapabilityVersionForm((current) => ({
        ...current,
        capability_id: "capability-1",
        title: "Référence VRD 2026",
        description: "Référence vérifiée",
        valid_from: "2026-02-01",
        valid_until: "2026-12-31",
        usage_scope: "Dossier de candidature",
      }));
    });
    await act(async () => {
      await result.current.addEnterpriseCapabilityVersion();
    });

    expect(api.addEnterpriseCapabilityVersion).toHaveBeenCalledWith("capability-1", {
      expected_revision: 5,
      title: "Référence VRD 2026",
      description: "Référence vérifiée",
      valid_from: "2026-02-01T00:00:00.000Z",
      valid_until: "2026-12-31T23:59:59.000Z",
      usage_scope: "Dossier de candidature",
      proof_document_ids: ["document-validated"],
    });
  });

  it("prepares an opaque upload, sends the file, then reloads the company", async () => {
    const file = new File(["kbis"], "kbis.pdf", { type: "application/pdf" });
    const api = {
      getEnterpriseCompany: vi.fn().mockResolvedValue(company()),
      listEnterpriseCapabilities: vi.fn().mockResolvedValue({ capabilities: [] }),
      createEnterpriseCompany: vi.fn(),
      createEnterpriseCapability: vi.fn(),
      addEnterpriseCapabilityVersion: vi.fn(),
      prepareEnterpriseDocumentUpload: vi.fn().mockResolvedValue(
        receipt("EnterpriseDocumentUpload", "upload-1"),
      ),
      uploadEnterpriseDocumentContent: vi.fn().mockResolvedValue({ upload_id: "upload-1", state: "CLEAN" }),
      verifyEnterpriseDocument: vi.fn(),
    } satisfies EnterpriseApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderEnterpriseHook(api, setMessage);

    await act(async () => {
      await result.current.refreshEnterpriseCompany();
    });
    act(() => {
      result.current.setEnterpriseFile(file);
      result.current.setEnterpriseDocumentForm((current) => ({
        ...current,
        document_label: "Kbis 2026",
        expires_at: "2027-01-01",
      }));
    });
    await act(async () => {
      await result.current.uploadEnterpriseDocument();
    });

    expect(api.prepareEnterpriseDocumentUpload).toHaveBeenCalledWith("company-1", {
      document_kind: "KBIS",
      document_label: "Kbis 2026",
      original_filename: "kbis.pdf",
      expected_byte_size: file.size,
      expires_at: "2027-01-01T23:59:59.000Z",
    });
    expect(api.uploadEnterpriseDocumentContent).toHaveBeenCalledWith("company-1", "upload-1", file);
    expect(result.current.enterpriseFile).toBeNull();
    expect(result.current.enterpriseUploading).toBe(false);
  });

  it("maps a rejected human verification to a non-accepted reason code", async () => {
    const api = {
      getEnterpriseCompany: vi.fn().mockResolvedValue(company()),
      listEnterpriseCapabilities: vi.fn().mockResolvedValue({ capabilities: [] }),
      createEnterpriseCompany: vi.fn(),
      createEnterpriseCapability: vi.fn(),
      addEnterpriseCapabilityVersion: vi.fn(),
      prepareEnterpriseDocumentUpload: vi.fn(),
      uploadEnterpriseDocumentContent: vi.fn(),
      verifyEnterpriseDocument: vi.fn().mockResolvedValue(receipt("EnterpriseDocumentVerification", "document-pending")),
    } satisfies EnterpriseApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderEnterpriseHook(api, setMessage);

    await act(async () => {
      await result.current.refreshEnterpriseCompany();
    });
    act(() => {
      result.current.setEnterpriseVerificationDocumentId("document-pending");
      result.current.setEnterpriseVerificationOutcome("REJECTED");
      result.current.setEnterpriseVerificationReason("DOCUMENT_EXPIRED");
    });
    await act(async () => {
      await result.current.verifyEnterpriseDocument();
    });

    expect(api.verifyEnterpriseDocument).toHaveBeenCalledWith("company-1", "document-pending", {
      expected_verification_revision: 1,
      outcome: "REJECTED",
      reason_code: "DOCUMENT_EXPIRED",
    });
    expect(setMessage).toHaveBeenLastCalledWith({
      tone: "success",
      text: "Pièce rejetée humainement et journalisée.",
    });
  });
});
