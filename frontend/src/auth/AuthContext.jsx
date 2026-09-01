import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { clearToken, fetchMe, getToken, login as apiLogin, setToken } from "../api/client.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function boot() {
      if (!getToken()) {
        setLoading(false);
        return;
      }
      try {
        setUser(await fetchMe());
      } catch {
        clearToken();
        setUser(null);
      } finally {
        setLoading(false);
      }
    }
    boot();
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      async login(email, password) {
        const { access_token } = await apiLogin(email, password);
        setToken(access_token);
        const me = await fetchMe();
        setUser(me);
        return me;
      },
      logout() {
        clearToken();
        setUser(null);
      },
    }),
    [user, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
