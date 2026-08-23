import type { Dispatch, SetStateAction } from "react";
import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "../../infrastructure/api";
import type {
  SubmissionEvidenceReceipt,
  SubmissionPackageReceipt,
  SubmissionSignatureProjection,
  SubmissionSignatureReceipt,
} from "../../shared/types";
import { useSubmissionActions } from "./useSubmissionActions";

type HookMessage = { tone: "success" | "error" | "warning"; text: string };
type SubmissionApi = Pick<
  ApiClient,
  "prepareSubmissionPackage" | "downloadSubmissionPackage" | "recordSubmissionEvidence"
>;
type SignatureApi = SubmissionApi &
  Pick<ApiClient, "requestSubmissionSignature" | "getSubmissionSignature">;

const packageReceipt = (replayed = false): SubmissionPackageReceipt => ({
  status: "SUCCEEDED",
  command_id: "command-submission-1",
  idempotency_key: "idempotency-submission-1",
  result_code: "SUBMISSION_PACKAGE_PREPARED",
  aggregate_refs: [
    {
      aggregate_type: "SubmissionPackage",
      aggregate_id: "submission-package-1",
      aggregate_revision: 1,
    },
  ],
  event_ids: ["event-submission-1"],
  replayed,
});

const signatureReceipt = (): SubmissionSignatureReceipt => ({
  status: "SUCCEEDED",
  command_id: "command-signature-1",
  idempotency_key: "idempotency-signature-1",
  result_code: "SUBMISSION_SIGNATURE_REQUESTED",
  aggregate_refs: [
    {
      aggregate_type: "SubmissionSignature",
      aggregate_id: "signature-1",
      aggregate_revision: 1,
    },
  ],
  event_ids: ["event-signature-1"],
  replayed: false,
  external_submission: "NOT_PERFORMED",
});

const signatureProjection = (): SubmissionSignatureProjection => ({
  signature_id: "signature-1",
  submission_package_id: "submission-package-1",
  case_id: "case-1",
  provider: "TEST_PROVIDER",
  status: "SIGNED",
  expected_package_version: 2,
  revision: 2,
  external_submission: "NOT_PERFORMED",
});

const evidenceReceipt = (): SubmissionEvidenceReceipt => ({
  status: "SUCCEEDED",
  command_id: "command-evidence-1",
  idempotency_key: "idempotency-evidence-1",
  result_code: "SUBMISSION_EVIDENCE_RECORDED",
  aggregate_refs: [
    {
      aggregate_type: "SubmissionPackage",
      aggregate_id: "submission-package-1",
      aggregate_revision: 2,
    },
  ],
  event_ids: ["event-evidence-1"],
  replayed: false,
  external_submission: "NOT_PERFORMED",
});

function renderSubmissionHook(
  api: SubmissionApi,
  setMessage: Dispatch<SetStateAction<HookMessage | null>>,
) {
  return renderHook(() => useSubmissionActions(api as ApiClient, setMessage));
}

