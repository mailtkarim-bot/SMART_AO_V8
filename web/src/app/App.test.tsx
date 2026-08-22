import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import type { AssignedCase } from "../shared/types";

const { overridesRef } = vi.hoisted(() => ({
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
    listPricingScenarios: () => Promise.resolve([]),
    getDecisionDossier: () =>
      Promise.reject(Object.assign(new Error("ignored"), { status: 404 })),
  };
}

function connect() {
  fireEvent.click(screen.getByRole("button", { name: /Connexion API/i }));
  fireEvent.change(screen.getByLabelText("URL API"), {
    target: { value: "http://localhost:8000" },
  });
  fireEvent.change(screen.getByLabelText("Bearer token"), {
    target: { value: "token-test" },
  });
  fireEvent.click(screen.getByRole("button", { name: /Enregistrer et charger/i }));
}

function delayedRejection(error: Error, delayMs: number): Promise<never> {
  return new Promise((_, reject) => {
    setTimeout(() => reject(error), delayMs);
  });
}

describe("App readiness integration", () => {
  beforeEach(() => {
    window.localStorage.clear();
    overridesRef.current = {};
  });

  it("affiche l’état backend et les dépendances dans la configuration API", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /Connexion API/i }));

    expect(screen.getByRole("heading", { name: "Connexion au backend" })).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("Backend prêt");
    expect(screen.getByRole("status")).toHaveTextContent("PostgreSQL : ok");
    expect(screen.getByRole("status")).toHaveTextContent("ClamAV : ok");
  });
});

describe("App error visibility", () => {
  beforeEach(() => {
    window.localStorage.clear();
    overridesRef.current = {};
  });

  it("affiche une erreur visible quand le chargement des scénarios de chiffrage échoue", async () => {
    overridesRef.current = {
      ...baseOverrides(),
      listPricingScenarios: () =>
        delayedRejection(new Error("Scénarios indisponibles"), 30),
    };
    render(<App />);
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
    render(<App />);
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
    render(<App />);
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
