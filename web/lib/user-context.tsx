"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { getUserId } from "./api";

interface UserContextValue {
  userId: string;
  role: string;
  name: string;
  email: string;
  adminKey: string;
  setRole: (role: string) => void;
  setIdentity: (name: string, email: string) => void;
  setAdminKey: (key: string) => void;
  clearIdentity: () => void;
}

const UserContext = createContext<UserContextValue | null>(null);

export function UserProvider({ children }: { children: ReactNode }) {
  // All identity state starts empty for SSR and the first client render so the
  // server's HTML matches what the client will paint on pass 1. Hydration from
  // localStorage happens inside the post-mount effect below — that keeps the
  // two render trees identical and avoids the Next.js hydration-mismatch warning
  // (e.g. server paints "U" in the avatar, client lazy-inits to "NR").
  const [userId, setUserId] = useState("");
  const [role, _setRole] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [adminKey, _setAdminKey] = useState("");

  // Hydrate from localStorage once the client takes over. This is an external-store
  // sync, not a render-triggered state cascade.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    setUserId(getUserId());
    _setRole(localStorage.getItem("forge_user_role") ?? "");
    _setAdminKey(localStorage.getItem("forge_admin_key") ?? "");

    try {
      const raw = localStorage.getItem("forge_user");
      if (raw) {
        const parsed = JSON.parse(raw) as { name?: string; email?: string };
        setName(parsed.name ?? "");
        setEmail(parsed.email ?? "");
      }
    } catch {
      // ignore bad JSON
    }
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect */

  const setRole = useCallback((r: string) => {
    _setRole(r);
    localStorage.setItem("forge_user_role", r);
  }, []);

  const setIdentity = useCallback((n: string, e: string) => {
    setName(n);
    setEmail(e);
    localStorage.setItem("forge_user", JSON.stringify({ name: n, email: e }));
  }, []);

  const setAdminKey = useCallback((key: string) => {
    _setAdminKey(key);
    localStorage.setItem("forge_admin_key", key);
  }, []);

  const clearIdentity = useCallback(() => {
    setName("");
    setEmail("");
    _setRole("");
    _setAdminKey("");
    localStorage.removeItem("forge_user");
    localStorage.removeItem("forge_user_role");
    localStorage.removeItem("forge_admin_key");
  }, []);

  const value = useMemo<UserContextValue>(
    () => ({
      userId,
      role,
      name,
      email,
      adminKey,
      setRole,
      setIdentity,
      setAdminKey,
      clearIdentity,
    }),
    [userId, role, name, email, adminKey, setRole, setIdentity, setAdminKey, clearIdentity],
  );

  return (
    <UserContext.Provider value={value}>{children}</UserContext.Provider>
  );
}

export function useUser(): UserContextValue {
  const ctx = useContext(UserContext);
  if (!ctx) {
    throw new Error("useUser must be used within a <UserProvider>");
  }
  return ctx;
}
