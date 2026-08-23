import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createApiClient,
  type ApiClient,
} from "../../infrastructure/api";
import type { AuthSession, CurrentActor } from "../../shared/types";

export type LoginInput = {
  email: string;
  password: string;
  tenant_id: string;
};

export type AuthenticationState = {
  accessToken: string;
  currentActor: CurrentActor | null;
  isRestoring: boolean;
  isAuthenticated: boolean;
  api: ApiClient;
  login: (input: LoginInput) => Promise<CurrentActor>;
  logout: () => Promise<void>;
};

export function useAuthentication(baseUrl: string): AuthenticationState {
  const [accessToken, setAccessToken] = useState("");
  const [currentActor, setCurrentActor] = useState<CurrentActor | null>(null);
  const [isRestoring, setIsRestoring] = useState(true);

  const handleTokenRefreshed = useCallback((session: AuthSession) => {
    setAccessToken(session.access_token);
  }, []);
  const handleSessionExpired = useCallback(() => {
    setAccessToken("");
    setCurrentActor(null);
  }, []);

  const api = useMemo(
    () => createApiClient(baseUrl, accessToken, handleTokenRefreshed, handleSessionExpired),
    [accessToken, baseUrl, handleSessionExpired, handleTokenRefreshed],
  );
  const sessionApi = useMemo(
    () => createApiClient(baseUrl, "", handleTokenRefreshed, handleSessionExpired),
    [baseUrl, handleSessionExpired, handleTokenRefreshed],
  );

  useEffect(() => {
    let cancelled = false;
    setIsRestoring(true);
    setAccessToken("");
    setCurrentActor(null);

    async function restoreSession() {
      try {
        const session = await sessionApi.refresh();
        if (!session || cancelled) return;
        const authenticatedApi = createApiClient(
          baseUrl,
          session.access_token,
          handleTokenRefreshed,
          handleSessionExpired,
        );
        const actor = await authenticatedApi.getCurrentActor();
        if (!cancelled) {
          setAccessToken(session.access_token);
          setCurrentActor(actor);
        }
      } catch {
        if (!cancelled) {
          setAccessToken("");
          setCurrentActor(null);
        }
      } finally {
        if (!cancelled) setIsRestoring(false);
      }
    }

    void restoreSession();
    return () => {
      cancelled = true;
    };
  }, [baseUrl, handleSessionExpired, handleTokenRefreshed, sessionApi]);

  const login = useCallback(
    async (input: LoginInput) => {
      const session = await api.login(input);
      const authenticatedApi = createApiClient(
        baseUrl,
        session.access_token,
        handleTokenRefreshed,
        handleSessionExpired,
      );
      const actor = await authenticatedApi.getCurrentActor();
      setAccessToken(session.access_token);
      setCurrentActor(actor);
      return actor;
    },
    [api, baseUrl, handleSessionExpired, handleTokenRefreshed],
  );

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setAccessToken("");
      setCurrentActor(null);
    }
  }, [api]);

  return {
    accessToken,
    currentActor,
    isRestoring,
    isAuthenticated: Boolean(accessToken && currentActor),
    api,
    login,
    logout,
  };
}
