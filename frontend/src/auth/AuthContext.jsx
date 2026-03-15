import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { apiClient } from "../api/client";

const STORAGE_KEY = "market_auth_state";
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [state, setState] = useState(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : { user: null, accessToken: null, refreshToken: null };
    } catch {
      return { user: null, accessToken: null, refreshToken: null };
    }
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }, [state]);

  const value = useMemo(
    () => ({
      user: state.user,
      accessToken: state.accessToken,
      refreshToken: state.refreshToken,
      isAuthenticated: Boolean(state.accessToken && state.user),
      async login(credentials) {
        const payload = await apiClient.login(credentials);
        setState({
          user: payload.user,
          accessToken: payload.access_token,
          refreshToken: payload.refresh_token,
        });
      },
      async register(data) {
        return apiClient.register(data);
      },
      async refreshAccessToken() {
        if (!state.refreshToken) {
          return null;
        }
        const payload = await apiClient.refresh(state.refreshToken);
        setState((old) => ({ ...old, accessToken: payload.access_token }));
        return payload.access_token;
      },
      async logout() {
        if (state.accessToken) {
          try {
            await apiClient.logout(state.accessToken);
          } catch {
            // Best-effort token revocation.
          }
        }
        setState({ user: null, accessToken: null, refreshToken: null });
      },
    }),
    [state]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return ctx;
}
