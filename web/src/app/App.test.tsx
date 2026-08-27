import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import type { AssignedCase } from "../shared/types";

const { authRoleRef, overridesRef } = vi.hoisted(() => ({
  authRoleRef: { current: "PATRON_ADMIN" as string },
  overridesRef: { current: {} as Record<string, unknown> },
}));

vi.mock("../infrastructure/api", () => ({
  createApiClient: () =>
    new Proxy({ ...overridesRef.current } as Record<string, unknown>, {
      get(target, prop) {
        if (typeof prop === "string" && prop in target) return target[prop];
        return () => Promise.resolve({});
      },
    }) as never,
}));

vi.mock("../features/auth/useAuthentication", () => ({
  useAuthentication: () => ({
    accessToken: "token-test",
    currentActor: {
      actor_id: "actor-1",
      identity_id: "identity-1",
      actor_kind: authRoleRef.current,
      membership_state: "ACTIVE",
    },
    isRestoring: false,
    isAuthenticated: true,
    api: new Proxy(
      {
        getEnterpriseCompany: () => Promise.reject(new Error("no company")),
        listAssignedCases: () => Promise.resolve([]),
        listPatronAssignments: () => Promise.resolve({ items: [] }),
        listPatronActions: () => Promise.resolve({ items: [], open_count: 0 }),
        listBoampObservations: () => Promise.resolve({ observations: [] }),
        getCaseDceReading: () => Promise.reject(Object.assign(new Error("missing DCE"), { status: 404 })),
        searchCaseKnowledge: () => Promise.resolve({ case_id: "case-1", query: "", results: [] }),
        listPricingScenarios: () => Promise.resolve([]),
        listDecisionRiskRequirementLinks: () => Promise.resolve({ items: [], next_cursor: null }),
        listDceContractRiskSignals: () => Promise.resolve({ case_id: "case-1", items: [] }),
        reconcileDecisionPricing: () => Promise.resolve({ link_id: "", search: "", items: [] }),
        getDecisionDossier: () => Promise.reject(Object.assign(new Error("missing"), { status: 404 })),
        ...overridesRef.current,
      } as Record<string, unknown>,
      {
      get(target, prop) {
        if (typeof prop === "string" && prop in target) return target[prop];
        return () => Promise.resolve({});
      },
    }) as never,
    login: vi.fn(),
    logout: vi.fn(),
  }),
}));

vi.mock("../features/connection/useBackendReadiness", () => ({
  useBackendReadiness: () => ({
    backendReadiness: {
      status: "ok",
      service: "smart-ao-v8",
      checks: { database: "ok", clamav: "ok" },
    },
    backendReadinessState: "ready",
    checkBackendReadiness: vi.fn(),
  }),
}));

const CASE: AssignedCase = {
  case_id: "case-1",
  work_label: "Extension de collège",
  case_lifecycle: "PREPARATION",
  commercial_stage: "QUALIFICATION",
  dce_availability: "AVAILABLE",
};

function baseOverrides(): Record<string, unknown> {
  return {
    getEnterpriseCompany: () => Promise.reject(new Error("no company")),
    listAssignedCases: () => Promise.resolve([CASE]),
    listPatronAssignments: () => Promise.resolve({ items: [] }),
    listPatronActions: () => Promise.resolve({ items: [], open_count: 0 }),
    listBoampObservations: () => Promise.resolve({ observations: [] }),
    getCaseDceReading: () => Promise.reject(Object.assign(new Error("missing DCE"), { status: 404 })),
    searchCaseKnowledge: () => Promise.resolve({ case_id: "case-1", query: "", results: [] }),
    listPricingScenarios: () => Promise.resolve([]),
    listDecisionRiskRequirementLinks: () => Promise.resolve({ items: [], next_cursor: null }),
    listDceContractRiskSignals: () => Promise.resolve({ case_id: "case-1", items: [] }),
    reconcileDecisionPricing: () => Promise.resolve({ link_id: "", search: "", items: [] }),
    getDecisionDossier: () =>
      Promise.reject(Object.assign(new Error("ignored"), { status: 404 })),
  };
}

async function renderApp() {
  await act(async () => {
    render(<App />);
    await new Promise((resolve) => setTimeout(resolve, 80));
  });
}

function connect() {
  // The auth hook is connected by the test mock; no bearer-entry flow is allowed.
}

function delayedRejection(error: Error, delayMs: number): Promise<never> {
  return new Promise((_, reject) => {
    setTimeout(() => reject(error), delayMs);
  });
}

describe("App readiness integration", () => {
  beforeEach(() => {
    window.localStorage.clear();
    authRoleRef.current = "PATRON_ADMIN";
    overridesRef.current = {};
  });

  it("affiche l’état backend et les dépendances dans la configuration API", async () => {
    await renderApp();

    fireEvent.click(screen.getByRole("button", { name: /Session/ }));

    const dialog = screen.getByRole("dialog", { name: "Connexion au backend" });
    expect(dialog).toBeVisible();
    const readiness = within(dialog).getByRole("status");
    expect(readiness).toHaveTextContent("Backend prêt");
    expect(readiness).toHaveTextContent("PostgreSQL : ok");
    expect(readiness).toHaveTextContent("ClamAV : ok");
  });
});

describe("App error visibility", () => {
  beforeEach(() => {
    window.localStorage.clear();
    authRoleRef.current = "PATRON_ADMIN";
    overridesRef.current = {};
  });

  it("ne rend pas les surfaces patronales dans l’espace collaborateur", async () => {
    authRoleRef.current = "COLLABORATEUR";
    await renderApp();

    expect(screen.getByText("ESPACE COLLABORATEUR")).toBeVisible();
    expect(screen.queryByText("Actions à traiter")).toBeNull();
    expect(screen.queryByText("Opportunités BOAMP")).toBeNull();
    expect(screen.queryByText("Dépôt")).toBeNull();
    expect(screen.queryByText("Ventes")).toBeNull();
  });

  it("affiche une erreur visible quand le chargement des scénarios de chiffrage échoue", async () => {
    overridesRef.current = {
      ...baseOverrides(),
      listPricingScenarios: () =>
        delayedRejection(new Error("Scénarios indisponibles"), 30),
    };
    await renderApp();
    connect();

    expect(
      await screen.findByText("Scénarios indisponibles", {}, { timeout: 3000 }),
    ).toBeVisible();
  });

  it("affiche une erreur visible quand le dossier de décision échoue hors 404", async () => {
    overridesRef.current = {
      ...baseOverrides(),
      getDecisionDossier: () =>
        delayedRejection(new Error("Dossier momentanément indisponible"), 30),
    };
    await renderApp();
    connect();

    expect(
      await screen.findByText("Dossier momentanément indisponible", {}, { timeout: 3000 }),
    ).toBeVisible();
  });

  it("reste silencieux quand l’absence de dossier de décision répond 404", async () => {
    overridesRef.current = {
      ...baseOverrides(),
      getDecisionDossier: () =>
        delayedRejection(
          Object.assign(new Error("ne doit jamais apparaître"), { status: 404 }),
          50,
        ),
    };
    await renderApp();
    connect();

    expect(
      await screen.findByRole(
        "heading",
        { name: "Extension de collège" },
        { timeout: 3000 },
      ),
    ).toBeVisible();
    await new Promise((resolve) => setTimeout(resolve, 150));
    expect(screen.queryByText("ne doit jamais apparaître")).toBeNull();
  });
});
