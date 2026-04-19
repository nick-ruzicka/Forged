"use client";

import Link from "next/link";
import { useCoInstalls } from "@/lib/hooks";

interface CoInstallCardsProps {
  toolId: number;
  toolName: string;
}

export function CoInstallCards({ toolId, toolName }: CoInstallCardsProps) {
  const { data: coinstalls } = useCoInstalls(toolId);

  if (!coinstalls || coinstalls.length === 0) return null;

  return (
    <div className="flex flex-col gap-3">
      <p className="text-[10px] font-medium uppercase tracking-wider text-text-muted">
        People who use {toolName} also use
      </p>
      <div className="flex gap-3">
        {coinstalls.map((ci) => (
          <Link
            key={ci.slug}
            href={`/apps/${ci.slug}`}
            className="flex flex-1 flex-col gap-1 rounded-lg border border-border bg-surface p-3 opacity-80 transition-all hover:border-accent hover:opacity-100"
          >
            <div className="flex items-center gap-2">
              <span className="text-base">{ci.icon || "⊞"}</span>
              <span className="text-sm font-semibold text-foreground">{ci.name}</span>
            </div>
            <span className="text-[10px] text-text-muted">
              used by {ci.overlap} others
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
