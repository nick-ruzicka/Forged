# Forge Next.js Frontend Rewrite — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the vanilla JS frontend with a Next.js/React/Tailwind/shadcn app that looks and feels like Linear/Vercel — dark monochrome with persistent sidebar navigation.

**Architecture:** Monorepo — new `web/` directory alongside existing Flask `api/`. Next.js consumes Flask as a REST API via proxy rewrites. All data fetching is client-side via SWR hooks. No backend changes.

**Tech Stack:** Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, shadcn/ui, SWR, sonner (toasts)

**Spec:** `docs/superpowers/specs/2026-04-18-nextjs-frontend-rewrite-design.md`

---

## Task 1: Scaffold Next.js + Tailwind + shadcn

**Files:**
- Create: `web/` (entire directory via create-next-app)
- Create: `web/tailwind.config.ts`
- Create: `web/next.config.ts`
- Create: `web/app/globals.css`
- Create: `web/app/layout.tsx`
- Create: `web/app/page.tsx`

- [ ] **Step 1: Create Next.js app**

```bash
cd /Users/nicholasruzicka/projects/forge
npx create-next-app@latest web --typescript --tailwind --eslint --app --src-dir=false --import-alias="@/*" --use-npm
```

When prompted: use App Router (yes), use `src/` directory (no), customize import alias (yes, `@/*`).

- [ ] **Step 2: Install dependencies**

```bash
cd web
npm install swr sonner next-themes class-variance-authority clsx tailwind-merge lucide-react
npm install -D @types/node
```

- [ ] **Step 3: Initialize shadcn**

```bash
npx shadcn@latest init
```

When prompted: style (New York), base color (Zinc), CSS variables (yes). This creates `components/ui/`, `lib/utils.ts`, and updates `tailwind.config.ts`.

- [ ] **Step 4: Install shadcn components**

```bash
npx shadcn@latest add button badge card command dialog dropdown-menu input textarea select tabs tooltip separator skeleton
```

- [ ] **Step 5: Configure dark theme colors in globals.css**

Replace the contents of `web/app/globals.css` with:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 0%;
    --foreground: 0 0% 93%;
    --card: 0 0% 4%;
    --card-foreground: 0 0% 93%;
    --popover: 0 0% 4%;
    --popover-foreground: 0 0% 93%;
    --primary: 220 100% 50%;
    --primary-foreground: 0 0% 100%;
    --secondary: 0 0% 7%;
    --secondary-foreground: 0 0% 93%;
    --muted: 0 0% 7%;
    --muted-foreground: 0 0% 53%;
    --accent: 0 0% 7%;
    --accent-foreground: 0 0% 93%;
    --destructive: 0 84% 60%;
    --destructive-foreground: 0 0% 100%;
    --border: 0 0% 10%;
    --input: 0 0% 10%;
    --ring: 220 100% 50%;
    --radius: 0.375rem;

    --success: 160 70% 48%;
    --warning: 38 92% 50%;
    --surface: 0 0% 4%;
    --surface-2: 0 0% 7%;
    --border-strong: 0 0% 16%;
    --text-secondary: 0 0% 53%;
    --text-muted: 0 0% 33%;
  }
}

@layer base {
  * {
    @apply border-border;
  }
  body {
    @apply bg-background text-foreground;
    font-feature-settings: "rlig" 1, "calt" 1;
  }
}
```

- [ ] **Step 6: Configure next.config.ts with API proxy**

Replace `web/next.config.ts`:

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8090/api/:path*",
      },
      {
        source: "/apps/:path*",
        destination: "http://localhost:8090/apps/:path*",
      },
    ];
  },
};

export default nextConfig;
```

- [ ] **Step 7: Set up root layout with Inter + Geist Mono fonts**

Replace `web/app/layout.tsx`:

```tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import localFont from "next/font/local";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
});

const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-mono",
  weight: "100 900",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Forge",
  description: "Internal AI tool marketplace",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} ${geistMono.variable} font-sans antialiased`}>
        {children}
      </body>
    </html>
  );
}
```

- [ ] **Step 8: Create placeholder home page**

Replace `web/app/page.tsx`:

```tsx
export default function CatalogPage() {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <h1 className="text-2xl font-semibold">Forge</h1>
    </div>
  );
}
```

- [ ] **Step 9: Verify dev server starts**

```bash
cd /Users/nicholasruzicka/projects/forge/web
npm run dev
```

Open http://localhost:3000 — should show "Forge" centered on a black background with white text.

- [ ] **Step 10: Commit**

```bash
cd /Users/nicholasruzicka/projects/forge
git add web/
git commit -m "feat: scaffold Next.js app with Tailwind + shadcn dark theme"
```

---

## Task 2: API Client, Types, and User Context

**Files:**
- Create: `web/lib/api.ts`
- Create: `web/lib/types.ts`
- Create: `web/lib/user-context.tsx`
- Create: `web/lib/milestones.ts`

- [ ] **Step 1: Create TypeScript types for API responses**

Create `web/lib/types.ts`:

```typescript
export interface App {
  id: number;
  slug: string;
  name: string;
  tagline?: string;
  description?: string;
  category?: string;
  tags?: string;
  icon?: string;
  status: string;
  version: number;
  delivery?: string;
  install_command?: string;
  source_url?: string;
  launch_url?: string;
  app_type?: string;
  author_name?: string;
  author_email?: string;
  install_count?: number;
  open_count?: number;
  avg_rating?: number;
  role_tags?: string | string[];
  created_at?: string;
  deployed_at?: string;
}

export interface Skill {
  id: number;
  title: string;
  description?: string;
  use_case?: string;
  category?: string;
  prompt_text?: string;
  author_name?: string;
  source_url?: string;
  upvotes: number;
  copy_count: number;
  created_at?: string;
}

export interface UserItem {
  id: number;
  tool_id: number;
  slug?: string;
  name?: string;
  tagline?: string;
  icon?: string;
  delivery?: string;
  source_url?: string;
  install_command?: string;
  open_count?: number;
  added_at?: string;
  last_opened_at?: string;
}

export interface Star {
  id: number;
  tool_id: number;
  slug?: string;
  name?: string;
  tagline?: string;
  icon?: string;
}

export interface Review {
  id: number;
  tool_id: number;
  rating: number;
  text?: string;
  user_name?: string;
  user_email?: string;
  created_at?: string;
}

export interface ClaudeRun {
  id: number;
  prompt: string;
  output?: string;
  status: "running" | "complete" | "error";
  exit_code?: number;
  started_at?: string;
  completed_at?: string;
}

export interface AdminStats {
  apps_live: number;
  apps_pending: number;
  skills_total: number;
}

export interface QueueItem extends App {
  html_length?: number;
}

export interface InspectionBadge {
  icon: string;
  label: string;
  detail?: string;
  tone?: "warn" | "info";
}
```

- [ ] **Step 2: Create API client**

Create `web/lib/api.ts`:

```typescript
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

function getUserId(): string {
  if (typeof window === "undefined") return "";
  let id = localStorage.getItem("forge_user_id") || "";
  if (!id) {
    id = crypto.randomUUID?.() ?? `anon-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    localStorage.setItem("forge_user_id", id);
  }
  return id;
}

function getAdminKey(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("forge_admin_key") || "";
}

type FetchOptions = {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
};

export async function api<T>(path: string, opts?: FetchOptions): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "X-Forge-User-Id": getUserId(),
    ...opts?.headers,
  };
  const adminKey = getAdminKey();
  if (adminKey) {
    headers["X-Admin-Key"] = adminKey;
  }
  if (opts?.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(path, {
    method: opts?.method || "GET",
    headers,
    body: opts?.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => `HTTP ${res.status}`);
    throw new ApiError(res.status, text);
  }
  return res.json();
}

// ---- Apps ----

export const getApps = (params?: Record<string, string>) => {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return api<{ tools: import("./types").App[]; total: number }>(`/api/tools${qs}`);
};

export const getAppBySlug = (slug: string) =>
  api<import("./types").App>(`/api/tools/slug/${encodeURIComponent(slug)}`);

export const getAppReviews = (toolId: number) =>
  api<{ reviews: import("./types").Review[] }>(`/api/tools/${toolId}/reviews`);

export const postReview = (toolId: number, rating: number, text: string) =>
  api(`/api/tools/${toolId}/reviews`, { method: "POST", body: { rating, text } });

export const getAppInspection = (toolId: number) =>
  api<{ badges: import("./types").InspectionBadge[] }>(`/api/tools/${toolId}/inspection`);

// ---- User shelf ----

export const getMyItems = () =>
  api<{ items: import("./types").UserItem[] }>("/api/me/items");

export const addItem = (toolId: number) =>
  api(`/api/me/items/${toolId}`, { method: "POST", body: {} });

export const removeItem = (toolId: number) =>
  api(`/api/me/items/${toolId}`, { method: "DELETE" });

export const launchItem = (toolId: number) =>
  api(`/api/me/items/${toolId}/launch`, { method: "POST", body: {} });

export const installItem = (toolId: number) =>
  api(`/api/me/items/${toolId}/install`, { method: "POST", body: {} });

// ---- Stars ----

export const getMyStars = () =>
  api<{ items: import("./types").Star[] }>("/api/me/stars");

export const addStar = (toolId: number) =>
  api(`/api/me/stars/${toolId}`, { method: "POST", body: {} });

export const removeStar = (toolId: number) =>
  api(`/api/me/stars/${toolId}`, { method: "DELETE" });

// ---- Skills ----

export const getSkills = (params?: Record<string, string>) => {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return api<{ skills: import("./types").Skill[] } | import("./types").Skill[]>(`/api/skills${qs}`);
};

export const upvoteSkill = (skillId: number) =>
  api(`/api/skills/${skillId}/upvote`, { method: "POST" });

export const downloadSkillUrl = (skillId: number) =>
  `/api/skills/${skillId}/download`;

export const submitSkill = (data: Record<string, string>) =>
  api("/api/skills", { method: "POST", body: data });

export const getMySkills = () =>
  api<{ skills: import("./types").Skill[] }>("/api/me/skills");

export const subscribeSkill = (skillId: number) =>
  api(`/api/me/skills/${skillId}`, { method: "POST", body: {} });

// ---- Submit ----

export const submitApp = (data: FormData | Record<string, unknown>) => {
  if (data instanceof FormData) {
    return fetch("/api/submit/app", { method: "POST", body: data, headers: { "X-Forge-User-Id": getUserId() } }).then(r => r.json());
  }
  return api("/api/submit/app", { method: "POST", body: data });
};

export const submitFromGithub = (githubUrl: string, metadata: Record<string, string>) =>
  api("/api/submit/from-github", { method: "POST", body: { github_url: githubUrl, ...metadata } });

// ---- Admin ----

export const getAdminQueue = () =>
  api<{ tools: import("./types").QueueItem[] }>("/api/admin/queue");

export const getAdminStats = () =>
  api<import("./types").AdminStats>("/api/admin/analytics");

export const approveApp = (toolId: number) =>
  api(`/api/admin/tools/${toolId}/approve`, { method: "POST", body: { reviewer: "admin" } });

export const rejectApp = (toolId: number, reason: string) =>
  api(`/api/admin/tools/${toolId}/reject`, { method: "POST", body: { reason } });

// ---- Claude Runs ----

export const getClaudeRuns = () =>
  api<{ runs: import("./types").ClaudeRun[] }>("/api/claude-runs");

export const getClaudeRunLog = (runId: number) =>
  api<import("./types").ClaudeRun>(`/api/claude-runs/${runId}/log`);

export const execClaude = (prompt: string) =>
  api<import("./types").ClaudeRun>("/api/claude-exec", { method: "POST", body: { prompt } });

// ---- Agent ----

export const getAgentRunning = () =>
  api<{ running: boolean }>("/api/forge-agent/running").catch(() => ({ running: false }));
```

- [ ] **Step 3: Create User Context provider**

Create `web/lib/user-context.tsx`:

```tsx
"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";

interface UserState {
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

const UserContext = createContext<UserState | null>(null);

function readLS(key: string): string {
  try { return localStorage.getItem(key) || ""; } catch { return ""; }
}
function writeLS(key: string, value: string) {
  try { localStorage.setItem(key, value); } catch {}
}
function removeLS(key: string) {
  try { localStorage.removeItem(key); } catch {}
}

function ensureUserId(): string {
  let id = readLS("forge_user_id");
  if (!id) {
    id = crypto.randomUUID?.() ?? `anon-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    writeLS("forge_user_id", id);
  }
  return id;
}

