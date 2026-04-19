"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { Loader2, Copy, Check, Download } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { installApp } from "@/lib/hooks";

interface InstallProgressProps {
  toolId: number;
  slug: string;
  agentAvailable?: boolean;
  installCommand?: string;
  installMeta?: string;
  autoInstall?: boolean;
  onInstalled?: () => void;
}

export function InstallProgress({
  toolId,
  slug,
  agentAvailable,
  installCommand,
  installMeta,
  autoInstall,
  onInstalled,
}: InstallProgressProps) {
  const [status, setStatus] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [installing, setInstalling] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const handleInstall = useCallback(async () => {
    setInstalling(true);
    setStatus("Starting...");
    setProgress(0);

    try {
      // Build install body from install_meta or fallback to command
      let installBody: Record<string, unknown>;
      try {
        const meta = installMeta ? JSON.parse(installMeta) : null;
        installBody =
          meta && meta.type
            ? { ...meta, name: slug }
            : { type: "command", command: installCommand, name: slug };
      } catch {
        installBody = { type: "command", command: installCommand, name: slug };
      }

      // POST to Flask SSE install proxy (direct — Next.js proxy doesn't stream SSE)
      const r = await fetch("http://localhost:8090/api/forge-agent/install", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(installBody),
      });

      const reader = r.body?.getReader();
      if (!reader) throw new Error("no_stream");

      const decoder = new TextDecoder();
      let buf = "";
      let lineCount = 0;
      let succeeded = false;
      let failed = false;

      try {
        while (true) {
          const { done: streamDone, value } = await reader.read();
          if (streamDone) break;
          buf += decoder.decode(value, { stream: true });
          const parts = buf.split("\n");
          buf = parts.pop() || "";

          for (const part of parts) {
            if (!part.startsWith("data: ")) continue;
            try {
              const evt = JSON.parse(part.slice(6));
              lineCount++;
              setStatus(evt.message || "Installing...");
              setProgress(Math.min(5 + lineCount * 4, 95));

              if (evt.type === "installed") {
                setProgress(100);
                setStatus("Installed!");
                setDone(true);
                succeeded = true;
              } else if (evt.type === "error") {
                setStatus(evt.message || "Install failed");
                setError(evt.message || "Install failed");
                setProgress(100);
                failed = true;
              }
            } catch {
              // skip malformed events
            }
          }
        }
      } catch {
        // Stream read error after install — ignore if already succeeded
      }

      // Post-stream: add to shelf if install succeeded
      if (succeeded) {
        try {
          await installApp(toolId);
          onInstalled?.();
        } catch {
          // Shelf add failed but install itself worked
        }
        return;
      }
      if (failed) return;

      // Stream ended without installed or error event
      setStatus(null);
      setInstalling(false);
    } catch (e) {
      setStatus(null);
      setInstalling(false);
      toast.error("Forge Agent not available — use the manual install command below");
    }
  }, [toolId, slug, installCommand, installMeta, onInstalled]);

  // Auto-install when agent is available and autoInstall is set
  const autoTriggered = useRef(false);
  useEffect(() => {
    if (autoInstall && agentAvailable && !autoTriggered.current && !installing && !done) {
      autoTriggered.current = true;
      handleInstall();
    }
  }, [autoInstall, agentAvailable, installing, done, handleInstall]);

  // Installing / done / error state
  if (installing || done || error) {
    return (
      <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
        <div className="flex items-center gap-2">
          {done ? (
            <Check className="size-4 text-green-500" />
          ) : error ? (
            <span className="text-sm text-destructive">✕</span>
          ) : (
            <Loader2 className="size-4 animate-spin text-primary" />
          )}
          <span className={`text-sm ${error ? "text-destructive" : "text-foreground"}`}>{status}</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-surface">
          <div
            className={`h-full rounded-full transition-all duration-500 ${done ? "bg-green-500" : error ? "bg-destructive" : "bg-primary"}`}
            style={{ width: `${progress}%` }}
          />
        </div>
        {error && installCommand && (
          <div className="mt-2 flex flex-col gap-2">
            <span className="text-xs text-text-muted">Install manually instead:</span>
            <div className="flex items-center gap-2">
              <code className="flex-1 rounded bg-surface px-3 py-2 font-mono text-xs text-foreground whitespace-pre-wrap">
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
                {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
              </Button>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
      {/* Agent install button */}
      {agentAvailable && installCommand && (
        <Button onClick={handleInstall} className="w-full">
          <Download className="mr-2 size-4" />
          Install {slug}
        </Button>
      )}

      {/* Fallback: manual install command */}
      {installCommand && (
        <div className="flex flex-col gap-2">
          <span className="text-xs text-text-muted">
            {agentAvailable ? "Or install manually:" : "Install command"}
          </span>
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
      )}
    </div>
  );
}
