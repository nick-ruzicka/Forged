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
// Apps
// ---------------------------------------------------------------------------

export function getApps(params?: Record<string, string>): Promise<App[]> {
  return api<App[]>("/apps", { params });
}

export function getAppBySlug(slug: string): Promise<App> {
  return api<App>(`/apps/${slug}`);
}

export function getAppReviews(toolId: number): Promise<Review[]> {
  return api<Review[]>(`/apps/${toolId}/reviews`);
}

export function postReview(
  toolId: number,
  rating: number,
  text: string,
): Promise<Review> {
  return api<Review>(`/apps/${toolId}/reviews`, {
    method: "POST",
    body: JSON.stringify({ rating, text }),
  });
}

export function getAppInspection(
  toolId: number,
): Promise<InspectionBadge[]> {
  return api<InspectionBadge[]>(`/apps/${toolId}/inspect`);
}

// ---------------------------------------------------------------------------
// User shelf
// ---------------------------------------------------------------------------

export function getMyItems(): Promise<UserItem[]> {
  return api<UserItem[]>("/me/items");
}

export function addItem(toolId: number): Promise<UserItem> {
  return api<UserItem>("/me/items", {
    method: "POST",
    body: JSON.stringify({ tool_id: toolId }),
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

// ---------------------------------------------------------------------------
// Stars
// ---------------------------------------------------------------------------

export function getMyStars(): Promise<Star[]> {
  return api<Star[]>("/me/stars");
}

export function addStar(toolId: number): Promise<Star> {
  return api<Star>("/me/stars", {
    method: "POST",
    body: JSON.stringify({ tool_id: toolId }),
  });
}

export function removeStar(toolId: number): Promise<void> {
  return api<void>(`/me/stars/${toolId}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Skills
// ---------------------------------------------------------------------------

export function getSkills(
  params?: Record<string, string>,
): Promise<Skill[]> {
  return api<Skill[]>("/skills", { params });
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

export function getMySkills(): Promise<Skill[]> {
  return api<Skill[]>("/me/skills");
}

export function subscribeSkill(skillId: number): Promise<void> {
  return api<void>(`/skills/${skillId}/subscribe`, { method: "POST" });
}

// ---------------------------------------------------------------------------
// Submit
// ---------------------------------------------------------------------------

export function submitApp(data: Partial<App>): Promise<App> {
  return api<App>("/apps", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function submitFromGithub(
  url: string,
  metadata?: Partial<App>,
): Promise<App> {
  return api<App>("/apps/github", {
    method: "POST",
    body: JSON.stringify({ url, ...metadata }),
  });
}

// ---------------------------------------------------------------------------
// Admin
// ---------------------------------------------------------------------------

export function getAdminQueue(): Promise<QueueItem[]> {
  return api<QueueItem[]>("/admin/queue");
}

export function getAdminStats(): Promise<AdminStats> {
  return api<AdminStats>("/admin/stats");
}

export function approveApp(toolId: number): Promise<void> {
  return api<void>(`/admin/queue/${toolId}/approve`, { method: "POST" });
}

export function rejectApp(toolId: number, reason: string): Promise<void> {
  return api<void>(`/admin/queue/${toolId}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

// ---------------------------------------------------------------------------
// Claude
// ---------------------------------------------------------------------------

export function getClaudeRuns(): Promise<ClaudeRun[]> {
  return api<ClaudeRun[]>("/claude/runs");
}

export function getClaudeRunLog(runId: number): Promise<ClaudeRun> {
  return api<ClaudeRun>(`/claude/runs/${runId}`);
}

export function execClaude(prompt: string): Promise<ClaudeRun> {
  return api<ClaudeRun>("/claude/exec", {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });
}

// ---------------------------------------------------------------------------
// Agent
// ---------------------------------------------------------------------------

export function getAgentRunning(): Promise<{ running: boolean }> {
  return api<{ running: boolean }>("/agent/status");
}