export function UserProvider({ children }: { children: ReactNode }) {
  const [userId, setUserId] = useState("");
  const [role, setRoleState] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [adminKey, setAdminKeyState] = useState("");

  useEffect(() => {
    setUserId(ensureUserId());
    setRoleState(readLS("forge_user_role"));
    const user = (() => { try { return JSON.parse(readLS("forge_user") || "{}"); } catch { return {}; } })();
    setName(user.name || "");
    setEmail(user.email || "");
    setAdminKeyState(readLS("forge_admin_key"));
  }, []);

  const setRole = (r: string) => { writeLS("forge_user_role", r); setRoleState(r); };
  const setIdentity = (n: string, e: string) => {
    writeLS("forge_user", JSON.stringify({ name: n, email: e }));
    setName(n); setEmail(e);
  };
  const setAdminKey = (k: string) => { writeLS("forge_admin_key", k); setAdminKeyState(k); };
  const clearIdentity = () => { removeLS("forge_user"); setName(""); setEmail(""); };

  return (
    <UserContext.Provider value={{ userId, role, name, email, adminKey, setRole, setIdentity, setAdminKey, clearIdentity }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error("useUser must be used within UserProvider");
  return ctx;
}
```

- [ ] **Step 4: Create milestone tracker**

Create `web/lib/milestones.ts`:

```typescript
const MESSAGES: Record<string, string> = {
  first_install: "You installed your first app! Open it from the sidebar.",
  first_star: "Starred! Find it in My Forge \u2192 Saved.",
  first_submission: "App submitted! It's in the review queue.",
  first_approval: "Your app was approved and is live.",
};

export function trackMilestone(name: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    const list: string[] = JSON.parse(localStorage.getItem("forge_milestones") || "[]");
    if (list.includes(name)) return null;
    list.push(name);
    localStorage.setItem("forge_milestones", JSON.stringify(list));
    return MESSAGES[name] || null;
  } catch {
    return null;
  }
}
```

- [ ] **Step 5: Commit**

```bash
cd /Users/nicholasruzicka/projects/forge
git add web/lib/
git commit -m "feat: add API client, types, user context, and milestone tracker"
```

---

## Task 3: SWR Hooks

**Files:**
- Create: `web/lib/hooks.ts`

- [ ] **Step 1: Create all SWR hooks**

Create `web/lib/hooks.ts`:

```typescript
"use client";

import useSWR, { mutate as globalMutate } from "swr";
import * as api from "./api";
import type { App, Skill, UserItem, Star, Review, ClaudeRun, AdminStats, QueueItem } from "./types";

// ---- Apps ----

export function useApps(filters?: Record<string, string>) {
  const key = filters ? `/api/tools?${new URLSearchParams(filters)}` : "/api/tools";
  return useSWR(key, () => api.getApps(filters).then(r => r.tools));
}

export function useApp(slug: string | null) {
  return useSWR(slug ? `/api/tools/slug/${slug}` : null, () => api.getAppBySlug(slug!));
}

// ---- User shelf ----

export function useMyItems() {
  return useSWR("/api/me/items", () => api.getMyItems().then(r => r.items));
}

export function useMyStars() {
  return useSWR("/api/me/stars", () => api.getMyStars().then(r => r.items));
}

export function useMySkills() {
  return useSWR("/api/me/skills", () => api.getMySkills().then(r => r.skills));
}

// ---- Skills ----

export function useSkills(filters?: Record<string, string>) {
  const key = filters ? `/api/skills?${new URLSearchParams(filters)}` : "/api/skills";
  return useSWR(key, async () => {
    const res = await api.getSkills(filters);
    return Array.isArray(res) ? res : (res as { skills: Skill[] }).skills || [];
  });
}

// ---- Reviews ----

export function useReviews(toolId: number | null) {
  return useSWR(toolId ? `/api/tools/${toolId}/reviews` : null, () => api.getAppReviews(toolId!).then(r => r.reviews));
}

// ---- Admin ----

export function useAdminQueue() {
  return useSWR("/api/admin/queue", () => api.getAdminQueue().then(r => r.tools));
}

export function useAdminStats() {
  return useSWR("/api/admin/analytics", () => api.getAdminStats());
}

// ---- Claude Runs ----

export function useClaudeRuns() {
  return useSWR("/api/claude-runs", () => api.getClaudeRuns().then(r => r.runs), { refreshInterval: 5000 });
}

export function useClaudeRun(runId: number | null) {
  const isRunning = (data?: ClaudeRun) => data?.status === "running";
  return useSWR(
    runId ? `/api/claude-runs/${runId}/log` : null,
    () => api.getClaudeRunLog(runId!),
    { refreshInterval: (data) => isRunning(data) ? 3000 : 0 },
  );
}

// ---- Agent status ----

export function useAgentRunning(enabled = false) {
  return useSWR(enabled ? "/api/forge-agent/running" : null, () => api.getAgentRunning(), { refreshInterval: 15000 });
}

// ---- Mutation helpers (optimistic) ----

export async function toggleStar(toolId: number, isStarred: boolean) {
  if (isStarred) {
    await globalMutate("/api/me/stars", (items: Star[] | undefined) => items?.filter(s => s.tool_id !== toolId), false);
    await api.removeStar(toolId);
  } else {
    await api.addStar(toolId);
  }
  globalMutate("/api/me/stars");
}

export async function installApp(toolId: number) {
  await api.addItem(toolId);
  globalMutate("/api/me/items");
}

export async function uninstallApp(toolId: number) {
  await globalMutate("/api/me/items", (items: UserItem[] | undefined) => items?.filter(i => i.tool_id !== toolId), false);
  await api.removeItem(toolId);
  globalMutate("/api/me/items");
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/nicholasruzicka/projects/forge
git add web/lib/hooks.ts
git commit -m "feat: add SWR hooks for all API endpoints"
```

---

## Task 4: Root Layout, Sidebar, and Command Menu

**Files:**
- Modify: `web/app/layout.tsx`
- Create: `web/components/sidebar.tsx`
- Create: `web/components/command-menu.tsx`
- Create: `web/components/keyboard-shortcuts.tsx`
- Create: `web/components/toaster-provider.tsx`

- [ ] **Step 1: Create toaster provider**

Create `web/components/toaster-provider.tsx`:

```tsx
"use client";

import { Toaster } from "sonner";

export function ToasterProvider() {
  return (
    <Toaster
      position="bottom-right"
      toastOptions={{
        style: {
          background: "#111",
          border: "1px solid #1a1a1a",
          color: "#ededed",
        },
      }}
    />
  );
}
```

- [ ] **Step 2: Create sidebar component**

Create `web/components/sidebar.tsx`:

```tsx
"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutGrid, Sparkles, Box, Upload, Shield, ChevronLeft, ChevronRight, Search, Menu, X } from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip";
import { useMyItems } from "@/lib/hooks";
import { useUser } from "@/lib/user-context";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Apps", icon: LayoutGrid },
  { href: "/skills", label: "Skills", icon: Sparkles },
  { href: "/my-forge", label: "My Forge", icon: Box },
  { href: "/publish", label: "Publish", icon: Upload },
];

export function Sidebar({ onOpenCommandMenu }: { onOpenCommandMenu: () => void }) {
  const pathname = usePathname();
  const { adminKey, name, email } = useUser();
  const { data: installedItems } = useMyItems();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem("forge_sidebar_collapsed") === "1");
    } catch {}
  }, []);

  const toggleCollapsed = () => {
    const next = !collapsed;
    setCollapsed(next);
    try { localStorage.setItem("forge_sidebar_collapsed", next ? "1" : "0"); } catch {}
  };

  const initials = (() => {
    const source = name || email || "";
    if (!source) return "?";
    const parts = source.split(/[\s@._-]+/).filter(Boolean);
    if (parts.length === 0) return "?";
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[1][0]).toUpperCase();
  })();

  const visibleItems = (installedItems || [])
    .sort((a, b) => (b.last_opened_at || "").localeCompare(a.last_opened_at || ""))
    .slice(0, 8);

  const sidebarContent = (
    <TooltipProvider delayDuration={0}>
      <div className={cn("flex flex-col h-full bg-[hsl(var(--surface))] border-r border-border", collapsed ? "w-14" : "w-[220px]")}>
        {/* Logo */}
        <div className="px-3 py-4">
          <Link href="/" className="flex items-center gap-2 text-foreground hover:text-foreground">
            <span className="text-[hsl(var(--primary))] text-lg">⚒</span>
            {!collapsed && <span className="font-mono font-bold text-sm tracking-wide">FORGE</span>}
          </Link>
        </div>

        {/* Search trigger */}
        <div className="px-2 mb-2">
          <button
            onClick={onOpenCommandMenu}
            className={cn(
              "w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm text-muted-foreground hover:bg-[hsl(var(--surface-2))] transition-colors",
              collapsed && "justify-center"
            )}
          >
            <Search className="h-4 w-4 shrink-0" />
            {!collapsed && <span className="flex-1 text-left">Search...</span>}
            {!collapsed && <kbd className="text-[10px] text-muted-foreground bg-[hsl(var(--surface-2))] px-1.5 py-0.5 rounded">⌘K</kbd>}
          </button>
        </div>

        {/* Main nav */}
        <nav className="px-2 space-y-0.5">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const isActive = href === "/" ? pathname === "/" : pathname.startsWith(href);
            const link = (
              <Link
                key={href}
                href={href}
                onClick={() => setMobileOpen(false)}
                className={cn(
                  "flex items-center gap-2 px-2 py-1.5 rounded-md text-sm transition-colors",
                  isActive
                    ? "bg-[hsl(var(--primary)/0.08)] text-[hsl(var(--primary))]"
                    : "text-muted-foreground hover:bg-[hsl(var(--surface-2))] hover:text-foreground",
                  collapsed && "justify-center"
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {!collapsed && <span>{label}</span>}
              </Link>
            );
            if (collapsed) {
              return (
                <Tooltip key={href}>
                  <TooltipTrigger asChild>{link}</TooltipTrigger>
                  <TooltipContent side="right">{label}</TooltipContent>
                </Tooltip>
              );
            }
            return link;
          })}
        </nav>

        {/* Installed apps */}
        {visibleItems.length > 0 && (
          <>
            <Separator className="my-3 mx-2" />
            <div className="px-2 space-y-0.5 overflow-y-auto flex-shrink">
              {!collapsed && <p className="px-2 mb-1 text-[10px] uppercase tracking-widest text-muted-foreground">Installed</p>}
              {visibleItems.map(item => {
                const link = (
                  <Link
                    key={item.tool_id}
                    href={`/apps/${item.slug || item.tool_id}`}
                    onClick={() => setMobileOpen(false)}
                    className={cn(
                      "flex items-center gap-2 px-2 py-1 rounded-md text-sm text-muted-foreground hover:bg-[hsl(var(--surface-2))] hover:text-foreground transition-colors",
                      collapsed && "justify-center"
                    )}
                  >
                    <span className="text-base shrink-0">{item.icon || "⊞"}</span>
                    {!collapsed && <span className="truncate">{item.name}</span>}
                  </Link>
                );
                if (collapsed) {
                  return (
                    <Tooltip key={item.tool_id}>
                      <TooltipTrigger asChild>{link}</TooltipTrigger>
                      <TooltipContent side="right">{item.name}</TooltipContent>
                    </Tooltip>
                  );
                }
                return link;
              })}
              {!collapsed && (installedItems || []).length > 8 && (
                <Link href="/my-forge" className="px-2 py-1 text-xs text-muted-foreground hover:text-foreground">
                  Show all...
                </Link>
              )}
            </div>
          </>
        )}

        {/* Spacer */}
        <div className="flex-1" />

        {/* Admin */}
        {adminKey && (
          <div className="px-2 mb-1">
            <Link
              href="/admin"
              onClick={() => setMobileOpen(false)}
              className={cn(
                "flex items-center gap-2 px-2 py-1.5 rounded-md text-sm text-muted-foreground hover:bg-[hsl(var(--surface-2))] hover:text-foreground transition-colors",
                pathname.startsWith("/admin") && "bg-[hsl(var(--primary)/0.08)] text-[hsl(var(--primary))]",
                collapsed && "justify-center"
              )}
            >
              <Shield className="h-4 w-4 shrink-0" />
              {!collapsed && <span>Admin</span>}
            </Link>
          </div>
        )}

        {/* User + collapse toggle */}
        <div className="px-2 pb-3 flex items-center gap-2">
          <div className={cn(
            "h-7 w-7 rounded-full bg-[hsl(var(--primary))] text-white text-xs font-semibold flex items-center justify-center shrink-0",
          )}>
            {initials}
          </div>
          {!collapsed && <span className="text-xs text-muted-foreground truncate flex-1">{name || email || "Anonymous"}</span>}
          <button onClick={toggleCollapsed} className="text-muted-foreground hover:text-foreground ml-auto hidden md:block">
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </TooltipProvider>
  );

  return (
    <>
      {/* Mobile hamburger bar */}
      <div className="md:hidden fixed top-0 left-0 right-0 h-12 bg-[hsl(var(--surface))] border-b border-border flex items-center px-3 z-50">
        <button onClick={() => setMobileOpen(!mobileOpen)} className="text-foreground">
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
        <Link href="/" className="ml-3 font-mono font-bold text-sm tracking-wide">⚒ FORGE</Link>
      </div>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-40 bg-black/60" onClick={() => setMobileOpen(false)}>
          <div className="w-[220px] h-full" onClick={e => e.stopPropagation()}>
            {sidebarContent}
          </div>
        </div>
      )}

      {/* Desktop sidebar */}
      <div className="hidden md:block shrink-0">
        {sidebarContent}
      </div>
    </>
  );
}
```

- [ ] **Step 3: Create command menu**

Create `web/components/command-menu.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { useApps, useSkills } from "@/lib/hooks";

