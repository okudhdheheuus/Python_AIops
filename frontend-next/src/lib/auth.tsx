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

function decodeJwtRole(token: string): string {
  try {
    const segment = token.split(".")[1];
    if (!segment) return "viewer";
    const base64 = segment.replace(/-/g, "+").replace(/_/g, "/");
    const json = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    );
    const payload = JSON.parse(json);
    return payload.role || "viewer";
  } catch {
    return "viewer";
  }
}

function loadFromStorage() {
  if (typeof window === "undefined") return { token: null, user: null };
  const savedToken = localStorage.getItem("token");
  if (!savedToken) return { token: null, user: null };
  const savedUserRaw = localStorage.getItem("user");
  let user: User | null = null;
  if (savedUserRaw) {
    try {
      const savedUser = JSON.parse(savedUserRaw) as User;
      // 角色从 token 重新推导，避免旧的 localStorage 里误存为 admin
      user = { username: savedUser.username, role: decodeJwtRole(savedToken) };
    } catch {
      user = null;
    }
  }
  return { token: savedToken, user };
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
      // 修正本地旧缓存（角色曾被硬编码为 admin），写回正确角色
      if (savedUser) {
        const raw = localStorage.getItem("user");
        const healed = JSON.stringify(savedUser);
        if (raw !== healed) localStorage.setItem("user", healed);
      }
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
      const userInfo = { username, role: decodeJwtRole(jwt) };
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
