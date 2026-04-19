"use client";

import useSWR, { mutate as globalMutate } from "swr";
import type {
  App,
  Skill,
  UserItem,
  Star,
  Review,
  ClaudeRun,
  AdminStats,
  QueueItem,
  CoInstall,
  TrendingData,
  SocialData,
  UsageData,
  RunningData,
} from "./types";
import {
  getApps,
  getAppBySlug,
  getAppReviews,
  getMyItems,
  getMyStars,
  getMySkills,
  getSkills,
  getClaudeRuns,
  getClaudeRunLog,
  getAdminQueue,
  getAdminStats,
  getAgentRunning,
  addItem,
  removeItem,
  addStar,
  removeStar,
  getCoInstalls,
  getTrending,
  getSocial,
  getAgentUsage,
  getAgentRunningApps,
} from "./api";

// ---------------------------------------------------------------------------
// Apps
// ---------------------------------------------------------------------------

export function useApps(filters?: Record<string, string>) {
  const key = filters
    ? ["/apps", JSON.stringify(filters)]
    : ["/apps"];
  return useSWR<App[]>(key, () => getApps(filters));
}

export function useApp(slug: string | undefined) {
  return useSWR<App>(
    slug ? ["/apps", slug] : null,
    () => getAppBySlug(slug!),
  );
}

// ---------------------------------------------------------------------------
// User data
// ---------------------------------------------------------------------------

export function useMyItems() {
  return useSWR<UserItem[]>("/me/items", getMyItems);
}

export function useMyStars() {
  return useSWR<Star[]>("/me/stars", getMyStars);
}

export function useMySkills() {
  return useSWR<Skill[]>("/me/skills", getMySkills);
}

// ---------------------------------------------------------------------------
// Skills
// ---------------------------------------------------------------------------

export function useSkills(filters?: Record<string, string>) {
  const key = filters
    ? ["/skills", JSON.stringify(filters)]
    : ["/skills"];
  return useSWR<Skill[]>(key, () => getSkills(filters));
}

// ---------------------------------------------------------------------------
// Reviews
// ---------------------------------------------------------------------------

export function useReviews(toolId: number | undefined) {
  return useSWR<Review[]>(
    toolId != null ? ["/reviews", toolId] : null,
    () => getAppReviews(toolId!),
  );
}

// ---------------------------------------------------------------------------
// Admin
// ---------------------------------------------------------------------------

export function useAdminQueue() {
  return useSWR<QueueItem[]>("/admin/queue", getAdminQueue);
}

export function useAdminStats() {
  return useSWR<AdminStats>("/admin/stats", getAdminStats);
}

// ---------------------------------------------------------------------------
// Claude
// ---------------------------------------------------------------------------

export function useClaudeRuns() {
  return useSWR<ClaudeRun[]>("/claude/runs", getClaudeRuns, {
    refreshInterval: 5000,
  });
}

export function useClaudeRun(id: number | undefined) {
  const { data, ...rest } = useSWR<ClaudeRun>(
    id != null ? ["/claude/runs", id] : null,
    () => getClaudeRunLog(id!),
    {
      refreshInterval: (latestData) =>
        latestData?.status === "running" ? 3000 : 0,
    },
  );
  return { data, ...rest };
}

// ---------------------------------------------------------------------------
// Agent
// ---------------------------------------------------------------------------

export function useAgentRunning(enabled: boolean) {
  return useSWR<{ running: boolean }>(
    enabled ? "/agent/status" : null,
    getAgentRunning,
    { refreshInterval: 15000 },
  );
}

// ---------------------------------------------------------------------------
// Social / Discovery
// ---------------------------------------------------------------------------

export function useCoInstalls(toolId: number | undefined) {
  return useSWR<CoInstall[]>(
    toolId != null ? ["/coinstalls", toolId] : null,
    () => getCoInstalls(toolId!),
  );
}

export function useTrending() {
  return useSWR<TrendingData>("/team/trending", getTrending);
}

export function useSocial(toolId: number | undefined) {
  return useSWR<SocialData>(
    toolId != null ? ["/social", toolId] : null,
    () => getSocial(toolId!),
  );
}

export function useAgentUsage(slug: string | undefined) {
  return useSWR<UsageData>(
    slug ? ["/agent/usage", slug] : null,
    () => getAgentUsage(slug!),
  );
}

export function useRunningApps(enabled: boolean = true) {
  return useSWR<RunningData>(
    enabled ? "/agent/running-apps" : null,
    getAgentRunningApps,
    { refreshInterval: 15000 },
  );
}

// ---------------------------------------------------------------------------
// Mutation helpers
// ---------------------------------------------------------------------------

export async function toggleStar(
  toolId: number,
  isStarred: boolean,
): Promise<void> {
  if (isStarred) {
    // Optimistic remove
    await globalMutate<Star[]>(
      "/me/stars",
      (current) => current?.filter((s) => s.tool_id !== toolId),
      false,
    );
    await removeStar(toolId);
  } else {
    await addStar(toolId);
  }
  await globalMutate("/me/stars");
}

export async function installApp(toolId: number): Promise<void> {
  await addItem(toolId);
  await globalMutate("/me/items");
}

export async function uninstallApp(toolId: number): Promise<void> {
  // Optimistic remove
  await globalMutate<UserItem[]>(
    "/me/items",
    (current) => current?.filter((i) => i.tool_id !== toolId),
    false,
  );
  await removeItem(toolId);
  await globalMutate("/me/items");
}
