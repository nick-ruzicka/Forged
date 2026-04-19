"use client";

import Link from "next/link";
import { Star } from "lucide-react";
import type { App } from "@/lib/types";
import { StarButton } from "@/components/star-button";
import { InstallButton } from "@/components/install-button";
import { Badge } from "@/components/ui/badge";

interface AppCardProps {
  app: App;
  isStarred: boolean;
  isInstalled: boolean;
}

export function AppCard({ app, isStarred, isInstalled }: AppCardProps) {
  return (
    <Link
      href={`/apps/${app.slug}`}
      className="group relative flex flex-col gap-4 rounded-2xl border border-border bg-card p-5 transition-all duration-200 hover:border-border-strong hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.3)]"
    >
      {/* Top row: icon + star */}
      <div className="flex items-start justify-between">
        <div className="flex size-12 items-center justify-center rounded-xl bg-surface-2 text-2xl ring-1 ring-border">
          {app.icon || "📦"}
        </div>
        <StarButton toolId={app.id} isStarred={isStarred} size="sm" />
      </div>

      {/* Name + tagline */}
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center gap-2">
          <span className="text-[15px] font-semibold tracking-tight text-foreground">
            {app.name}
          </span>
          {isInstalled && (
            <span className="flex size-4 items-center justify-center rounded-full bg-green-500/15 text-green-400">
              <svg width="8" height="8" viewBox="0 0 8 8" fill="none"><path d="M1.5 4L3.2 5.7L6.5 2.3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
            </span>
          )}
        </div>
        {app.tagline && (
          <span className="text-[13px] leading-snug text-text-secondary line-clamp-2">
            {app.tagline}
          </span>
        )}
      </div>

      {/* Category + rating row */}
      <div className="flex items-center gap-2">
        {app.category && (
          <Badge variant="secondary" className="text-[10px]">{app.category}</Badge>
        )}
        {app.avg_rating != null && app.avg_rating > 0 && (
          <div className="flex items-center gap-0.5">
            <Star className="size-3 fill-yellow-400 text-yellow-400" />
            <span className="text-[11px] font-medium tabular-nums text-text-secondary">
              {app.avg_rating.toFixed(1)}
            </span>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="mt-auto flex items-center justify-between border-t border-border pt-3">
        <span className="text-xs text-text-muted">
          {app.author_name || "Unknown"}
          {app.install_count != null && app.install_count > 0 && (
            <>
              <span className="mx-1.5 text-border">·</span>
              {app.install_count >= 1000
                ? (app.install_count / 1000).toFixed(1).replace(/\.0$/, "") + "k"
                : app.install_count}{" "}
              installs
            </>
          )}
        </span>
        <InstallButton
          toolId={app.id}
          slug={app.slug}
          isInstalled={isInstalled}
          delivery={app.delivery}
        />
      </div>
    </Link>
  );
}
