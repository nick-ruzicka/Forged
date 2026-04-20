"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Search, ArrowRight, TrendingUp } from "lucide-react";
import { AppIcon } from "@/components/app-icon";
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

  // Role picker on first visit. Derive `open` from (no role) minus user dismissals.
  const [rolePickerDismissed, setRolePickerDismissed] = useState(false);
  const rolePickerOpen = !role && !rolePickerDismissed;
  const handleRolePickerOpenChange = (next: boolean) => {
    if (!next) setRolePickerDismissed(true);
  };

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
        <h1 className="text-[28px] font-bold tracking-[-0.03em] text-white/98">Apps</h1>
        <p className="text-sm text-white/55 leading-relaxed">
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

      {/* Featured banner */}
      {!isLoading && !query && !activeCategory && sortedApps.length > 0 && (() => {
        const newest = [...sortedApps].sort((a, b) =>
          new Date(b.created_at ?? 0).getTime() - new Date(a.created_at ?? 0).getTime()
        )[0];
        if (!newest) return null;
        return (
          <Link
            href={`/apps/${newest.slug}`}
            className="group relative overflow-hidden rounded-2xl border border-white/[0.06] p-8 transition-all duration-200 hover:border-white/[0.10] hover:brightness-105 cursor-pointer"
            style={{ minHeight: 160, background: "radial-gradient(ellipse at top left, rgba(0,102,255,0.04), transparent 70%)" }}
          >
            <div className="relative flex items-center gap-6">
              {/* Icon with glow */}
              <div className="relative shrink-0">
                <div className="absolute inset-0 scale-150 rounded-full bg-primary/[0.08] blur-2xl pointer-events-none" />
                <AppIcon name={newest.name} slug={newest.slug} icon={newest.icon} size={80} />
              </div>

              {/* Content */}
              <div className="flex min-w-0 flex-1 flex-col gap-2">
                <span className="text-[8px] font-semibold uppercase tracking-[0.16em] text-white/35">
                  Featured
                </span>
                <div className="flex items-center gap-2.5">
                  <span className="rounded-full bg-[rgba(0,102,255,0.15)] px-2 py-0.5 text-[10px] font-semibold text-[#5B9FFF]">
                    NEW
                  </span>
                  <span className="text-2xl font-bold tracking-tight text-white/98">
                    {newest.name}
                  </span>
                </div>
                {newest.tagline && (
                  <span className="text-sm text-white/60 line-clamp-1">
                    {newest.tagline}
                  </span>
                )}
              </div>

              {/* Right: install stat */}
              <div className="hidden shrink-0 sm:flex flex-col items-end gap-1">
                {newest.install_count != null && newest.install_count > 0 && (
                  <div className="flex items-center gap-1.5 text-white/45">
                    <TrendingUp className="size-3.5" />
                    <span className="text-sm font-medium tabular-nums">{newest.install_count}</span>
                    <span className="text-xs">installs</span>
                  </div>
                )}
                <ArrowRight className="size-4 text-white/30 transition-transform group-hover:translate-x-1" />
              </div>
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
      <RolePicker open={rolePickerOpen} onOpenChange={handleRolePickerOpenChange} />
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
