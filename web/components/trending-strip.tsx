"use client";

import Link from "next/link";
import { useTrending } from "@/lib/hooks";

export function TrendingStrip() {
  const { data } = useTrending();

  if (!data) return null;

  const hasRole = data.role_trending.length > 0;
  const hasTeam = data.team_popular.length > 0;

  if (!hasRole && !hasTeam) return null;

  return (
    <div className="flex flex-col gap-4">
      {hasRole && (
        <div className="flex flex-col gap-2">
          <p className="text-[10px] font-medium uppercase tracking-wider text-text-muted">
            Trending with {data.role || "your role"}s this week
          </p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {data.role_trending.map((item) => (
              <TrendingChip key={item.slug} item={item} />
            ))}
          </div>
        </div>
      )}
      {hasTeam && (
        <div className="flex flex-col gap-2">
          <p className="text-[10px] font-medium uppercase tracking-wider text-text-muted">
            Popular on your team
          </p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {data.team_popular.map((item) => (
              <TrendingChip key={item.slug} item={item} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function TrendingChip({ item }: { item: { slug: string; name: string; icon?: string; reason: string } }) {
  return (
    <Link
      href={`/apps/${item.slug}`}
      className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 transition-colors hover:border-accent"
    >
      <span className="text-sm">{item.icon || "⊞"}</span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs font-medium text-foreground">{item.name}</p>
        <p className="truncate text-[9px] text-text-muted">{item.reason}</p>
      </div>
    </Link>
  );
}
