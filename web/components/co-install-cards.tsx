"use client";

import Link from "next/link";
import { Users } from "lucide-react";
import { useCoInstalls } from "@/lib/hooks";

interface CoInstallCardsProps {
  toolId: number;
  toolName: string;
}

export function CoInstallCards({ toolId, toolName }: CoInstallCardsProps) {
  const { data: coinstalls } = useCoInstalls(toolId);

  if (!coinstalls || coinstalls.length === 0) return null;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <Users className="size-3.5 text-text-muted" />
        <h3 className="text-[13px] font-semibold uppercase tracking-widest text-text-muted/70">
          Frequently used together
        </h3>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {coinstalls.map((ci) => (
          <Link
            key={ci.slug}
            href={`/apps/${ci.slug}`}
            className="group flex items-center gap-3 rounded-2xl border border-border bg-card p-4 transition-all duration-150 hover:border-border-strong hover:-translate-y-0.5 hover:shadow-[0_4px_20px_rgba(0,0,0,0.2)]"
          >
            <div className="flex size-10 items-center justify-center rounded-xl bg-surface-2 text-lg ring-1 ring-border">
              {ci.icon || "⊞"}
            </div>
            <div className="flex min-w-0 flex-1 flex-col gap-0.5">
              <span className="truncate text-[14px] font-semibold text-foreground">
                {ci.name}
              </span>
              <span className="text-xs text-text-muted">
                {ci.overlap} users in common
              </span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
