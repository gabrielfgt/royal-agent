import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { dashboardApi, UNAUTHORIZED_EVENT } from "@/lib/api";
import { getToken, setToken } from "@/lib/session";

interface AuthContextValue {
  token: string | null;
  login: (token: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(getToken);

  const logout = useCallback(() => {
    setToken(null);
    setTokenState(null);
  }, []);

  const login = useCallback(async (candidate: string) => {
    const trimmed = candidate.trim();
    await dashboardApi.check(trimmed);
    setToken(trimmed);
    setTokenState(trimmed);
  }, []);

  useEffect(() => {
    window.addEventListener(UNAUTHORIZED_EVENT, logout);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, logout);
  }, [logout]);

  const value = useMemo(() => ({ token, login, logout }), [token, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth precisa de AuthProvider");
  return context;
}
