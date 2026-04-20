"use client";

import Link from "next/link";
import type { App } from "@/lib/types";
import { StarButton } from "@/components/star-button";
import { InstallButton } from "@/components/install-button";
import { AppIcon } from "@/components/app-icon";

interface AppCardProps {
  app: App;
  isStarred: boolean;
  isInstalled: boolean;
}

export function AppCard({ app, isStarred, isInstalled }: AppCardProps) {
  return (
    <Link
      href={`/apps/${app.slug}`}
      className="group relative flex flex-col gap-4 rounded-xl border border-white/[0.06] bg-white/[0.02] p-5 transition-all duration-200 hover:border-white/[0.10] hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.3)]"
      style={{ transitionTimingFunction: "cubic-bezier(0.2, 0, 0, 1)" }}
    >
      {/* Category label above title */}
      {app.category && (
        <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/40">
          {app.category}
        </span>
      )}

      {/* Icon + name row */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3.5">
          <AppIcon name={app.name} slug={app.slug} icon={app.icon} size={48} />
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <span className="text-[15px] font-semibold tracking-tight text-white/95">
                {app.name}
              </span>
              {isInstalled && (
                <span className="flex size-4 items-center justify-center rounded-full bg-green-500/15 text-green-400">
                  <svg width="8" height="8" viewBox="0 0 8 8" fill="none"><path d="M1.5 4L3.2 5.7L6.5 2.3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                </span>
              )}
            </div>
            {app.tagline && (
              <span className="text-[13.5px] font-normal leading-[1.5] text-white/60 line-clamp-2">
                {app.tagline}
              </span>
            )}
          </div>
        </div>
        <StarButton toolId={app.id} isStarred={isStarred} size="sm" />
      </div>

      {/* Footer */}
      <div className="mt-auto flex items-center justify-between border-t border-white/[0.06] pt-3">
        <span className="text-xs text-white/45">
          {app.author_name || "Unknown"}
          {app.install_count != null && app.install_count > 0 && (
            <>
              <span className="mx-1.5 text-white/20">&middot;</span>
              <span className="tabular-nums">
                {app.install_count >= 1000
                  ? (app.install_count / 1000).toFixed(1).replace(/\.0$/, "") + "k"
                  : app.install_count}
              </span>
              {" installs"}
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
