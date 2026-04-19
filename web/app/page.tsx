"use client";

import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
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
    <div className="flex flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold text-foreground">Apps</h1>
        <p className="text-sm text-text-secondary">
          Browse and install tools built by your team.
        </p>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-text-muted" />
        <Input
          placeholder="Search apps..."
          className="bg-surface pl-9"
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

      {/* Trending */}
      <TrendingStrip />

      {/* Loading */}
      {isLoading && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-40 rounded-xl" />
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
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
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
