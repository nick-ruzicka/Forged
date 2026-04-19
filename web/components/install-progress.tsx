"use client";

import { useState } from "react";
import { Loader2, Copy, Check } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";

interface InstallProgressProps {
  agentAvailable?: boolean;
  status?: string;
  progress?: number;
  installCommand?: string;
}

export function InstallProgress({
  agentAvailable,
  status,
  progress,
  installCommand,
}: InstallProgressProps) {
  const [copied, setCopied] = useState(false);

  // Agent-driven install progress
  if (agentAvailable && status) {
    return (
      <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
        <div className="flex items-center gap-2">
          <Loader2 className="size-4 animate-spin text-primary" />
          <span className="text-sm text-foreground">{status}</span>
        </div>
        {progress != null && (
          <div className="h-2 w-full overflow-hidden rounded-full bg-surface">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: `${Math.min(100, progress)}%` }}
            />
          </div>
        )}
      </div>
    );
  }

  // Fallback: manual install command
  if (installCommand) {
    return (
      <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
        <span className="text-xs text-text-muted">Install command</span>
        <div className="flex items-center gap-2">
          <code className="flex-1 rounded bg-surface px-3 py-2 font-mono text-sm text-foreground">
            {installCommand}
          </code>
          <Button
            variant="ghost"
            size="icon"
            onClick={async () => {
              await navigator.clipboard.writeText(installCommand);
              setCopied(true);
              toast.success("Copied to clipboard");
              setTimeout(() => setCopied(false), 2000);
            }}
          >
            {copied ? (
              <Check className="size-4" />
            ) : (
              <Copy className="size-4" />
            )}
          </Button>
        </div>
      </div>
    );
  }

  return null;
}
