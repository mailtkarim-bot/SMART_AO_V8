import type { Dispatch, SetStateAction } from "react";
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ApiClient } from "../../infrastructure/api";
import type { CollaboratorTask, PreparationPackage } from "../../shared/types";
import { useCollaboratorWizard } from "./useCollaboratorWizard";

type HookMessage = { tone: "success" | "error" | "warning"; text: string };
type WizardApi = Pick<
  ApiClient,
  | "getCollaboratorPreparation"
  | "listCollaboratorTasks"
  | "evaluatePreparationReadiness"
  | "generateTechnicalDocument"
  | "claimCollaboratorTask"
  | "recordCollaboratorTaskResult"
  | "completeCollaboratorTask"
  | "transmitPreparationSnapshot"
>;

const preparation = (): PreparationPackage => ({
  package_id: "package-1",
  case_id: "case-1",
  assignment_id: "assignment-1",
  dce_version_id: "dce-1",
  state: "IN_PREPARATION",
  aggregate_revision: 7,
  latest_readiness: {
    readiness_id: "readiness-1",
    revision: 3,
    state: "READY_WITH_WARNINGS",
    blocker_codes: [],
    warning_codes: ["OPTIONAL_REFERENCE_MISSING"],
    checked_requirement_count: 4,
    checked_task_count: 2,
  },
  generated_documents: [],
});

const task = (id = "task-1"): CollaboratorTask => ({
  task_id: id,
  case_id: "case-1",
  assignment_id: "assignment-1",
  requirement_id: "requirement-1",
  task_kind: "REQUIREMENT_RESPONSE",
  title: "Répondre à la clause technique",
  objective: "Produire une preuve structurée",
  priority: "HIGH",
  state: "OPEN",
  due_at: null,
  aggregate_revision: 4,
});

function renderWizardHook(
  api: WizardApi,
  setMessage: Dispatch<SetStateAction<HookMessage | null>>,
) {
  return renderHook(() => useCollaboratorWizard(api as ApiClient, setMessage));
}