export function CommandMenu({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const router = useRouter();
  const { data: apps } = useApps();
  const { data: skills } = useSkills();
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!open) setSearch("");
  }, [open]);

  const go = (path: string) => {
    onOpenChange(false);
    router.push(path);
  };

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput placeholder="Search apps and skills..." value={search} onValueChange={setSearch} />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>

        <CommandGroup heading="Pages">
          <CommandItem onSelect={() => go("/")}>Apps</CommandItem>
          <CommandItem onSelect={() => go("/skills")}>Skills</CommandItem>
          <CommandItem onSelect={() => go("/my-forge")}>My Forge</CommandItem>
          <CommandItem onSelect={() => go("/publish")}>Publish</CommandItem>
        </CommandGroup>

        {(apps || []).length > 0 && (
          <CommandGroup heading="Apps">
            {(apps || []).filter(a => !search || a.name.toLowerCase().includes(search.toLowerCase())).slice(0, 8).map(app => (
              <CommandItem key={app.id} onSelect={() => go(`/apps/${app.slug}`)}>
                <span className="mr-2">{app.icon || "⊞"}</span>
                {app.name}
                {app.tagline && <span className="ml-2 text-muted-foreground text-xs truncate">{app.tagline}</span>}
              </CommandItem>
            ))}
          </CommandGroup>
        )}

        {(skills || []).length > 0 && (
          <CommandGroup heading="Skills">
            {(skills || []).filter(s => !search || s.title.toLowerCase().includes(search.toLowerCase())).slice(0, 8).map(skill => (
              <CommandItem key={skill.id} onSelect={() => go("/skills")}>
                <span className="mr-2">📄</span>
                {skill.title}
              </CommandItem>
            ))}
          </CommandGroup>
        )}
      </CommandList>
    </CommandDialog>
  );
}
```

- [ ] **Step 4: Create keyboard shortcuts handler**

Create `web/components/keyboard-shortcuts.tsx`:

```tsx
"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

export function KeyboardShortcuts({ onOpenCommandMenu }: { onOpenCommandMenu: () => void }) {
  const router = useRouter();
  const gPending = useRef(false);
  const gTimer = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      const isTyping = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (e.target as HTMLElement)?.isContentEditable;

      // Cmd/Ctrl+K — command palette
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        onOpenCommandMenu();
        return;
      }

      // Escape is handled by shadcn dialogs
      if (isTyping) return;

      // / — focus search
      if (e.key === "/") {
        e.preventDefault();
        onOpenCommandMenu();
        return;
      }

      // g-prefix chords
      if (e.key === "g" && !gPending.current) {
        gPending.current = true;
        clearTimeout(gTimer.current);
        gTimer.current = setTimeout(() => { gPending.current = false; }, 900);
        return;
      }

      if (gPending.current) {
        gPending.current = false;
        clearTimeout(gTimer.current);
        if (e.key === "c") router.push("/");
        else if (e.key === "s" || e.key === "k") router.push("/skills");
        else if (e.key === "m") router.push("/my-forge");
      }
    };

    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onOpenCommandMenu, router]);

  return null;
}
```

- [ ] **Step 5: Update root layout to use sidebar, providers, command menu**

Replace `web/app/layout.tsx`:

```tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import localFont from "next/font/local";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
});

const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-mono",
  weight: "100 900",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Forge",
  description: "Internal AI tool marketplace",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} ${geistMono.variable} font-sans antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

- [ ] **Step 6: Create providers wrapper (client component)**

Create `web/app/providers.tsx`:

```tsx
"use client";

import { useState } from "react";
import { UserProvider } from "@/lib/user-context";
import { Sidebar } from "@/components/sidebar";
import { CommandMenu } from "@/components/command-menu";
import { KeyboardShortcuts } from "@/components/keyboard-shortcuts";
import { ToasterProvider } from "@/components/toaster-provider";

export function Providers({ children }: { children: React.ReactNode }) {
  const [commandOpen, setCommandOpen] = useState(false);

  return (
    <UserProvider>
      <div className="flex h-screen overflow-hidden">
        <Sidebar onOpenCommandMenu={() => setCommandOpen(true)} />
        <main className="flex-1 overflow-y-auto pt-12 md:pt-0">
          {children}
        </main>
      </div>
      <CommandMenu open={commandOpen} onOpenChange={setCommandOpen} />
      <KeyboardShortcuts onOpenCommandMenu={() => setCommandOpen(true)} />
      <ToasterProvider />
    </UserProvider>
  );
}
```

- [ ] **Step 7: Verify sidebar renders**

```bash
cd /Users/nicholasruzicka/projects/forge/web
npm run dev
```

Open http://localhost:3000 — should show dark sidebar on left with logo, search trigger, nav items. Content area shows "Forge".

- [ ] **Step 8: Commit**

```bash
cd /Users/nicholasruzicka/projects/forge
git add web/
git commit -m "feat: add sidebar, command menu, keyboard shortcuts, and providers"
```

---

## Task 5: Shared Components

**Files:**
- Create: `web/components/app-card.tsx`
- Create: `web/components/star-button.tsx`
- Create: `web/components/install-button.tsx`
- Create: `web/components/category-pills.tsx`
- Create: `web/components/empty-state.tsx`
- Create: `web/components/app-embed.tsx`
- Create: `web/components/role-picker.tsx`

- [ ] **Step 1: Create star button**

Create `web/components/star-button.tsx`:

```tsx
"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Star } from "lucide-react";
import { toggleStar } from "@/lib/hooks";
import { trackMilestone } from "@/lib/milestones";
import { cn } from "@/lib/utils";

export function StarButton({ toolId, isStarred, size = "sm" }: { toolId: number; isStarred: boolean; size?: "sm" | "icon" }) {
  const [starred, setStarred] = useState(isStarred);
  const [loading, setLoading] = useState(false);

  const handleClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    setLoading(true);
    const prev = starred;
    setStarred(!prev);
    try {
      await toggleStar(toolId, prev);
      if (!prev) {
        const msg = trackMilestone("first_star");
        if (msg) toast.success(msg);
      }
    } catch {
      setStarred(prev);
      toast.error("Failed to update star");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Button
      variant="ghost"
      size={size}
      onClick={handleClick}
      disabled={loading}
      className={cn("text-muted-foreground hover:text-foreground", starred && "text-yellow-400 hover:text-yellow-300")}
    >
      <Star className={cn("h-4 w-4", starred && "fill-current")} />
    </Button>
  );
}
```

- [ ] **Step 2: Create install button**

Create `web/components/install-button.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Check, Download, ExternalLink } from "lucide-react";
import { installApp } from "@/lib/hooks";
import { trackMilestone } from "@/lib/milestones";

export function InstallButton({
  toolId,
  slug,
  isInstalled,
  delivery,
}: {
  toolId: number;
  slug: string;
  isInstalled: boolean;
  delivery?: string;
}) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const isExternal = delivery === "external";

  if (isInstalled) {
    return (
      <Button size="sm" variant="ghost" className="text-[hsl(var(--success))]" onClick={(e) => { e.stopPropagation(); router.push(`/apps/${slug}`); }}>
        <Check className="h-4 w-4 mr-1" />
        Open
      </Button>
    );
  }

  const handleInstall = async (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    setLoading(true);
    try {
      await installApp(toolId);
      const msg = trackMilestone("first_install");
      toast.success(msg || "Installed");
    } catch {
      toast.error("Install failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Button size="sm" onClick={handleInstall} disabled={loading}>
      {isExternal ? <Download className="h-4 w-4 mr-1" /> : <ExternalLink className="h-4 w-4 mr-1" />}
      {loading ? "..." : isExternal ? "Install" : "Open"}
    </Button>
  );
}
```

