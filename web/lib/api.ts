import type {
  App,
  Skill,
  UserItem,
  Star,
  Review,
  ClaudeRun,
  AdminStats,
  QueueItem,
  InspectionBadge,
  CoInstall,
  TrendingData,
  SocialData,
  UsageData,
  RunningData,
  PrivacyData,
} from "./types";

// ---------------------------------------------------------------------------
// Error
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// ---------------------------------------------------------------------------
// Identity helpers
// ---------------------------------------------------------------------------

export function getUserId(): string {
  if (typeof window === "undefined") return "";
  let id = localStorage.getItem("forge_user_id");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("forge_user_id", id);
  }
  return id;
}

export function getAdminKey(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("forge_admin_key");
}

// ---------------------------------------------------------------------------
// Generic fetch wrapper
// ---------------------------------------------------------------------------

export async function api<T>(
  path: string,
  opts: RequestInit & { params?: Record<string, string> } = {},
): Promise<T> {
  const { params, ...init } = opts;

  let url = path.startsWith("http") ? path : `/api${path}`;
  if (params) {
    const qs = new URLSearchParams(params).toString();
    if (qs) url += `?${qs}`;
  }

  const headers: Record<string, string> = {
    Accept: "application/json",
    "X-Forge-User-Id": getUserId(),
    ...(init.headers as Record<string, string>),
  };

  const adminKey = getAdminKey();
  if (adminKey) {
    headers["X-Admin-Key"] = adminKey;
  }

  if (init.body && typeof init.body === "string") {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(url, { ...init, headers });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new ApiError(res.status, text);
  }

  // Some endpoints may return 204 / empty body
  const ct = res.headers.get("content-type");
  if (!ct || !ct.includes("application/json")) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Apps — Flask serves GET /api/tools → {"tools": [...], "total": N}
// ---------------------------------------------------------------------------

export async function getApps(params?: Record<string, string>): Promise<App[]> {
  const res = await api<{ tools?: App[]; data?: App[] } | App[]>("/tools", { params });
  if (Array.isArray(res)) return res;
  return res.tools || res.data || [];
}

export async function getAppBySlug(slug: string): Promise<App> {
  return api<App>(`/tools/slug/${encodeURIComponent(slug)}`);
}

export async function getAppReviews(toolId: number): Promise<Review[]> {
  const res = await api<{ reviews?: Review[] } | Review[]>(`/tools/${toolId}/reviews`);
  if (Array.isArray(res)) return res;
  return res.reviews || [];
}

export function postReview(
  toolId: number,
  rating: number,
  text: string,
): Promise<Review> {
  return api<Review>(`/tools/${toolId}/reviews`, {
    method: "POST",
    body: JSON.stringify({ rating, note: text }),
  });
}

export async function getAppInspection(
  toolId: number,
): Promise<InspectionBadge[]> {
  const res = await api<{ badges?: InspectionBadge[] } | InspectionBadge[]>(`/tools/${toolId}/inspection`);
  if (Array.isArray(res)) return res;
  return res.badges || [];
}

// ---------------------------------------------------------------------------
// User shelf — Flask serves GET /api/me/items → {"items": [...]}
// ---------------------------------------------------------------------------

export async function getMyItems(): Promise<UserItem[]> {
  const res = await api<{ items?: UserItem[] } | UserItem[]>("/me/items");
  if (Array.isArray(res)) return res;
  return res.items || [];
}

export function addItem(toolId: number): Promise<UserItem> {
  return api<UserItem>(`/me/items/${toolId}`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function removeItem(toolId: number): Promise<void> {
  return api<void>(`/me/items/${toolId}`, { method: "DELETE" });
}

export function launchItem(toolId: number): Promise<void> {
  return api<void>(`/me/items/${toolId}/launch`, { method: "POST" });
}

export function installItem(toolId: number): Promise<void> {
  return api<void>(`/me/items/${toolId}/install`, { method: "POST" });
}

export interface ScanResult {
  matched: number;
  detected: number;
  unmarked: number;
  error?: string;
}

// Trigger a local scan via the forge-agent. Backend reconciles + returns counts.
export function scanInstalled(): Promise<ScanResult> {
  return api<ScanResult>("/forge-agent/scan");
}

// Hide a shelf row (matched or unknown). Idempotent.
export function hideItem(itemId: number): Promise<{ hidden: boolean }> {
  return api<{ hidden: boolean }>(`/me/items/${itemId}/hide`, { method: "POST" });
}

// ---------------------------------------------------------------------------
// Stars — Flask serves GET /api/me/stars → {"items": [...]}
// ---------------------------------------------------------------------------

export async function getMyStars(): Promise<Star[]> {
  const res = await api<{ items?: Star[] } | Star[]>("/me/stars");
  if (Array.isArray(res)) return res;
  return res.items || [];
}

export function addStar(toolId: number): Promise<Star> {
  return api<Star>(`/me/stars/${toolId}`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function removeStar(toolId: number): Promise<void> {
  return api<void>(`/me/stars/${toolId}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Skills — Flask may return array or {"skills": [...]}
// ---------------------------------------------------------------------------

export async function getSkills(
  params?: Record<string, string>,
): Promise<Skill[]> {
  const res = await api<{ skills?: Skill[]; data?: Skill[] } | Skill[]>("/skills", { params });
  if (Array.isArray(res)) return res;
  return res.skills || res.data || [];
}

export function upvoteSkill(skillId: number): Promise<void> {
  return api<void>(`/skills/${skillId}/upvote`, { method: "POST" });
}

export function downloadSkillUrl(skillId: number): string {
  return `/api/skills/${skillId}/download`;
}

export function submitSkill(
  data: Partial<Skill>,
): Promise<Skill> {
  return api<Skill>("/skills", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getMySkills(): Promise<Skill[]> {
  const res = await api<{ skills?: Skill[] } | Skill[]>("/me/skills");
  if (Array.isArray(res)) return res;
  return res.skills || [];
}

export function subscribeSkill(skillId: number): Promise<void> {
  return api<void>(`/me/skills/${skillId}`, { method: "POST", body: JSON.stringify({}) });
}

// ---------------------------------------------------------------------------
// Submit — Flask serves POST /api/submit/app, POST /api/submit/from-github
// ---------------------------------------------------------------------------

export function submitApp(data: Record<string, unknown>): Promise<App> {
  return api<App>("/submit/app", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function submitFromGithub(
  url: string,
  metadata?: Record<string, string>,
): Promise<App> {
  return api<App>("/submit/from-github", {
    method: "POST",
    body: JSON.stringify({ github_url: url, ...metadata }),
  });
}

// ---------------------------------------------------------------------------
// Admin — Flask serves GET /api/admin/queue → {"tools": [...]}
// ---------------------------------------------------------------------------

export async function getAdminQueue(): Promise<QueueItem[]> {
  const res = await api<{ tools?: QueueItem[] } | QueueItem[]>("/admin/queue");
  if (Array.isArray(res)) return res;
  return res.tools || [];
}

export async function getAdminStats(): Promise<AdminStats> {
  return api<AdminStats>("/admin/analytics");
}

export function approveApp(toolId: number): Promise<void> {
  return api<void>(`/admin/tools/${toolId}/approve`, {
    method: "POST",
    body: JSON.stringify({ reviewer: "admin" }),
  });
}

export function rejectApp(toolId: number, reason: string): Promise<void> {
  return api<void>(`/admin/tools/${toolId}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

// ---------------------------------------------------------------------------
// Claude — Flask serves GET /api/claude-runs → {"runs": [...]}
// ---------------------------------------------------------------------------

export async function getClaudeRuns(): Promise<ClaudeRun[]> {
  const res = await api<{ runs?: ClaudeRun[] } | ClaudeRun[]>("/claude-runs");
  if (Array.isArray(res)) return res;
  return res.runs || [];
}

export function getClaudeRunLog(runId: number): Promise<ClaudeRun> {
  return api<ClaudeRun>(`/claude-runs/${runId}/log`);
}

export function execClaude(prompt: string): Promise<ClaudeRun> {
  return api<ClaudeRun>("/claude-exec", {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });
}

// ---------------------------------------------------------------------------
// Agent
// ---------------------------------------------------------------------------

export function getAgentRunning(): Promise<{ running: boolean }> {
  return api<{ running: boolean }>("/forge-agent/running").catch(() => ({ running: false }));
}

// ---------------------------------------------------------------------------
// Social / Discovery
// ---------------------------------------------------------------------------

export async function getCoInstalls(toolId: number): Promise<CoInstall[]> {
  const res = await api<{ coinstalls?: CoInstall[] }>(`/tools/${toolId}/coinstalls`);
  return res.coinstalls || [];
}

export async function getTrending(): Promise<TrendingData> {
  return api<TrendingData>("/team/trending");
}

export async function getSocial(toolId: number): Promise<SocialData> {
  return api<SocialData>(`/tools/${toolId}/social`);
}

// ---------------------------------------------------------------------------
// Forge Agent
// ---------------------------------------------------------------------------

export async function getAgentUsage(slug: string): Promise<UsageData> {
  return api<UsageData>("/forge-agent/usage", { params: { slug } });
}

export async function getAgentRunningApps(): Promise<RunningData> {
  return api<RunningData>("/forge-agent/running").catch(() => ({ apps: [] }));
}

export async function getAgentPrivacy(): Promise<PrivacyData> {
  return api<PrivacyData>("/forge-agent/privacy");
}

export async function launchApp(slug: string, name: string): Promise<void> {
  await api("/forge-agent/launch", {
    method: "POST",
    body: JSON.stringify({ app_slug: slug, app_name: name }),
  });
}

export async function revealApp(slug: string, name: string): Promise<void> {
  await api("/forge-agent/launch", {
    method: "POST",
    body: JSON.stringify({ app_slug: slug, app_name: name, action: "reveal" }),
  });
}

export async function uninstallAgent(slug: string): Promise<void> {
  await api("/forge-agent/uninstall", {
    method: "POST",
    body: JSON.stringify({ slug }),
  });
}
