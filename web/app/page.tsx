"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Search, ArrowRight } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { AppCard } from "@/components/app-card";
import { CategoryPills } from "@/components/category-pills";
import { EmptyState } from "@/components/empty-state";
import { RolePicker } from "@/components/role-picker";
import { TrendingStrip } from "@/components/trending-strip";
import { useApps, useMyItems, useMyStars } from "@/lib/hooks";
import { useUser } from "@/lib/user-context";

export default function CatalogPage() {
  const { role } = useUser();

  // Role picker on first visit
  const [rolePickerOpen, setRolePickerOpen] = useState(false);
  useEffect(() => {
    if (!role) setRolePickerOpen(true);
  }, [role]);

  // Search with debounce
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 300);
    return () => clearTimeout(timer);
  }, [query]);

  // Category filter
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  // Build API filters
  const filters = useMemo(() => {
    const f: Record<string, string> = {};
    if (debouncedQuery) f.q = debouncedQuery;
    if (activeCategory) f.category = activeCategory;
    return Object.keys(f).length > 0 ? f : undefined;
  }, [debouncedQuery, activeCategory]);

  const { data: apps, isLoading } = useApps(filters);
  const { data: items } = useMyItems();
  const { data: stars } = useMyStars();

  const installedIds = useMemo(
    () => new Set((Array.isArray(items) ? items : []).map((i) => i.tool_id ?? i.id)),
    [items],
  );
  const starredIds = useMemo(
    () => new Set((Array.isArray(stars) ? stars : []).map((s) => s.tool_id ?? s.id)),
    [stars],
  );

  // Extract categories from all apps (unfiltered fetch for pills)
  const { data: allApps } = useApps();
  const categories = useMemo(() => {
    if (!allApps) return [];
    const cats = new Set<string>();
    for (const app of allApps) {
      if (app.category) cats.add(app.category);
    }
    return Array.from(cats).sort();
  }, [allApps]);

  // Role-aware sorting: matching role_tags float to top
  const sortedApps = useMemo(() => {
    if (!apps) return [];
    if (!role) return apps;

    return [...apps].sort((a, b) => {
      const aMatch = matchesRole(a.role_tags, role);
      const bMatch = matchesRole(b.role_tags, role);
      if (aMatch && !bMatch) return -1;
      if (!aMatch && bMatch) return 1;
      return 0;
    });
  }, [apps, role]);

  return (
    <div className="flex flex-col gap-8 p-6 md:p-8">
      {/* Header */}
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Apps</h1>
        <p className="text-[15px] text-text-secondary">
          Discover tools your team has built. Install in one click.
        </p>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-text-muted" />
        <input
          placeholder="Search apps..."
          className="h-10 w-full rounded-xl border border-border bg-surface-2/50 pl-10 pr-4 text-sm text-foreground placeholder:text-text-muted outline-none transition-all duration-200 focus:border-primary/50 focus:bg-surface focus:ring-2 focus:ring-primary/20"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {/* Category pills */}
      {categories.length > 0 && (
        <CategoryPills
          categories={categories}
          active={activeCategory}
          onSelect={setActiveCategory}
        />
      )}

      {/* Spotlight: newest app */}
      {!isLoading && !query && !activeCategory && sortedApps.length > 0 && (() => {
        const newest = [...sortedApps].sort((a, b) =>
          new Date(b.created_at ?? 0).getTime() - new Date(a.created_at ?? 0).getTime()
        )[0];
        if (!newest) return null;
        return (
          <Link
            href={`/apps/${newest.slug}`}
            className="group relative overflow-hidden rounded-2xl border border-border bg-gradient-to-r from-primary/[0.06] via-card to-card p-6 transition-all duration-200 hover:border-border-strong hover:shadow-[0_8px_30px_rgba(0,0,0,0.2)]"
          >
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,_var(--tw-gradient-stops))] from-primary/[0.06] to-transparent pointer-events-none" />
            <div className="relative flex items-center gap-5">
              <div className="flex size-14 shrink-0 items-center justify-center rounded-2xl bg-card text-3xl ring-1 ring-border shadow-lg">
                {newest.icon || "📦"}
              </div>
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-semibold uppercase tracking-widest text-primary">New</span>
                </div>
                <span className="text-lg font-bold tracking-tight text-foreground">
                  {newest.name}
                </span>
                {newest.tagline && (
                  <span className="text-[13px] text-text-secondary line-clamp-1">
                    {newest.tagline}
                  </span>
                )}
              </div>
              <ArrowRight className="size-5 shrink-0 text-text-muted transition-transform group-hover:translate-x-1" />
            </div>
          </Link>
        );
      })()}

      {/* Trending */}
      <TrendingStrip />

      {/* Loading */}
      {isLoading && (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-5">
              <Skeleton className="size-12 rounded-xl" />
              <div className="flex flex-col gap-2">
                <Skeleton className="h-4 w-32 rounded-lg" />
                <Skeleton className="h-3 w-48 rounded-lg" />
              </div>
              <div className="mt-auto flex justify-between border-t border-border pt-3">
                <Skeleton className="h-3 w-24 rounded-lg" />
                <Skeleton className="h-7 w-16 rounded-lg" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && sortedApps.length === 0 && (
        <EmptyState
          icon={<span className="text-3xl">⚒</span>}
          title="No apps match"
          message="Try adjusting your search or filters, or publish a new app."
          actionLabel="Publish an app"
          actionHref="/publish"
        />
      )}

      {/* Card grid */}
      {!isLoading && sortedApps.length > 0 && (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
          {sortedApps.map((app) => (
            <AppCard
              key={app.id}
              app={app}
              isStarred={starredIds.has(app.id)}
              isInstalled={installedIds.has(app.id)}
            />
          ))}
        </div>
      )}

      {/* Role picker dialog */}
      <RolePicker open={rolePickerOpen} onOpenChange={setRolePickerOpen} />
    </div>
  );
}

function matchesRole(
  roleTags: string | string[] | undefined,
  role: string,
): boolean {
  if (!roleTags) return false;
  const tags = Array.isArray(roleTags)
    ? roleTags
    : roleTags.split(",").map((t) => t.trim());
  return tags.some((t) => t.toLowerCase() === role.toLowerCase());
}