- [ ] **Step 3: Create app card**

Create `web/components/app-card.tsx`:

```tsx
"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { StarButton } from "./star-button";
import { InstallButton } from "./install-button";
import type { App } from "@/lib/types";

export function AppCard({
  app,
  isStarred,
  isInstalled,
}: {
  app: App;
  isStarred: boolean;
  isInstalled: boolean;
}) {
  return (
    <Link
      href={`/apps/${app.slug}`}
      className="block border border-border rounded-md bg-[hsl(var(--card))] p-4 hover:border-[hsl(var(--border-strong))] transition-colors group"
    >
      <div className="flex items-start justify-between mb-2">
        <span className="text-2xl">{app.icon || "⊞"}</span>
        <StarButton toolId={app.id} isStarred={isStarred} size="icon" />
      </div>

      <h3 className="font-medium text-sm text-foreground mb-0.5 group-hover:text-[hsl(var(--primary))] transition-colors">
        {app.name}
      </h3>
      <p className="text-xs text-muted-foreground line-clamp-1 mb-3">
        {app.tagline}
      </p>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>{app.author_name || "Unknown"}</span>
          {(app.install_count ?? 0) > 0 && (
            <span>· {app.install_count} installs</span>
          )}
        </div>
        <InstallButton toolId={app.id} slug={app.slug} isInstalled={isInstalled} delivery={app.delivery} />
      </div>
    </Link>
  );
}
```

- [ ] **Step 4: Create category pills**

Create `web/components/category-pills.tsx`:

```tsx
"use client";

import { cn } from "@/lib/utils";

export function CategoryPills({
  categories,
  active,
  onSelect,
}: {
  categories: string[];
  active: string | null;
  onSelect: (cat: string | null) => void;
}) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none">
      <button
        onClick={() => onSelect(null)}
        className={cn(
          "px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-colors border",
          active === null
            ? "bg-[hsl(var(--primary)/0.08)] text-[hsl(var(--primary))] border-[hsl(var(--primary)/0.2)]"
            : "bg-transparent text-muted-foreground border-border hover:border-[hsl(var(--border-strong))] hover:text-foreground"
        )}
      >
        All
      </button>
      {categories.map(cat => (
        <button
          key={cat}
          onClick={() => onSelect(cat)}
          className={cn(
            "px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-colors border",
            active === cat
              ? "bg-[hsl(var(--primary)/0.08)] text-[hsl(var(--primary))] border-[hsl(var(--primary)/0.2)]"
              : "bg-transparent text-muted-foreground border-border hover:border-[hsl(var(--border-strong))] hover:text-foreground"
          )}
        >
          {cat}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 5: Create empty state**

Create `web/components/empty-state.tsx`:

```tsx
import Link from "next/link";
import { Button } from "@/components/ui/button";

