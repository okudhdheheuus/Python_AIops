"use client";

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";

interface User {
  username: string;
  role: string;
}

interface AuthContextType {
  token: string | null;
  user: User | null;
  login: (username: string, password: string) => Promise<string | null>;
  logout: () => void;
  isAuthenticated: boolean;
  authFetch: (url: string, options?: RequestInit) => Promise<Response>;
}

const AuthContext = createContext<AuthContextType>({
  token: null,
  user: null,
  login: async () => null,
  logout: () => {},
  isAuthenticated: false,
  authFetch: async () => { throw new Error("not initialized"); },
});

function loadFromStorage() {
  if (typeof window === "undefined") return { token: null, user: null };
  const savedToken = localStorage.getItem("token");
  const savedUser = localStorage.getItem("user");
  if (!savedToken || !savedUser) return { token: null, user: null };
  try {
    return { token: savedToken, user: JSON.parse(savedUser) as User };
  } catch {
    return { token: null, user: null };
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [mounted, setMounted] = useState(false);
  const [token, setToken] = useState<string | null>(() => loadFromStorage().token);
  const [user, setUser] = useState<User | null>(() => loadFromStorage().user);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
    const { token: savedToken, user: savedUser } = loadFromStorage();
    if (savedToken) {
      setToken(savedToken);
      setUser(savedUser);
    }
    const handleStorage = (event: StorageEvent) => {
      if (event.key === "token" || event.key === "user") {
        const { token: t, user: u } = loadFromStorage();
        setToken(t);
        setUser(u);
      }
    };
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  const login = useCallback(async (username: string, password: string): Promise<string | null> => {
    try {
      const resp = await fetch(`/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!resp.ok) {
        const err = await resp.json();
        return err.detail || "登录失败";
      }
      const data = await resp.json();
      const jwt = data.access_token;
      const userInfo = { username, role: "admin" };
      setToken(jwt);
      setUser(userInfo);
      localStorage.setItem("token", jwt);
      localStorage.setItem("user", JSON.stringify(userInfo));
      return null;
    } catch {
      return "无法连接后端服务";
    }
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    localStorage.removeItem("token");
    localStorage.removeItem("user");
  }, []);

  const authFetch = useCallback(async (url: string, options?: RequestInit): Promise<Response> => {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options?.headers as Record<string, string> || {}),
    };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    const resp = await fetch(url, { ...options, headers });
    if (resp.status === 401) {
      logout();
    }
    return resp;
  }, [token, logout]);

  return (
    <AuthContext.Provider value={{ token, user, login, logout, isAuthenticated: mounted && !!token, authFetch }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
