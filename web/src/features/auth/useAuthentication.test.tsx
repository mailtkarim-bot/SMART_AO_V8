import { afterEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";

import { useAuthentication } from "./useAuthentication";

describe("useAuthentication", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    document.cookie = "smart_ao_csrf=; Max-Age=0; path=/";
  });

  it("stores the access token only in memory and exposes the server actor after login", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ access_token: "access-1", token_type: "Bearer", expires_in: 900 }), {
          status: 200,
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            actor_id: "actor-1",
            identity_id: "identity-1",
            actor_kind: "PATRON_ADMIN",
            membership_state: "ACTIVE",
          }),
          { status: 200 },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useAuthentication("https://app.example.test"));
    await act(async () => {
      await result.current.login({
        email: "patron@example.test",
        password: "x",
        tenant_id: "tenant-1",
      });
    });

    expect(result.current.accessToken).toBe("access-1");
    expect(result.current.currentActor?.actor_kind).toBe("PATRON_ADMIN");
    expect(window.localStorage.getItem("smart-ao-token")).toBeNull();
  });

  it("restores a session from the refresh cookie after a page reload", async () => {
    document.cookie = "smart_ao_csrf=csrf-restore; path=/";
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ access_token: "access-restored", token_type: "Bearer", expires_in: 900 }), {
          status: 200,
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            actor_id: "actor-1",
            identity_id: "identity-1",
            actor_kind: "PATRON_ADMIN",
            membership_state: "ACTIVE",
          }),
          { status: 200 },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useAuthentication("https://app.example.test"));
    await waitFor(() => expect(result.current.currentActor?.actor_kind).toBe("PATRON_ADMIN"));

    expect(result.current.accessToken).toBe("access-restored");
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://app.example.test/api/v1/auth/refresh",
      expect.objectContaining({ method: "POST", credentials: "include" }),
    );
  });

  it("clears the in-memory session even when logout fails over the network", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ access_token: "access-1", token_type: "Bearer", expires_in: 900 }), {
          status: 200,
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            actor_id: "actor-1",
            identity_id: "identity-1",
            actor_kind: "PATRON_ADMIN",
            membership_state: "ACTIVE",
          }),
          { status: 200 },
        ),
      )
      .mockRejectedValueOnce(new TypeError("network unavailable"));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useAuthentication("https://app.example.test"));
    await act(async () => {
      await result.current.login({
        email: "patron@example.test",
        password: "x",
        tenant_id: "tenant-1",
      });
      await expect(result.current.logout()).rejects.toThrow("network unavailable");
    });

    expect(result.current.accessToken).toBe("");
    expect(result.current.currentActor).toBeNull();
  });

  it("clears the in-memory session after a CSRF-protected logout", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ access_token: "access-1", token_type: "Bearer", expires_in: 900 }), {
          status: 200,
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            actor_id: "actor-1",
            identity_id: "identity-1",
            actor_kind: "PATRON_ADMIN",
            membership_state: "ACTIVE",
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useAuthentication("https://app.example.test"));
    await act(async () => {
      await result.current.login({
        email: "patron@example.test",
        password: "x",
        tenant_id: "tenant-1",
      });
      document.cookie = "smart_ao_csrf=csrf-1; path=/";
      await result.current.logout();
    });

    expect(result.current.accessToken).toBe("");
    expect(result.current.currentActor).toBeNull();
    expect(fetchMock).toHaveBeenLastCalledWith(
      "https://app.example.test/api/v1/auth/logout",
      expect.objectContaining({ method: "POST", credentials: "include" }),
    );
  });
});
