"use client";

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, refreshSession, tokens } from "./api";
import type { Role, TokenPair, User } from "./types";

type Status = "loading" | "authenticated" | "anonymous";

type AuthContextValue = {
  status: Status;
  user: User | null;
  login: (phone: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function homeFor(role: Role): string {
  switch (role) {
    case "citizen":
      return "/citizen";
    case "officer":
      return "/officer";
    default:
      return "/admin";
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [status, setStatus] = useState<Status>("loading");
  const [user, setUser] = useState<User | null>(null);

  // On first load, a refresh token in this tab means "still signed in": rotate it and load
  // the profile. Otherwise we're anonymous.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ok = tokens.refresh ? await refreshSession() : false;
      const me = ok ? await api.get<User>("/users/me").catch(() => null) : null;
      if (cancelled) return;
      setUser(me);
      setStatus(me ? "authenticated" : "anonymous");
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (phone: string, password: string) => {
    const pair = await api.post<TokenPair>("/auth/login", { phone, password }, false);
    tokens.set(pair);
    const me = await api.get<User>("/users/me");
    setUser(me);
    setStatus("authenticated");
    return me;
  }, []);

  const logout = useCallback(async () => {
    const refresh = tokens.refresh;
    if (refresh) await api.post("/auth/logout", { refresh_token: refresh }).catch(() => undefined);
    tokens.clear();
    setUser(null);
    setStatus("anonymous");
    router.replace("/login");
  }, [router]);

  const value = useMemo(() => ({ status, user, login, logout }), [status, user, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside <AuthProvider>");
  return value;
}
