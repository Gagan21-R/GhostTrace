import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, getToken, setToken } from "./api";

export interface User { id: string; email: string; full_name: string; role: string; is_active: boolean; created_at: string; last_login_at?: string }
interface AuthState { user: User | null; permissions: string[]; loading: boolean; login: (e: string, p: string) => Promise<void>;
  register: (e: string, n: string, p: string) => Promise<void>; logout: () => Promise<void>; can: (perm: string) => boolean }

const Ctx = createContext<AuthState>(null as unknown as AuthState);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [permissions, setPerms] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) { setLoading(false); return; }
    api.get<any>("/api/auth/me").then((r) => { setUser(r.user); setPerms(r.permissions); }).catch(() => setToken(null)).finally(() => setLoading(false));
  }, []);

  const accept = (r: any) => { setToken(r.access_token); setUser(r.user); setPerms(r.permissions); };
  const value: AuthState = {
    user, permissions, loading,
    login: async (email, password) => accept(await api.post("/api/auth/login", { email, password })),
    register: async (email, full_name, password) => accept(await api.post("/api/auth/register", { email, full_name, password })),
    logout: async () => {
      try { await api.post("/api/auth/logout"); } catch { /* token may already be invalid */ }
      setToken(null); setUser(null); setPerms([]); location.assign("/login");
    },
    can: (p) => permissions.includes(p),
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
