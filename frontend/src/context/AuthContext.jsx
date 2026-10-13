import React, { createContext, useContext, useState, useCallback, useEffect } from "react";
import { api } from "../api/client.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("erp_token") || "");
  const [email, setEmail] = useState(() => localStorage.getItem("erp_email") || "");
  // The user's role decides which screens/buttons are SHOWN. It is only a UX
  // convenience: every API call is authorised again by the backend.
  const [role, setRole] = useState(() => localStorage.getItem("erp_role") || "");

  const clearSession = useCallback(() => {
    setToken("");
    setEmail("");
    setRole("");
    localStorage.removeItem("erp_token");
    localStorage.removeItem("erp_email");
    localStorage.removeItem("erp_role");
  }, []);

  const login = useCallback(async (credentials) => {
    const data = await api.login(credentials);
    setToken(data.access_token);
    setEmail(credentials.email);
    localStorage.setItem("erp_token", data.access_token);
    localStorage.setItem("erp_email", credentials.email);
    try {
      const me = await api.me(data.access_token);
      setRole(me.role);
      localStorage.setItem("erp_role", me.role);
    } catch {
      /* role stays unknown; the useEffect below retries */
    }
    return data;
  }, []);

  // Refresh the role from the server whenever we have a token (covers page
  // reloads and sessions started before this feature existed). A rejected
  // token means the session is dead, so sign out.
  useEffect(() => {
    if (!token) return undefined;
    let cancelled = false;
    api
      .me(token)
      .then((me) => {
        if (cancelled) return;
        setRole(me.role);
        localStorage.setItem("erp_role", me.role);
      })
      .catch((err) => {
        if (!cancelled && err.status === 401) clearSession();
      });
    return () => {
      cancelled = true;
    };
  }, [token, clearSession]);

  const register = useCallback(async (payload) => {
    return api.register(payload);
  }, []);

  const logout = clearSession;

  const value = { token, email, role, isAuthenticated: Boolean(token), login, register, logout };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
