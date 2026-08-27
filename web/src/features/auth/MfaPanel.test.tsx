import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ApiClient } from "../../infrastructure/api";
import { MfaPanel } from "./MfaPanel";

function renderPanel() {
  const api = {
    beginTotpEnrollment: vi.fn().mockResolvedValue({
      factor_id: "factor-1",
      otpauth_uri: "otpauth://totp/SMART-AO:test@example.test",
      recovery_codes: ["one-time-1", "one-time-2"],
      expires_at: "2026-08-27T00:00:00Z",
    }),
    confirmTotpEnrollment: vi.fn().mockResolvedValue({
      access_token: "new-token",
      token_type: "Bearer",
      expires_in: 900,
      used_recovery_code: false,
    }),
    disableTotp: vi.fn().mockResolvedValue(undefined),
  } as unknown as ApiClient;
  const setMessage = vi.fn();
  render(<MfaPanel api={api} setMessage={setMessage} />);
  return { api, setMessage };
}

describe("MfaPanel", () => {
  it("starts and confirms an enrollment while displaying recovery codes", async () => {
    const { api, setMessage } = renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "Démarrer l’enrôlement" }));

    expect(await screen.findByText(/one-time-1/)).toBeInTheDocument();
    expect(screen.getByText(/otpauth:\/\/totp/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Code affiché par l’application"), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirmer l’activation" }));

    await waitFor(() => expect(api.confirmTotpEnrollment).toHaveBeenCalledWith("factor-1", "123456"));
    expect(setMessage).toHaveBeenCalledWith({ tone: "success", text: "MFA TOTP activée pour cette identité." });
  });

  it("requires a code to request TOTP disablement", async () => {
    const { api } = renderPanel();
    fireEvent.change(screen.getByLabelText("Code TOTP actuel"), { target: { value: "654321" } });
    fireEvent.click(screen.getByRole("button", { name: "Désactiver MFA" }));

    await waitFor(() => expect(api.disableTotp).toHaveBeenCalledWith("654321"));
  });
});
