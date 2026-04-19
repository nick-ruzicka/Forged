"use client";

import Link from "next/link";
import type { App } from "@/lib/types";
import { StarButton } from "@/components/star-button";
import { InstallButton } from "@/components/install-button";

interface AppCardProps {
  app: App;
  isStarred: boolean;
  isInstalled: boolean;
}

export function AppCard({ app, isStarred, isInstalled }: AppCardProps) {
  return (
    <Link
      href={`/apps/${app.slug}`}
      className="group flex flex-col gap-3 rounded-xl border border-border bg-card p-4 transition-colors hover:border-border-strong"
    >
      <div className="flex items-start justify-between">
        <span className="text-2xl">{app.icon || "📦"}</span>
        <StarButton toolId={app.id} isStarred={isStarred} size="sm" />
      </div>

      <div className="flex flex-col gap-1">
        <span className="text-sm font-medium text-foreground">{app.name}</span>
        {app.tagline && (
          <span className="text-xs text-text-secondary line-clamp-1">
            {app.tagline}
          </span>
        )}
      </div>

      <div className="mt-auto flex items-center justify-between">
        <span className="text-xs text-text-muted">
          {app.author_name || "Unknown"}
          {app.install_count != null && ` \u00b7 ${app.install_count} installs`}
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
