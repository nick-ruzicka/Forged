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
    <div className="flex flex-col gap-5 rounded-2xl border border-border bg-gradient-to-b from-surface-2/50 to-transparent p-5">
      {hasRole && (
        <div className="flex flex-col gap-3">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-text-muted/70">
            Trending with {data.role || "your role"}s this week
          </p>
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
            {data.role_trending.map((item) => (
              <TrendingChip key={item.slug} item={item} />
            ))}
          </div>
        </div>
      )}
      {hasTeam && (
        <div className="flex flex-col gap-3">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-text-muted/70">
            Popular on your team
          </p>
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
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
      className="group flex items-center gap-2.5 rounded-xl border border-border bg-card px-3.5 py-2.5 transition-all duration-150 hover:border-border-strong hover:bg-white/[0.02]"
    >
      <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-surface-2 text-sm ring-1 ring-border">
        {item.icon || "⊞"}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13px] font-medium text-foreground">{item.name}</p>
        <p className="truncate text-[11px] text-text-muted">{item.reason}</p>
      </div>
    </Link>
  );
}