describe("useSubmissionActions", () => {
  it("rejects preparation without a preparation package identifier", async () => {
    const api = {
      prepareSubmissionPackage: vi.fn(),
      downloadSubmissionPackage: vi.fn(),
      recordSubmissionEvidence: vi.fn(),
    } satisfies SubmissionApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderSubmissionHook(api, setMessage);

    await act(async () => {
      await result.current.prepareSubmissionPackage();
    });

    expect(api.prepareSubmissionPackage).not.toHaveBeenCalled();
    expect(setMessage).toHaveBeenCalledWith({
      tone: "error",
      text: "Renseignez l’identifiant de la préparation à déposer.",
    });
  });

  it("prepares the submission package and stores the returned aggregate identifier", async () => {
    const api = {
      prepareSubmissionPackage: vi.fn().mockResolvedValue(packageReceipt()),
      downloadSubmissionPackage: vi.fn(),
      recordSubmissionEvidence: vi.fn(),
    } satisfies SubmissionApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderSubmissionHook(api, setMessage);

    act(() => {
      result.current.setPreparationPackageId(" preparation-1 ");
      result.current.setPreparationRevision("3");
    });
    await act(async () => {
      await result.current.prepareSubmissionPackage();
    });

    expect(api.prepareSubmissionPackage).toHaveBeenCalledWith("preparation-1", 3);
    expect(result.current.submissionPackageId).toBe("submission-package-1");
    expect(setMessage).toHaveBeenCalledWith({
      tone: "success",
      text: "Paquet préparé pour contrôle patronal. Aucun dépôt externe n’a été effectué.",
    });
  });

  it("downloads a Blob as an audited ZIP export and marks the package exported", async () => {
    const archive = new Blob(["zip-content"], { type: "application/zip" });
    const objectUrl = "blob:submission-package-1";
    const createObjectURL = vi.fn().mockReturnValue(objectUrl);
    const revokeObjectURL = vi.fn();
    const click = vi.fn();
    const originalCreateElement = document.createElement.bind(document);
    const api = {
      prepareSubmissionPackage: vi.fn(),
      downloadSubmissionPackage: vi.fn().mockResolvedValue(archive),
      recordSubmissionEvidence: vi.fn(),
    } satisfies SubmissionApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;

    vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL });
    vi.spyOn(document, "createElement").mockImplementation((tagName, options) => {
      if (tagName === "a") {
        return { href: "", download: "", click } as unknown as HTMLAnchorElement;
      }
      return originalCreateElement(tagName, options);
    });

    const { result } = renderSubmissionHook(api, setMessage);
    act(() => {
      result.current.setSubmissionPackageId(" submission-package-1 ");
    });
    await act(async () => {
      await result.current.exportSubmissionPackage();
    });

    expect(api.downloadSubmissionPackage).toHaveBeenCalledWith("submission-package-1");
    expect(createObjectURL).toHaveBeenCalledWith(archive);
    expect(click).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith(objectUrl);
    expect(result.current.submissionExported).toBe(true);
    expect(setMessage).toHaveBeenCalledWith({
      tone: "success",
      text: "Dossier exporté. L’audit et la notification de téléchargement ont été enregistrés.",
    });

    vi.restoreAllMocks();
  });

  it("requests a signature with the explicit package version", async () => {
    const api = {
      prepareSubmissionPackage: vi.fn(),
      downloadSubmissionPackage: vi.fn(),
      recordSubmissionEvidence: vi.fn(),
      requestSubmissionSignature: vi.fn().mockResolvedValue(signatureReceipt()),
      getSubmissionSignature: vi.fn(),
    } satisfies SignatureApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderSubmissionHook(api, setMessage);

    act(() => {
      result.current.setSubmissionPackageId(" submission-package-1 ");
      result.current.setSignaturePackageVersion("2");
    });
    await act(async () => {
      await result.current.requestSignature();
    });

    expect(api.requestSubmissionSignature).toHaveBeenCalledWith("submission-package-1", 2);
    expect(result.current.signatureId).toBe("signature-1");
    expect(result.current.signatureStatus).toBe("REQUESTED");
    expect(result.current.signatureRevision).toBe(1);
    expect(setMessage).toHaveBeenCalledWith({
      tone: "success",
      text: "Demande de signature enregistrée. Aucun dépôt externe n’a été effectué.",
    });
  });

  it("loads only the bounded signature projection", async () => {
    const api = {
      prepareSubmissionPackage: vi.fn(),
      downloadSubmissionPackage: vi.fn(),
      recordSubmissionEvidence: vi.fn(),
      requestSubmissionSignature: vi.fn(),
      getSubmissionSignature: vi.fn().mockResolvedValue(signatureProjection()),
    } satisfies SignatureApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderSubmissionHook(api, setMessage);

    act(() => {
      result.current.setSignatureId("signature-1");
    });
    await act(async () => {
      await result.current.loadSignature();
    });

    expect(api.getSubmissionSignature).toHaveBeenCalledWith("signature-1");
    expect(result.current.signatureStatus).toBe("SIGNED");
    expect(result.current.signatureProvider).toBe("TEST_PROVIDER");
    expect(result.current.signatureRevision).toBe(2);
    expect(result.current.signaturePackageVersion).toBe("2");
  });

  it("records redacted manual evidence without changing the external submission invariant", async () => {
    const api = {
      prepareSubmissionPackage: vi.fn(),
      downloadSubmissionPackage: vi.fn(),
      recordSubmissionEvidence: vi.fn().mockResolvedValue(evidenceReceipt()),
    } satisfies SubmissionApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderSubmissionHook(api, setMessage);

    act(() => {
      result.current.setSubmissionPackageId("submission-package-1");
      result.current.setEvidenceForm({
        evidence_type: "MANUAL_PORTAL_REFERENCE",
        external_reference_hash: "a".repeat(64),
        evidence_sha256: "b".repeat(64),
        notes_redacted: "  preuve expurgée  ",
      });
    });
    await act(async () => {
      await result.current.recordSubmissionEvidence();
    });

    expect(api.recordSubmissionEvidence).toHaveBeenCalledWith("submission-package-1", {
      evidence_type: "MANUAL_PORTAL_REFERENCE",
      external_reference_hash: "a".repeat(64),
      evidence_sha256: "b".repeat(64),
      notes_redacted: "  preuve expurgée  ",
    });
    expect(setMessage).toHaveBeenCalledWith({
      tone: "success",
      text: "Preuve append-only enregistrée. Le dépôt externe reste à effectuer manuellement.",
    });
  });
});


afterEach(() => {
  vi.restoreAllMocks();
});