describe("useCollaboratorWizard", () => {
  it("requires both the case and preparation package identifiers", async () => {
    const api = {
      getCollaboratorPreparation: vi.fn(),
      listCollaboratorTasks: vi.fn(),
      evaluatePreparationReadiness: vi.fn(),
      generateTechnicalDocument: vi.fn(),
      claimCollaboratorTask: vi.fn(),
      recordCollaboratorTaskResult: vi.fn(),
      completeCollaboratorTask: vi.fn(),
      transmitPreparationSnapshot: vi.fn(),
    } satisfies WizardApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderWizardHook(api, setMessage);

    await act(async () => {
      await result.current.loadCollaboratorWizard();
    });

    expect(api.getCollaboratorPreparation).not.toHaveBeenCalled();
    expect(api.listCollaboratorTasks).not.toHaveBeenCalled();
    expect(setMessage).toHaveBeenCalledWith({
      tone: "error",
      text: "Renseignez l’affaire et le package de préparation collaborateur.",
    });
  });

  it("loads the preparation projection and selects the first task", async () => {
    const api = {
      getCollaboratorPreparation: vi.fn().mockResolvedValue(preparation()),
      listCollaboratorTasks: vi.fn().mockResolvedValue({ case_id: "case-1", tasks: [task()] }),
      evaluatePreparationReadiness: vi.fn(),
      generateTechnicalDocument: vi.fn(),
      claimCollaboratorTask: vi.fn(),
      recordCollaboratorTaskResult: vi.fn(),
      completeCollaboratorTask: vi.fn(),
      transmitPreparationSnapshot: vi.fn(),
    } satisfies WizardApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderWizardHook(api, setMessage);

    act(() => {
      result.current.setWizardCaseId(" case-1 ");
      result.current.setWizardPackageId(" package-1 ");
    });
    await act(async () => {
      await result.current.loadCollaboratorWizard();
    });

    expect(api.getCollaboratorPreparation).toHaveBeenCalledWith("package-1");
    expect(api.listCollaboratorTasks).toHaveBeenCalledWith("case-1");
    expect(result.current.wizardPackage?.package_id).toBe("package-1");
    expect(result.current.wizardTaskId).toBe("task-1");
    expect(setMessage).toHaveBeenLastCalledWith({
      tone: "success",
      text: "Wizard collaborateur chargé depuis les projections serveur.",
    });
  });

  it("recalculates readiness with the package revision and refreshes the projection", async () => {
    const api = {
      getCollaboratorPreparation: vi.fn().mockResolvedValue(preparation()),
      listCollaboratorTasks: vi.fn().mockResolvedValue({ case_id: "case-1", tasks: [task()] }),
      evaluatePreparationReadiness: vi.fn().mockResolvedValue({}),
      generateTechnicalDocument: vi.fn(),
      claimCollaboratorTask: vi.fn(),
      recordCollaboratorTaskResult: vi.fn(),
      completeCollaboratorTask: vi.fn(),
      transmitPreparationSnapshot: vi.fn(),
    } satisfies WizardApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderWizardHook(api, setMessage);

    act(() => {
      result.current.setWizardCaseId("case-1");
      result.current.setWizardPackageId("package-1");
    });
    await act(async () => {
      await result.current.loadCollaboratorWizard();
    });
    await act(async () => {
      await result.current.evaluateWizardReadiness();
    });

    expect(api.evaluatePreparationReadiness).toHaveBeenCalledWith("case-1", {
      package_id: "package-1",
      assignment_id: "assignment-1",
      dce_version_id: "dce-1",
      expected_revision: 7,
    });
    expect(api.getCollaboratorPreparation).toHaveBeenCalledTimes(2);
    expect(setMessage).toHaveBeenLastCalledWith({
      tone: "success",
      text: "Complétude recalculée. Les blocages restent opposables au serveur.",
    });
  });

  it("records a trimmed structured result using the optimistic task revision", async () => {
    const api = {
      getCollaboratorPreparation: vi.fn().mockResolvedValue(preparation()),
      listCollaboratorTasks: vi.fn().mockResolvedValue({ case_id: "case-1", tasks: [task()] }),
      evaluatePreparationReadiness: vi.fn(),
      generateTechnicalDocument: vi.fn(),
      claimCollaboratorTask: vi.fn(),
      recordCollaboratorTaskResult: vi.fn().mockResolvedValue({}),
      completeCollaboratorTask: vi.fn(),
      transmitPreparationSnapshot: vi.fn(),
    } satisfies WizardApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderWizardHook(api, setMessage);

    act(() => {
      result.current.setWizardCaseId("case-1");
      result.current.setWizardPackageId("package-1");
      result.current.setWizardTaskId("task-1");
      result.current.setWizardResultText("  preuve technique expurgée  ");
      result.current.setWizardOutcome("RECORDED");
    });
    await act(async () => {
      await result.current.loadCollaboratorWizard();
    });
    await act(async () => {
      await result.current.recordWizardTaskResult();
    });

    expect(api.recordCollaboratorTaskResult).toHaveBeenCalledWith("task-1", {
      expected_revision: 4,
      result_text: "preuve technique expurgée",
      outcome: "RECORDED",
    });
    expect(result.current.wizardResultText).toBe("");
  });

  it("transmits a selected snapshot with an optimistic package revision and no external deposit", async () => {
    const api = {
      getCollaboratorPreparation: vi.fn().mockResolvedValue(preparation()),
      listCollaboratorTasks: vi.fn().mockResolvedValue({ case_id: "case-1", tasks: [] }),
      evaluatePreparationReadiness: vi.fn(),
      generateTechnicalDocument: vi.fn(),
      claimCollaboratorTask: vi.fn(),
      recordCollaboratorTaskResult: vi.fn(),
      completeCollaboratorTask: vi.fn(),
      transmitPreparationSnapshot: vi.fn().mockResolvedValue({}),
    } satisfies WizardApi;
    const setMessage = vi.fn() as unknown as Dispatch<SetStateAction<HookMessage | null>>;
    const { result } = renderWizardHook(api, setMessage);

    act(() => {
      result.current.setWizardCaseId("case-1");
      result.current.setWizardPackageId("package-1");
      result.current.setWizardSnapshotId(" snapshot-1 ");
      result.current.setWizardTransmissionId(" transmission-1 ");
    });
    await act(async () => {
      await result.current.loadCollaboratorWizard();
    });
    await act(async () => {
      await result.current.transmitWizardSnapshot();
    });

    expect(api.transmitPreparationSnapshot).toHaveBeenCalledWith("package-1", {
      snapshot_id: "snapshot-1",
      transmission_id: "transmission-1",
      expected_package_revision: 7,
    });
    expect(setMessage).toHaveBeenLastCalledWith({
      tone: "success",
      text: "Snapshot transmis au patron. Aucun dépôt externe n’est effectué par cette action.",
    });
  });
});
