import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { AuthUser, LoginPayload, LoginResponse, RegisterPayload, UserRole } from "./types";

const API_BASE = "http://localhost:8000/api/v1";
const TOKEN_KEY = "msp.auth.token";
const USER_KEY = "msp.auth.user";

type AuthContextValue = {
  token: string | null;
  user: AuthUser | null;
  isAuthenticated: boolean;
  login: (role: UserRole, payload: LoginPayload) => Promise<void>;
  register: (role: UserRole, payload: RegisterPayload) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function getInitialToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

function getInitialUser(): AuthUser | null {
  const raw = localStorage.getItem(USER_KEY);
  return raw ? (JSON.parse(raw) as AuthUser) : null;
}

function applySession(data: LoginResponse, setToken: (t: string) => void, setUser: (u: AuthUser) => void) {
  const nextUser: AuthUser = { email: data.email, role: data.role, full_name: data.full_name };
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(nextUser));
  setToken(data.access_token);
  setUser(nextUser);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(getInitialToken);
  const [user, setUser] = useState<AuthUser | null>(getInitialUser);

  const login = useCallback(async (role: UserRole, payload: LoginPayload): Promise<void> => {
    const response = await fetch(`${API_BASE}/auth/login/${role}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error((body as { detail?: string }).detail ?? "Invalid credentials");
    }

    const data = (await response.json()) as LoginResponse;
    applySession(data, setToken, setUser);
  }, []);

  const register = useCallback(async (role: UserRole, payload: RegisterPayload): Promise<void> => {
    const response = await fetch(`${API_BASE}/auth/register/${role}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error((body as { detail?: string }).detail ?? "Registration failed");
    }

    const data = (await response.json()) as LoginResponse;
    applySession(data, setToken, setUser);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      user,
      isAuthenticated: Boolean(token && user),
      login,
      register,
      logout,
    }),
    [token, user, login, register, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
