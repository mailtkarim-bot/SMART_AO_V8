import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

vi.mock("../features/auth/useAuthentication", () => ({
  useAuthentication: () => ({
    accessToken: "",
    currentActor: null,
    isRestoring: false,
    isAuthenticated: false,
    api: {},
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

describe("App readiness integration", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("affiche l’état backend et les dépendances dans la configuration API", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /Connexion/ }));

    expect(screen.getByRole("heading", { name: "Connexion au backend" })).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("Backend prêt");
    expect(screen.getByRole("status")).toHaveTextContent("PostgreSQL : ok");
    expect(screen.getByRole("status")).toHaveTextContent("ClamAV : ok");
  });
});
