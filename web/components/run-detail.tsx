"use client";

import { Badge } from "@/components/ui/badge";
import type { ClaudeRun } from "@/lib/types";

interface RunDetailProps {
  run: ClaudeRun;
}

const statusConfig: Record<
  ClaudeRun["status"],
  { label: string; className: string }
> = {
  running: {
    label: "Running",
    className: "bg-green-500/15 text-green-400 border-green-500/30",
  },
  complete: {
    label: "Complete",
    className: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  },
  error: {
    label: "Error",
    className: "bg-red-500/15 text-red-400 border-red-500/30",
  },
};

export function RunDetail({ run }: RunDetailProps) {
  const cfg = statusConfig[run.status];

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Badge variant="outline" className={cfg.className}>
          {cfg.label}
        </Badge>
        {run.exit_code != null && (
          <span className="text-xs text-muted-foreground">
            Exit code: {run.exit_code}
          </span>
        )}
      </div>

      {/* Two-column grid */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {/* Prompt */}
        <div className="flex flex-col gap-1.5">
          <span className="text-xs font-medium uppercase text-muted-foreground">
            Prompt
          </span>
          <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap rounded-lg border bg-surface p-3 font-mono text-xs text-foreground">
            {run.prompt}
          </pre>
        </div>

        {/* Output */}
        <div className="flex flex-col gap-1.5">
          <span className="text-xs font-medium uppercase text-muted-foreground">
            Output
          </span>
          <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap rounded-lg border bg-surface p-3 font-mono text-xs text-foreground">
            {run.output ?? "(no output yet)"}
          </pre>
        </div>
      </div>
    </div>
  );
}