export function EmptyState({
  icon,
  title,
  message,
  actionLabel,
  actionHref,
  onAction,
}: {
  icon?: string;
  title: string;
  message: string;
  actionLabel?: string;
  actionHref?: string;
  onAction?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      {icon && <div className="text-4xl mb-4">{icon}</div>}
      <h3 className="text-lg font-medium text-foreground mb-1">{title}</h3>
      <p className="text-sm text-muted-foreground max-w-sm mb-4">{message}</p>
      {actionLabel && actionHref && (
        <Button asChild>
          <Link href={actionHref}>{actionLabel}</Link>
        </Button>
      )}
      {actionLabel && onAction && (
        <Button onClick={onAction}>{actionLabel}</Button>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Create app embed (sandboxed iframe)**

Create `web/components/app-embed.tsx`:

```tsx
"use client";

export function AppEmbed({ slug, className }: { slug: string; className?: string }) {
  const src = `/apps/${encodeURIComponent(slug)}`;

  return (
    <iframe
      src={src}
      title={slug}
      sandbox="allow-scripts allow-forms allow-modals allow-downloads"
      referrerPolicy="no-referrer"
      loading="eager"
      className={className || "w-full h-[600px] border border-border rounded-md bg-black"}
    />
  );
}
```

- [ ] **Step 7: Create role picker modal**

Create `web/components/role-picker.tsx`:

```tsx
"use client";

import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useUser } from "@/lib/user-context";

const ROLES = ["AE", "SDR", "RevOps", "CS", "Product", "Eng", "Recruiter", "Other"];

export function RolePicker({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const { setRole } = useUser();

  const handlePick = (role: string) => {
    setRole(role);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Welcome to Forge</DialogTitle>
          <p className="text-sm text-muted-foreground">What's your role? This helps us show relevant apps first.</p>
        </DialogHeader>
        <div className="grid grid-cols-4 gap-2 mt-4">
          {ROLES.map(role => (
            <button
              key={role}
              onClick={() => handlePick(role)}
              className="px-3 py-3 rounded-md border border-border text-sm font-medium text-foreground hover:bg-[hsl(var(--surface-2))] hover:border-[hsl(var(--border-strong))] transition-colors"
            >
              {role}
            </button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 8: Commit**

```bash
cd /Users/nicholasruzicka/projects/forge
git add web/components/
git commit -m "feat: add shared components — cards, star, install, pills, empty state, embed, role picker"
```

---

## Task 6: Catalog Page

**Files:**
- Modify: `web/app/page.tsx`

- [ ] **Step 1: Build the catalog page**

Replace `web/app/page.tsx`:

```tsx
"use client";

import { useState, useMemo, useEffect } from "react";
import { useApps, useMyItems, useMyStars } from "@/lib/hooks";
import { useUser } from "@/lib/user-context";
import { AppCard } from "@/components/app-card";
import { CategoryPills } from "@/components/category-pills";
import { EmptyState } from "@/components/empty-state";
import { RolePicker } from "@/components/role-picker";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Search } from "lucide-react";

export default function CatalogPage() {
  const { role } = useUser();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [showRolePicker, setShowRolePicker] = useState(false);
  const [debouncedSearch, setDebouncedSearch] = useState("");

  // Debounce search
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  // Show role picker on first visit
  useEffect(() => {
    if (!role) setShowRolePicker(true);
  }, [role]);

  const filters = useMemo(() => {
    const f: Record<string, string> = { sort: "most_used", limit: "50" };
    if (debouncedSearch) f.search = debouncedSearch;
    if (category) f.category = category;
    return f;
  }, [debouncedSearch, category]);

  const { data: apps, isLoading } = useApps(filters);
  const { data: myItems } = useMyItems();
  const { data: myStars } = useMyStars();

  const installedIds = new Set((myItems || []).map(i => i.tool_id));
  const starredIds = new Set((myStars || []).map(s => s.tool_id));
  const categories = useMemo(() => [...new Set((apps || []).map(a => a.category).filter(Boolean) as string[])].sort(), [apps]);

  // Role-aware sort
  const sortedApps = useMemo(() => {
    if (!apps) return [];
    if (!role) return apps;
    return [...apps].sort((a, b) => {
      const aMatch = matchesRole(a, role);
      const bMatch = matchesRole(b, role);
      if (aMatch && !bMatch) return -1;
      if (!aMatch && bMatch) return 1;
      return (b.install_count || 0) - (a.install_count || 0);
    });
  }, [apps, role]);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold mb-1">Apps</h1>
        <p className="text-sm text-muted-foreground">Browse and install tools built by your team.</p>
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search apps..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="pl-9 bg-[hsl(var(--surface))]"
        />
      </div>

      {/* Category pills */}
      <div className="mb-6">
        <CategoryPills categories={categories} active={category} onSelect={setCategory} />
      </div>

      {/* Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-[160px] rounded-md" />
          ))}
        </div>
      ) : sortedApps.length === 0 ? (
        <EmptyState icon="⚒" title="No apps match" message="Try different filters, or publish the first app in this category." actionLabel="Publish" actionHref="/publish" />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {sortedApps.map(app => (
            <AppCard
              key={app.id}
              app={app}
              isStarred={starredIds.has(app.id)}
              isInstalled={installedIds.has(app.id)}
            />
          ))}
        </div>
      )}

      <RolePicker open={showRolePicker} onOpenChange={setShowRolePicker} />
    </div>
  );
}

function matchesRole(app: { role_tags?: string | string[] }, role: string): boolean {
  try {
    const tags = typeof app.role_tags === "string" ? JSON.parse(app.role_tags) : (app.role_tags || []);
    return tags.includes(role);
  } catch { return false; }
}
```

- [ ] **Step 2: Verify catalog renders with Flask running**

Start Flask on port 8090, then open http://localhost:3000. Should show the app grid with cards, search, and category filters. If Flask isn't running, cards will show loading skeletons.

- [ ] **Step 3: Commit**

```bash
cd /Users/nicholasruzicka/projects/forge
git add web/app/page.tsx
git commit -m "feat: implement catalog page with search, filters, and role picker"
```

---

## Task 7: App Detail Page

**Files:**
- Create: `web/app/apps/[slug]/page.tsx`
- Create: `web/components/review-form.tsx`
- Create: `web/components/review-card.tsx`
- Create: `web/components/install-progress.tsx`

- [ ] **Step 1: Create review card**

Create `web/components/review-card.tsx`:

```tsx
import type { Review } from "@/lib/types";
import { Star } from "lucide-react";

export function ReviewCard({ review }: { review: Review }) {
  return (
    <div className="border border-border rounded-md p-4">
      <div className="flex items-center gap-2 mb-2">
        <div className="flex">
          {Array.from({ length: 5 }).map((_, i) => (
            <Star key={i} className={`h-3.5 w-3.5 ${i < review.rating ? "fill-yellow-400 text-yellow-400" : "text-muted-foreground"}`} />
          ))}
        </div>
        <span className="text-xs text-muted-foreground">{review.user_name || "Anonymous"}</span>
        {review.created_at && <span className="text-xs text-muted-foreground">· {new Date(review.created_at).toLocaleDateString()}</span>}
      </div>
      {review.text && <p className="text-sm text-foreground">{review.text}</p>}
    </div>
  );
}
```

- [ ] **Step 2: Create review form**

Create `web/components/review-form.tsx`:

```tsx
"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Star } from "lucide-react";
import * as api from "@/lib/api";
import { cn } from "@/lib/utils";

export function ReviewForm({ toolId, onSubmitted }: { toolId: number; onSubmitted: () => void }) {
  const [rating, setRating] = useState(0);
  const [hover, setHover] = useState(0);
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (rating === 0) { toast.error("Pick a rating"); return; }
    setLoading(true);
    try {
      await api.postReview(toolId, rating, text);
      toast.success("Review submitted");
      setRating(0); setText("");
      onSubmitted();
    } catch { toast.error("Failed to submit review"); }
    finally { setLoading(false); }
  };

  return (
    <div className="space-y-3">
      <div className="flex gap-1">
        {Array.from({ length: 5 }).map((_, i) => (
          <button
            key={i}
            onMouseEnter={() => setHover(i + 1)}
            onMouseLeave={() => setHover(0)}
            onClick={() => setRating(i + 1)}
            className="p-0.5"
          >
            <Star className={cn("h-5 w-5 transition-colors", (hover || rating) > i ? "fill-yellow-400 text-yellow-400" : "text-muted-foreground")} />
          </button>
        ))}
      </div>
      <Textarea placeholder="Write a review..." value={text} onChange={e => setText(e.target.value)} className="bg-[hsl(var(--surface))] min-h-[80px]" />
      <Button onClick={handleSubmit} disabled={loading} size="sm">
        {loading ? "Submitting..." : "Submit Review"}
      </Button>
    </div>
  );
}
```

- [ ] **Step 3: Create install progress component**

Create `web/components/install-progress.tsx`:

```tsx
"use client";

import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export function InstallProgress({
  installCommand,
  agentAvailable,
  status,
}: {
  installCommand?: string;
  agentAvailable: boolean;
  status?: string;
}) {
  if (agentAvailable && status) {
    return (
      <div className="border border-border rounded-md p-4 space-y-2">
        <div className="flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin text-[hsl(var(--primary))]" />
          <span className="text-sm font-medium">{status}</span>
        </div>
        <div className="h-1.5 bg-[hsl(var(--surface-2))] rounded-full overflow-hidden">
          <div className="h-full bg-[hsl(var(--primary))] rounded-full animate-pulse w-2/3" />
        </div>
      </div>
    );
  }

  if (installCommand) {
    return (
      <div className="border border-border rounded-md p-4 space-y-2">
        <p className="text-xs text-muted-foreground">Forge agent not available. Install manually:</p>
        <div className="flex items-center gap-2">
          <code className="flex-1 text-xs font-mono bg-[hsl(var(--surface))] p-2 rounded border border-border overflow-x-auto">
            {installCommand}
          </code>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              navigator.clipboard.writeText(installCommand);
              toast.success("Copied");
            }}
          >
            Copy
          </Button>
        </div>
      </div>
    );
  }

  return null;
}
```

- [ ] **Step 4: Create app detail page**

Create `web/app/apps/[slug]/page.tsx`:

```tsx
"use client";

import { use } from "react";
import Link from "next/link";
import { useApp, useMyItems, useMyStars, useReviews, useAgentRunning } from "@/lib/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { StarButton } from "@/components/star-button";
import { InstallButton } from "@/components/install-button";
import { AppEmbed } from "@/components/app-embed";
import { InstallProgress } from "@/components/install-progress";
import { ReviewForm } from "@/components/review-form";
import { ReviewCard } from "@/components/review-card";
import { EmptyState } from "@/components/empty-state";

export default function AppDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const { data: app, isLoading } = useApp(slug);
  const { data: myItems } = useMyItems();
  const { data: myStars } = useMyStars();
  const { data: reviews, mutate: mutateReviews } = useReviews(app?.id ?? null);
  const isExternal = app?.delivery === "external";
  const { data: agentStatus } = useAgentRunning(isExternal);

  if (isLoading) {
    return (
      <div className="p-6 max-w-4xl mx-auto space-y-4">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-[400px]" />
      </div>
    );
  }

  if (!app) {
    return <EmptyState icon="⚠" title="App not found" message="This app doesn't exist or has been removed." actionLabel="Back to Apps" actionHref="/" />;
  }

  const isInstalled = (myItems || []).some(i => i.tool_id === app.id);
  const isStarred = (myStars || []).some(s => s.tool_id === app.id);

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Back link */}
      <Link href="/" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4">
        <ArrowLeft className="h-4 w-4" /> Apps
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div className="flex items-start gap-4">
          <span className="text-4xl">{app.icon || "⊞"}</span>
          <div>
            <h1 className="text-2xl font-semibold">{app.name}</h1>
            <p className="text-sm text-muted-foreground mt-0.5">{app.tagline}</p>
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              <span className="text-xs text-muted-foreground">{app.author_name || "Unknown"}</span>
              {app.category && <Badge variant="secondary">{app.category}</Badge>}
              {(app.install_count ?? 0) > 0 && <span className="text-xs text-muted-foreground">{app.install_count} installs</span>}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <StarButton toolId={app.id} isStarred={isStarred} />
          <InstallButton toolId={app.id} slug={app.slug} isInstalled={isInstalled} delivery={app.delivery} />
          {app.source_url && (
            <Button variant="ghost" size="sm" asChild>
              <a href={app.source_url} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="h-4 w-4 mr-1" /> Source
              </a>
            </Button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="open">Open App</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6 mt-4">
          {/* Description */}
          {app.description && (
            <div className="prose prose-invert prose-sm max-w-none">
              <p className="text-sm text-foreground whitespace-pre-wrap">{app.description}</p>
            </div>
          )}

          {/* Install progress for external */}
          {isExternal && !isInstalled && (
            <InstallProgress
              installCommand={app.install_command}
              agentAvailable={agentStatus?.running || false}
            />
          )}

          {/* Reviews */}
          <div>
            <h2 className="text-sm font-medium mb-3">Reviews</h2>
            <ReviewForm toolId={app.id} onSubmitted={() => mutateReviews()} />
            <div className="space-y-3 mt-4">
              {(reviews || []).length === 0 ? (
                <p className="text-xs text-muted-foreground">No reviews yet. Be the first!</p>
              ) : (
                (reviews || []).map(review => <ReviewCard key={review.id} review={review} />)
              )}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="open" className="mt-4">
          {!isInstalled && (
            <div className="mb-4 p-3 rounded-md border border-[hsl(var(--primary)/0.3)] bg-[hsl(var(--primary)/0.05)] flex items-center justify-between">
              <span className="text-sm">Sample data — install to make this yours</span>
              <InstallButton toolId={app.id} slug={app.slug} isInstalled={false} delivery={app.delivery} />
            </div>
          )}
          <AppEmbed slug={slug} className="w-full h-[calc(100vh-250px)] border border-border rounded-md bg-black" />
        </TabsContent>
      </Tabs>
    </div>
  );
}
```

- [ ] **Step 5: Commit**

```bash
cd /Users/nicholasruzicka/projects/forge
git add web/app/apps/ web/components/review-card.tsx web/components/review-form.tsx web/components/install-progress.tsx
git commit -m "feat: implement app detail page with overview, embed, and reviews"
```

---

## Task 8: Skills Page

**Files:**
- Create: `web/app/skills/page.tsx`
- Create: `web/components/skill-card.tsx`
- Create: `web/components/submit-skill-dialog.tsx`

- [ ] **Step 1: Create skill card**

Create `web/components/skill-card.tsx`:

```tsx
"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronRight, Download, ArrowUp, Copy } from "lucide-react";
import * as api from "@/lib/api";
import type { Skill } from "@/lib/types";
import { cn } from "@/lib/utils";

export function SkillCard({ skill }: { skill: Skill }) {
  const [upvoted, setUpvoted] = useState(false);
  const [upvotes, setUpvotes] = useState(skill.upvotes);
  const [subscribed, setSubscribed] = useState(false);
  const [installOpen, setInstallOpen] = useState(false);

  const slug = (skill.title || "skill").toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "") || "skill";
  const downloadUrl = `${typeof window !== "undefined" ? window.location.origin : ""}${api.downloadSkillUrl(skill.id)}`;
  const cmd = `mkdir -p ~/.claude/skills/${slug} && curl -L -o ~/.claude/skills/${slug}/SKILL.md ${downloadUrl}`;

  const handleUpvote = async () => {
    if (upvoted) { toast.info("Already upvoted"); return; }
    setUpvoted(true);
    setUpvotes(u => u + 1);
    try { await api.upvoteSkill(skill.id); }
    catch { setUpvoted(false); setUpvotes(u => u - 1); toast.error("Upvote failed"); }
  };

  const handleSubscribe = async () => {
    setSubscribed(true);
    try {
      await api.subscribeSkill(skill.id);
      toast.success(`Subscribed to "${skill.title}". Run "forge sync" to install.`);
    } catch { setSubscribed(false); toast.error("Subscribe failed"); }
  };

  const handleCopyCmd = () => {
    navigator.clipboard.writeText(cmd);
    toast.success("Install command copied");
  };

  return (
    <div className="border border-border rounded-md bg-[hsl(var(--card))] p-4 space-y-3">
      <div className="flex items-center justify-between">
        {skill.category && <Badge variant="secondary">{skill.category}</Badge>}
        {skill.copy_count > 0 && <span className="text-xs text-muted-foreground">{skill.copy_count} downloads</span>}
      </div>

      <h3 className="font-medium text-sm">{skill.title}</h3>
      <p className="text-xs text-muted-foreground line-clamp-2">{skill.use_case || skill.description}</p>

      <div className="text-xs font-mono text-muted-foreground bg-[hsl(var(--surface))] p-2 rounded border border-border line-clamp-4 whitespace-pre-wrap">
        {(skill.prompt_text || "").slice(0, 300)}
      </div>

      {/* Install disclosure */}
      <div>
        <button onClick={() => setInstallOpen(!installOpen)} className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors">
          <ChevronRight className={cn("h-3 w-3 transition-transform", installOpen && "rotate-90")} />
          Install with curl
          <Button size="sm" variant="ghost" className="h-6 ml-2 text-xs" onClick={e => { e.stopPropagation(); handleCopyCmd(); }}>
            <Copy className="h-3 w-3 mr-1" /> Copy
          </Button>
        </button>
        {installOpen && (
          <code className="block mt-2 text-[11px] font-mono text-muted-foreground bg-[hsl(var(--surface))] p-2 rounded border border-border overflow-x-auto whitespace-nowrap">
            {cmd}
          </code>
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-1">
        <div className="flex items-center gap-2">
          <Button size="sm" variant="ghost" className={cn("h-7 text-xs", upvoted && "text-[hsl(var(--primary))]")} onClick={handleUpvote}>
            <ArrowUp className="h-3.5 w-3.5 mr-0.5" /> {upvotes}
          </Button>
          {skill.source_url ? (
            <a href={skill.source_url} target="_blank" rel="noopener" className="text-xs text-[hsl(var(--primary))] hover:underline">@{skill.author_name || "source"}</a>
          ) : (
            <span className="text-xs text-muted-foreground">by {skill.author_name || "Anonymous"}</span>
          )}
        </div>
        <div className="flex gap-1.5">
          <Button size="sm" variant="outline" className="h-7 text-xs" onClick={handleSubscribe} disabled={subscribed}>
            {subscribed ? "✓ Subscribed" : "+ Subscribe"}
          </Button>
          <Button size="sm" className="h-7 text-xs" asChild>
            <a href={api.downloadSkillUrl(skill.id)} download><Download className="h-3 w-3 mr-1" /> .md</a>
          </Button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create submit skill dialog**

Create `web/components/submit-skill-dialog.tsx`:

```tsx
"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import * as api from "@/lib/api";
import { useUser } from "@/lib/user-context";

const CATEGORIES = ["Development", "Testing", "Debugging", "Planning", "Code Review", "Documents", "Other"];

export function SubmitSkillDialog({ open, onOpenChange, onSubmitted }: { open: boolean; onOpenChange: (open: boolean) => void; onSubmitted: () => void }) {
  const { name } = useUser();
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({ title: "", use_case: "", category: "Development", prompt_text: "", source_url: "", author_name: name });

  const set = (key: string, value: string) => setForm(f => ({ ...f, [key]: value }));

  const handleSubmit = async () => {
    if (!form.title || !form.use_case || !form.prompt_text) { toast.error("Fill in required fields"); return; }
    setLoading(true);
    try {
      await api.submitSkill(form);
      toast.success("Skill submitted");
      onOpenChange(false);
      onSubmitted();
    } catch { toast.error("Submit failed"); }
    finally { setLoading(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Submit a Skill</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 mt-2">
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">Title *</label>
            <Input value={form.title} onChange={e => set("title", e.target.value)} maxLength={100} placeholder="e.g. Discovery call follow-up template" />
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">Use this when you want to... *</label>
            <Input value={form.use_case} onChange={e => set("use_case", e.target.value)} maxLength={160} placeholder="send a recap after a discovery call" />
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">Category</label>
            <Select value={form.category} onValueChange={v => set("category", v)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{CATEGORIES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">SKILL.md contents *</label>
            <Textarea value={form.prompt_text} onChange={e => set("prompt_text", e.target.value)} className="font-mono text-xs min-h-[160px]" placeholder={"---\nname: my-skill\ndescription: Use when ...\n---\n\nBody..."} />
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">GitHub URL</label>
            <Input value={form.source_url} onChange={e => set("source_url", e.target.value)} placeholder="https://github.com/you/skills/tree/main/my-skill" />
          </div>
          <div>
            <label className="text-xs text-muted-foreground mb-1 block">GitHub handle</label>
            <Input value={form.author_name} onChange={e => set("author_name", e.target.value)} placeholder="e.g. obra" />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button onClick={handleSubmit} disabled={loading}>{loading ? "Submitting..." : "Submit Skill"}</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 3: Create skills page**

Create `web/app/skills/page.tsx`:

```tsx
"use client";

import { useState, useMemo, useEffect } from "react";
import { useSkills } from "@/lib/hooks";
import { SkillCard } from "@/components/skill-card";
import { CategoryPills } from "@/components/category-pills";
import { EmptyState } from "@/components/empty-state";
import { SubmitSkillDialog } from "@/components/submit-skill-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search, Plus } from "lucide-react";

const CATEGORIES = ["Development", "Testing", "Debugging", "Planning", "Code Review", "Documents", "Other"];

export default function SkillsPage() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [sort, setSort] = useState("upvotes");
  const [submitOpen, setSubmitOpen] = useState(false);
  const [debouncedSearch, setDebouncedSearch] = useState("");

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  const filters = useMemo(() => {
    const f: Record<string, string> = { sort };
    if (debouncedSearch) f.search = debouncedSearch;
    if (category) f.category = category;
    return f;
  }, [debouncedSearch, category, sort]);

  const { data: skills, isLoading, mutate } = useSkills(filters);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold mb-1">Skills</h1>
          <p className="text-sm text-muted-foreground">Real SKILL.md files for Claude Code. Download and drop into <code className="font-mono text-xs">~/.claude/skills/</code>.</p>
        </div>
        <Button onClick={() => setSubmitOpen(true)}><Plus className="h-4 w-4 mr-1" /> Submit a Skill</Button>
      </div>

      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input placeholder="Search skills..." value={search} onChange={e => setSearch(e.target.value)} className="pl-9 bg-[hsl(var(--surface))]" />
      </div>

      <div className="flex items-center justify-between mb-6">
        <CategoryPills categories={CATEGORIES} active={category} onSelect={setCategory} />
        <Select value={sort} onValueChange={setSort}>
          <SelectTrigger className="w-[160px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="upvotes">Most Upvoted</SelectItem>
            <SelectItem value="newest">Newest</SelectItem>
            <SelectItem value="copies">Most Downloaded</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-[280px] rounded-md" />)}
        </div>
      ) : (skills || []).length === 0 ? (
        <EmptyState icon="✨" title="No skills yet" message="Be the first to share a prompt template." actionLabel="+ Submit a Skill" onAction={() => setSubmitOpen(true)} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {(skills || []).map(skill => <SkillCard key={skill.id} skill={skill} />)}
        </div>
      )}

      <SubmitSkillDialog open={submitOpen} onOpenChange={setSubmitOpen} onSubmitted={() => mutate()} />
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
cd /Users/nicholasruzicka/projects/forge
git add web/app/skills/ web/components/skill-card.tsx web/components/submit-skill-dialog.tsx
git commit -m "feat: implement skills page with search, filter, upvote, subscribe, and submit"
```

---

## Task 9: My Forge Page

**Files:**
- Create: `web/app/my-forge/page.tsx`
- Create: `web/components/app-pane.tsx`

- [ ] **Step 1: Create app pane (inline app viewer)**

Create `web/components/app-pane.tsx`:

```tsx
"use client";

import { Button } from "@/components/ui/button";
import { AppEmbed } from "./app-embed";
import { X, ExternalLink } from "lucide-react";

export function AppPane({ slug, name, onClose }: { slug: string; name: string; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex flex-col">
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-[hsl(var(--surface))]">
        <span className="text-sm font-medium">{name}</span>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" asChild>
            <a href={`/apps/${slug}`} target="_blank" rel="noopener"><ExternalLink className="h-4 w-4 mr-1" /> Full screen</a>
          </Button>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <div className="flex-1">
        <AppEmbed slug={slug} className="w-full h-full border-0" />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create My Forge page**

Create `web/app/my-forge/page.tsx`:

```tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useMyItems, useMyStars, useMySkills, useAgentRunning, uninstallApp } from "@/lib/hooks";
import * as api from "@/lib/api";
import { useUser } from "@/lib/user-context";
import { EmptyState } from "@/components/empty-state";
import { AppPane } from "@/components/app-pane";
import { Skeleton } from "@/components/ui/skeleton";

export default function MyForgePage() {
  const { name, email, clearIdentity, setIdentity } = useUser();
  const { data: items, isLoading: itemsLoading, mutate: mutateItems } = useMyItems();
  const { data: stars, isLoading: starsLoading } = useMyStars();
  const { data: skills, isLoading: skillsLoading } = useMySkills();
  const { data: agentStatus } = useAgentRunning(true);
  const [openApp, setOpenApp] = useState<{ slug: string; name: string } | null>(null);

  const handleRemove = async (toolId: number) => {
    try { await uninstallApp(toolId); toast.success("Removed"); mutateItems(); }
    catch { toast.error("Remove failed"); }
  };

  const handleUnsave = async (toolId: number) => {
    try { await api.removeStar(toolId); toast.success("Unsaved"); }
    catch { toast.error("Unsave failed"); }
  };

  const handleOpen = (item: { slug?: string; name?: string; tool_id: number; delivery?: string }) => {
    if (item.delivery === "external") {
      api.launchItem(item.tool_id).catch(() => {});
    } else {
      setOpenApp({ slug: item.slug || String(item.tool_id), name: item.name || "App" });
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold mb-1">My Forge</h1>
          <p className="text-sm text-muted-foreground">Your installed apps, saved items, and skills.</p>
        </div>
        <div className="text-xs text-muted-foreground">
          {name || email ? (
            <>{name || email} · <button onClick={clearIdentity} className="hover:text-foreground">sign out</button></>
          ) : (
            <button onClick={() => {
              const n = prompt("Name:");
              const e = prompt("Email:");
              if (n && e) setIdentity(n, e);
            }} className="hover:text-foreground">set email</button>
          )}
        </div>
      </div>

      <Tabs defaultValue="installed">
        <TabsList>
          <TabsTrigger value="installed">Installed {items && <Badge variant="secondary" className="ml-1.5 h-5 text-[10px]">{items.length}</Badge>}</TabsTrigger>
          <TabsTrigger value="saved">Saved {stars && <Badge variant="secondary" className="ml-1.5 h-5 text-[10px]">{stars.length}</Badge>}</TabsTrigger>
          <TabsTrigger value="skills">Skills {skills && <Badge variant="secondary" className="ml-1.5 h-5 text-[10px]">{skills.length}</Badge>}</TabsTrigger>
        </TabsList>

        <TabsContent value="installed" className="mt-4">
          {itemsLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-[120px] rounded-md" />)}
            </div>
          ) : (items || []).length === 0 ? (
            <EmptyState icon="⊞" title="Nothing installed yet" message="Browse the catalog and install apps you want to use." actionLabel="Browse apps" actionHref="/" />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {(items || []).map(item => (
                <div key={item.id} className="border border-border rounded-md bg-[hsl(var(--card))] p-4 group">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xl">{item.icon || "⊞"}</span>
                      <div>
                        <Link href={`/apps/${item.slug || item.tool_id}`} className="text-sm font-medium hover:text-[hsl(var(--primary))]">{item.name}</Link>
                        <p className="text-xs text-muted-foreground">{item.tagline}</p>
                      </div>
                    </div>
                    {item.delivery === "external" && <Badge variant="outline" className="text-[10px]">External</Badge>}
                  </div>
                  <div className="flex items-center justify-between mt-3">
                    <span className="text-xs text-muted-foreground">{item.open_count || 0} opens</span>
                    <div className="flex gap-1.5">
                      <Button size="sm" variant="default" className="h-7 text-xs" onClick={() => handleOpen(item)}>
                        {item.delivery === "external" ? "Launch" : "Open"}
                      </Button>
                      <Button size="sm" variant="ghost" className="h-7 text-xs text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity" onClick={() => handleRemove(item.tool_id)}>
                        Remove
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="saved" className="mt-4">
          {starsLoading ? (
            <Skeleton className="h-[120px] rounded-md" />
          ) : (stars || []).length === 0 ? (
            <EmptyState icon="☆" title="No saved apps" message="Star apps in the catalog to save them for later." actionLabel="Browse apps" actionHref="/" />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {(stars || []).map(star => (
                <div key={star.id} className="border border-border rounded-md bg-[hsl(var(--card))] p-4 group">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xl">{star.icon || "⊞"}</span>
                    <div>
                      <Link href={`/apps/${star.slug || star.tool_id}`} className="text-sm font-medium hover:text-[hsl(var(--primary))]">{star.name}</Link>
                      <p className="text-xs text-muted-foreground">{star.tagline}</p>
                    </div>
                  </div>
                  <div className="flex justify-end">
                    <Button size="sm" variant="ghost" className="h-7 text-xs text-muted-foreground hover:text-destructive" onClick={() => handleUnsave(star.tool_id)}>
                      Unsave
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="skills" className="mt-4">
          {skillsLoading ? (
            <Skeleton className="h-[120px] rounded-md" />
          ) : (skills || []).length === 0 ? (
            <EmptyState icon="📄" title="No skills synced" message='Subscribe to skills in the Skills library, then run "forge sync".' actionLabel="Browse skills" actionHref="/skills" />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {(skills || []).map(skill => (
                <div key={skill.id} className="border border-border rounded-md bg-[hsl(var(--card))] p-4">
                  <div className="flex items-center gap-2">
                    <span>📄</span>
                    <div>
                      <p className="text-sm font-medium">{skill.title}</p>
                      <p className="text-xs text-muted-foreground">{skill.category} · {skill.author_name}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>

      {openApp && <AppPane slug={openApp.slug} name={openApp.name} onClose={() => setOpenApp(null)} />}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
cd /Users/nicholasruzicka/projects/forge
git add web/app/my-forge/ web/components/app-pane.tsx
git commit -m "feat: implement My Forge page with installed/saved/skills tabs and inline app pane"
```

---

## Task 10: Publish Page

**Files:**
- Create: `web/app/publish/page.tsx`
- Create: `web/components/drop-zone.tsx`

- [ ] **Step 1: Create drop zone component**

Create `web/components/drop-zone.tsx`:

```tsx
"use client";

import { useState, useRef, DragEvent } from "react";
import { cn } from "@/lib/utils";

export function DropZone({ onFile, accept = ".html,.zip" }: { onFile: (file: File) => void; accept?: string }) {
  const [over, setOver] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handle = (file: File) => { setFileName(`${file.name} (${(file.size / 1024).toFixed(1)} KB)`); onFile(file); };

  const onDrop = (e: DragEvent) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files?.[0]; if (f) handle(f); };

  return (
    <div
      className={cn(
        "border-2 border-dashed rounded-md p-10 text-center cursor-pointer transition-colors",
        over ? "border-[hsl(var(--primary))] bg-[hsl(var(--primary)/0.05)]" : "border-border hover:border-[hsl(var(--border-strong))]"
      )}
      onClick={() => inputRef.current?.click()}
      onDragOver={e => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
    >
      <input ref={inputRef} type="file" accept={accept} className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) handle(f); }} />
      {fileName ? (
        <p className="text-sm text-foreground">{fileName}</p>
      ) : (
        <p className="text-sm text-muted-foreground">📦 Drop a zip or .html file here, or click to browse</p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create publish page**

Create `web/app/publish/page.tsx`:

```tsx
"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DropZone } from "@/components/drop-zone";
import { useUser } from "@/lib/user-context";
import * as api from "@/lib/api";
import { trackMilestone } from "@/lib/milestones";
import { cn } from "@/lib/utils";

const CATEGORIES = ["Productivity", "Account Research", "Email", "Reporting", "Onboarding", "Forecasting", "Developer Tools", "Writing", "Meetings", "Other"];
const MODES = [
  { key: "paste", label: "📝 Paste HTML" },
  { key: "upload", label: "📦 Upload file" },
  { key: "github", label: "🐙 From GitHub" },
] as const;
type Mode = (typeof MODES)[number]["key"];

export default function PublishPage() {
  const { name, email, setIdentity } = useUser();
  const [mode, setMode] = useState<Mode>("paste");
  const [htmlContent, setHtmlContent] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [githubUrl, setGithubUrl] = useState("");
  const [meta, setMeta] = useState({ name: "", tagline: "", category: "Productivity", icon: "⊞", description: "", author_name: "", author_email: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState<{ name: string; url: string } | null>(null);

  useEffect(() => {
    setMeta(m => ({ ...m, author_name: m.author_name || name, author_email: m.author_email || email }));
  }, [name, email]);

  const set = (k: string, v: string) => setMeta(m => ({ ...m, [k]: v }));

  const handlePasteDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file && file.name.endsWith(".html")) {
      file.text().then(t => setHtmlContent(t));
    }
  };

  const handleSubmit = async () => {
    if (!meta.name || !meta.tagline || !meta.author_email) { setError("Name, tagline, and email are required."); return; }
    setError(""); setLoading(true);

    try {
      if (meta.author_name && meta.author_email) setIdentity(meta.author_name, meta.author_email);

      let result: Record<string, unknown>;

      if (mode === "github") {
        result = await api.submitFromGithub(githubUrl, meta) as Record<string, unknown>;
      } else {
        const html = mode === "paste" ? htmlContent : await uploadFile?.text();
        if (!html) { setError("No HTML content provided."); setLoading(false); return; }
        result = await api.submitApp({ ...meta, html }) as Record<string, unknown>;
      }

      const slug = (result.slug || result.id || meta.name) as string;
      const msg = trackMilestone("first_submission");
      if (msg) toast.success(msg);
      setSuccess({ name: meta.name, url: `/apps/${slug}` });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Publish failed");
    } finally { setLoading(false); }
  };

  if (success) {
    return (
      <div className="p-6 max-w-lg mx-auto text-center mt-20">
        <div className="border border-border rounded-lg bg-[hsl(var(--card))] p-8">
          <div className="text-4xl mb-4">🎉</div>
          <h2 className="text-xl font-semibold mb-2">{success.name} published</h2>
          <p className="text-sm text-muted-foreground mb-4">It's pending admin review. Once approved, anyone on your team can add it to their Forge.</p>
          <code className="block text-xs font-mono text-muted-foreground bg-[hsl(var(--surface))] p-2 rounded mb-4">{typeof window !== "undefined" ? window.location.origin : ""}{success.url}</code>
          <div className="flex gap-2 justify-center">
            <Button asChild><Link href={success.url}>Open it</Link></Button>
            <Button variant="secondary" asChild><Link href="/my-forge">Go to My Forge</Link></Button>
            <Button variant="ghost" onClick={() => { setSuccess(null); setHtmlContent(""); setMeta(m => ({ ...m, name: "", tagline: "", description: "" })); }}>Publish another</Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h1 className="text-xl font-semibold mb-1">Publish</h1>
      <p className="text-sm text-muted-foreground mb-6">Submit a new app to the Forge catalog.</p>

      {/* Mode pills */}
      <div className="flex gap-2 mb-6">
        {MODES.map(m => (
          <button key={m.key} onClick={() => setMode(m.key)} className={cn("px-3 py-1.5 rounded-md text-sm transition-colors border", mode === m.key ? "bg-[hsl(var(--primary)/0.08)] text-[hsl(var(--primary))] border-[hsl(var(--primary)/0.2)]" : "border-border text-muted-foreground hover:text-foreground hover:border-[hsl(var(--border-strong))]")}>{m.label}</button>
        ))}
      </div>

      {/* Content area */}
      {mode === "paste" && (
        <div className="mb-6">
          <Textarea value={htmlContent} onChange={e => setHtmlContent(e.target.value)} onDrop={handlePasteDrop} onDragOver={e => e.preventDefault()} placeholder="Paste your HTML here..." className="font-mono text-xs min-h-[300px] bg-[hsl(var(--surface))]" />
          <p className="text-xs text-muted-foreground mt-1">Tip: drag-drop an .html file directly into this box.</p>
        </div>
      )}
      {mode === "upload" && (
        <div className="mb-6"><DropZone onFile={setUploadFile} accept=".html,.zip" /></div>
      )}
      {mode === "github" && (
        <div className="mb-6">
          <Input value={githubUrl} onChange={e => setGithubUrl(e.target.value)} placeholder="https://github.com/your-team/your-app" className="bg-[hsl(var(--surface))]" />
          <p className="text-xs text-muted-foreground mt-1">Public repos work out of the box. Private repos need a deploy token.</p>
        </div>
      )}

      {/* Metadata */}
      <div className="space-y-3 border-t border-border pt-6">
        <div className="grid grid-cols-[1fr_60px] gap-3">
          <div><label className="text-xs text-muted-foreground mb-1 block">Name *</label><Input value={meta.name} onChange={e => set("name", e.target.value)} maxLength={60} className="bg-[hsl(var(--surface))]" /></div>
          <div><label className="text-xs text-muted-foreground mb-1 block">Icon</label><Input value={meta.icon} onChange={e => set("icon", e.target.value)} maxLength={3} className="bg-[hsl(var(--surface))] text-center text-lg" /></div>
        </div>
        <div><label className="text-xs text-muted-foreground mb-1 block">Tagline *</label><Input value={meta.tagline} onChange={e => set("tagline", e.target.value)} maxLength={100} placeholder="What does it do, in 8 words?" className="bg-[hsl(var(--surface))]" /></div>
        <div><label className="text-xs text-muted-foreground mb-1 block">Category</label>
          <Select value={meta.category} onValueChange={v => set("category", v)}>
            <SelectTrigger className="bg-[hsl(var(--surface))]"><SelectValue /></SelectTrigger>
            <SelectContent>{CATEGORIES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div><label className="text-xs text-muted-foreground mb-1 block">Description</label><Textarea value={meta.description} onChange={e => set("description", e.target.value)} placeholder="2-3 sentences." className="bg-[hsl(var(--surface))]" /></div>
        <div className="grid grid-cols-2 gap-3">
          <div><label className="text-xs text-muted-foreground mb-1 block">Your name</label><Input value={meta.author_name} onChange={e => set("author_name", e.target.value)} className="bg-[hsl(var(--surface))]" /></div>
          <div><label className="text-xs text-muted-foreground mb-1 block">Your email *</label><Input value={meta.author_email} onChange={e => set("author_email", e.target.value)} type="email" className="bg-[hsl(var(--surface))]" /></div>
        </div>
      </div>

      {error && <p className="text-sm text-destructive mt-4">{error}</p>}

      <div className="flex justify-end mt-6">
        <Button onClick={handleSubmit} disabled={loading}>{loading ? "Publishing..." : "Publish"}</Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
cd /Users/nicholasruzicka/projects/forge
git add web/app/publish/ web/components/drop-zone.tsx
git commit -m "feat: implement publish page with paste/upload/github modes"
```

---

## Task 11: Admin Pages

**Files:**
- Create: `web/app/admin/page.tsx`
- Create: `web/app/admin/runs/page.tsx`
- Create: `web/components/admin-gate.tsx`
- Create: `web/components/run-detail.tsx`

- [ ] **Step 1: Create admin gate component**

Create `web/components/admin-gate.tsx`:

```tsx
"use client";

import { useState, ReactNode } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useUser } from "@/lib/user-context";
import * as api from "@/lib/api";

export function AdminGate({ children }: { children: ReactNode }) {
  const { adminKey, setAdminKey } = useUser();
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const [verified, setVerified] = useState(!!adminKey);
  const [loading, setLoading] = useState(false);

  // Auto-verify on mount if key exists
  if (adminKey && !verified) {
    api.getAdminQueue().then(() => setVerified(true)).catch(() => {
      setAdminKey("");
      setVerified(false);
    });
  }

  if (verified && adminKey) return <>{children}</>;

  const handleSubmit = async () => {
    if (!input) return;
    setLoading(true); setError("");
    // Temporarily set key so api.ts picks it up
    localStorage.setItem("forge_admin_key", input);
    try {
      await api.getAdminQueue();
      setAdminKey(input);
      setVerified(true);
    } catch {
      localStorage.removeItem("forge_admin_key");
      setError("Wrong key — try again");
    } finally { setLoading(false); }
  };

  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="border border-border rounded-lg bg-[hsl(var(--card))] p-8 w-full max-w-sm">
        <h2 className="text-lg font-semibold mb-1">Admin access</h2>
        <p className="text-sm text-muted-foreground mb-4">Enter the admin key (from <code className="font-mono text-xs">ADMIN_KEY</code> env var).</p>
        <Input
          type="password"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleSubmit()}
          placeholder={error || "Admin key"}
          className={`bg-[hsl(var(--surface))] mb-3 ${error ? "border-destructive" : ""}`}
        />
        <Button className="w-full" onClick={handleSubmit} disabled={loading}>{loading ? "Verifying..." : "Continue"}</Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create admin page**

Create `web/app/admin/page.tsx`:

```tsx
"use client";

import { toast } from "sonner";
import { AdminGate } from "@/components/admin-gate";
import { useAdminQueue, useAdminStats } from "@/lib/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import * as api from "@/lib/api";
import Link from "next/link";

export default function AdminPage() {
  return (
    <AdminGate>
      <AdminContent />
    </AdminGate>
  );
}

function AdminContent() {
  const { data: stats } = useAdminStats();
  const { data: queue, mutate } = useAdminQueue();

  const handleApprove = async (toolId: number) => {
    if (!confirm("Approve this app? It becomes live in the catalog immediately.")) return;
    try { await api.approveApp(toolId); toast.success("Approved"); mutate(); }
    catch { toast.error("Approve failed"); }
  };

  const handleReject = async (toolId: number) => {
    const reason = prompt("Why are you rejecting this? (Author will see this.)");
    if (reason === null) return;
    try { await api.rejectApp(toolId, reason); toast.info("Rejected"); mutate(); }
    catch { toast.error("Reject failed"); }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold mb-1">Admin</h1>
          <p className="text-sm text-muted-foreground">Review queue and platform stats.</p>
        </div>
        <Link href="/admin/runs" className="text-sm text-[hsl(var(--primary))] hover:underline">Claude Runs →</Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {stats ? (
          <>
            <div className="border border-border rounded-md bg-[hsl(var(--card))] p-4"><div className="text-2xl font-bold text-[hsl(var(--primary))]">{stats.apps_live}</div><div className="text-xs text-muted-foreground uppercase tracking-wide">Apps live</div></div>
            <div className="border border-border rounded-md bg-[hsl(var(--card))] p-4"><div className="text-2xl font-bold text-[hsl(var(--primary))]">{stats.apps_pending}</div><div className="text-xs text-muted-foreground uppercase tracking-wide">Pending review</div></div>
            <div className="border border-border rounded-md bg-[hsl(var(--card))] p-4"><div className="text-2xl font-bold text-[hsl(var(--primary))]">{stats.skills_total}</div><div className="text-xs text-muted-foreground uppercase tracking-wide">Skills total</div></div>
          </>
        ) : Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-[80px] rounded-md" />)}
      </div>

      {/* Queue */}
      <h2 className="text-sm font-medium mb-3">Review Queue</h2>
      {!queue ? (
        <Skeleton className="h-[200px] rounded-md" />
      ) : queue.length === 0 ? (
        <EmptyState icon="🎉" title="Queue is empty" message="Nothing pending. Check back when authors publish new apps." />
      ) : (
        <div className="space-y-3">
          {queue.map(tool => (
            <div key={tool.id} className="border border-border rounded-md bg-[hsl(var(--card))] p-4">
              <div className="flex items-start gap-3 mb-2">
                <span className="text-2xl w-9 h-9 flex items-center justify-center border border-border rounded-md bg-[hsl(var(--surface))]">{tool.icon || "⊞"}</span>
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium text-sm">{tool.name}</h3>
                  <p className="text-xs text-muted-foreground">{tool.tagline}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 text-xs text-muted-foreground mb-3 flex-wrap">
                <span>{tool.category || "Other"}</span>
                <span>· {tool.author_name || "Unknown"} ({tool.author_email})</span>
                {tool.html_length && <span>· {tool.html_length} bytes</span>}
              </div>
              <div className="flex gap-2">
                <Button size="sm" className="bg-[hsl(var(--success))] hover:bg-[hsl(var(--success))]/90 text-white h-7 text-xs" onClick={() => handleApprove(tool.id)}>Approve</Button>
                <Button size="sm" variant="destructive" className="h-7 text-xs" onClick={() => handleReject(tool.id)}>Reject</Button>
                <Button size="sm" variant="ghost" className="h-7 text-xs" asChild><a href={`/apps/${tool.slug}`} target="_blank" rel="noopener">Preview</a></Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create run detail component**

Create `web/components/run-detail.tsx`:

```tsx
"use client";

import { Badge } from "@/components/ui/badge";
import type { ClaudeRun } from "@/lib/types";

const statusColors = { running: "bg-green-500/10 text-green-400", complete: "bg-blue-500/10 text-blue-400", error: "bg-red-500/10 text-red-400" };

export function RunDetail({ run }: { run: ClaudeRun }) {
  const color = statusColors[run.status] || statusColors.complete;
  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-2 mb-3">
        <Badge className={color}>{run.status}</Badge>
        {run.exit_code !== undefined && run.exit_code !== null && <span className="text-xs text-muted-foreground font-mono">exit {run.exit_code}</span>}
      </div>
      <div className="grid grid-cols-2 gap-4 flex-1 min-h-0">
        <div className="flex flex-col">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Prompt</p>
          <div className="flex-1 bg-[hsl(var(--surface))] border border-border rounded-md p-3 font-mono text-xs overflow-auto whitespace-pre-wrap">{run.prompt}</div>
        </div>
        <div className="flex flex-col">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Output</p>
          <div className="flex-1 bg-[hsl(var(--surface))] border border-border rounded-md p-3 font-mono text-xs overflow-auto whitespace-pre-wrap">{run.output || "(no output yet)"}</div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create admin runs page**

Create `web/app/admin/runs/page.tsx`:

```tsx
"use client";

import { useState } from "react";
import { toast } from "sonner";
import { AdminGate } from "@/components/admin-gate";
import { RunDetail } from "@/components/run-detail";
import { useClaudeRuns, useClaudeRun } from "@/lib/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import * as api from "@/lib/api";
import Link from "next/link";
import { cn } from "@/lib/utils";

const statusColors = { running: "bg-green-500/10 text-green-400", complete: "bg-blue-500/10 text-blue-400", error: "bg-red-500/10 text-red-400" };

export default function AdminRunsPage() {
  return <AdminGate><RunsContent /></AdminGate>;
}

function RunsContent() {
  const { data: runs, mutate } = useClaudeRuns();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const { data: selectedRun } = useClaudeRun(selectedId);
  const [prompt, setPrompt] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleExec = async () => {
    if (!prompt.trim()) return;
    setSubmitting(true);
    try {
      const run = await api.execClaude(prompt);
      setSelectedId(run.id);
      setPrompt("");
      mutate();
    } catch { toast.error("Agent unavailable"); }
    finally { setSubmitting(false); }
  };

  return (
    <div className="flex h-[calc(100vh-48px)] md:h-screen">
      {/* Left: run list */}
      <div className="w-[280px] border-r border-border bg-[hsl(var(--surface))] flex flex-col shrink-0">
        <div className="px-3 py-3 border-b border-border flex items-center justify-between">
          <span className="text-sm font-medium">Claude Runs</span>
          <Link href="/admin" className="text-xs text-muted-foreground hover:text-foreground">← Admin</Link>
        </div>
        <div className="flex-1 overflow-y-auto">
          {!runs ? (
            <div className="p-3 space-y-2">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[50px] rounded-md" />)}</div>
          ) : runs.length === 0 ? (
            <p className="text-xs text-muted-foreground p-3">No runs yet</p>
          ) : (
            runs.map(run => (
              <button
                key={run.id}
                onClick={() => setSelectedId(run.id)}
                className={cn("w-full text-left px-3 py-2.5 border-b border-border hover:bg-[hsl(var(--surface-2))] transition-colors", selectedId === run.id && "border-l-2 border-l-[hsl(var(--primary))] bg-[hsl(var(--surface-2))]")}
              >
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-xs font-mono text-muted-foreground">#{run.id}</span>
                  <Badge className={`${statusColors[run.status] || ""} text-[10px] h-4`}>{run.status}</Badge>
                </div>
                <p className="text-xs text-muted-foreground line-clamp-1">{run.prompt}</p>
              </button>
            ))
          )}
        </div>
        <div className="p-3 border-t border-border">
          <Textarea value={prompt} onChange={e => setPrompt(e.target.value)} placeholder="Enter a prompt..." className="text-xs min-h-[60px] bg-[hsl(var(--surface-2))] mb-2" />
          <Button size="sm" className="w-full" onClick={handleExec} disabled={submitting}>{submitting ? "..." : "▶ Run"}</Button>
        </div>
      </div>

      {/* Right: detail */}
      <div className="flex-1 p-6 overflow-auto">
        {selectedRun ? (
          <RunDetail run={selectedRun} />
        ) : (
          <div className="flex items-center justify-center h-full text-sm text-muted-foreground">← Select a run to view its log</div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Commit**

```bash
cd /Users/nicholasruzicka/projects/forge
git add web/app/admin/ web/components/admin-gate.tsx web/components/run-detail.tsx
git commit -m "feat: implement admin pages — review queue, stats, and Claude runs viewer"
```

---

## Task 12: Final Integration and Verification

**Files:**
- Verify all pages work end-to-end

- [ ] **Step 1: Ensure Geist Mono font file exists**

```bash
ls web/app/fonts/GeistMonoVF.woff 2>/dev/null || (mkdir -p web/app/fonts && curl -L -o web/app/fonts/GeistMonoVF.woff "https://github.com/vercel/geist-font/raw/main/packages/next/src/fonts/GeistMonoVF.woff")
```

If the curl fails, update `layout.tsx` to remove the local font and use `font-mono` system fallback instead.

- [ ] **Step 2: Run the dev server and verify each page**

```bash
cd /Users/nicholasruzicka/projects/forge/web
npm run dev
```

Open http://localhost:3000 and verify:

1. `/` — sidebar shows, catalog grid loads (with Flask running), search works, category pills work
2. `/apps/[slug]` — click any card, detail page loads with overview and embed tabs
3. `/skills` — grid loads, search works, upvote/subscribe/install disclosure works
4. `/my-forge` — three tabs show, installed apps list works
5. `/publish` — three mode pills work, form validates, submit works
6. `/admin` — key gate shows, after auth shows queue and stats
7. `/admin/runs` — split view loads, can select runs
8. `⌘K` — command palette opens, searches across apps and skills
9. Sidebar — installed apps appear, collapse toggle works
10. Mobile — sidebar hides, hamburger works (use responsive mode in browser devtools)

- [ ] **Step 3: Type check**

```bash
cd /Users/nicholasruzicka/projects/forge/web
npx tsc --noEmit
```

Fix any TypeScript errors.

- [ ] **Step 4: Build check**

```bash
cd /Users/nicholasruzicka/projects/forge/web
npm run build
```

Fix any build errors.

- [ ] **Step 5: Add .superpowers to .gitignore**

```bash
echo ".superpowers/" >> /Users/nicholasruzicka/projects/forge/.gitignore
```

- [ ] **Step 6: Final commit**

```bash
cd /Users/nicholasruzicka/projects/forge
git add web/ .gitignore
git commit -m "feat: complete Next.js frontend rewrite — all pages implemented"
```
