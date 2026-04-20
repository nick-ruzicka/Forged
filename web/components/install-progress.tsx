"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { Loader2, Copy, Check, Download, Terminal, AlertCircle } from "lucide-react";
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

type Phase = "idle" | "installing" | "done" | "error";

export function InstallProgress({
  toolId,
  slug,
  agentAvailable,
  installCommand,
  installMeta,
  autoInstall,
  onInstalled,
}: InstallProgressProps) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [statusLine, setStatusLine] = useState("");
  const [logLines, setLogLines] = useState<string[]>([]);
  const [progress, setProgress] = useState(0);
  const [copied, setCopied] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  const appendLog = useCallback((line: string) => {
    setLogLines((prev) => [...prev, line]);
    setTimeout(() => {
      if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
    }, 50);
  }, []);

  const handleInstall = useCallback(async () => {
    setPhase("installing");
    setStatusLine("Connecting to Forge Agent...");
    setLogLines([]);
    setProgress(0);

    try {
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

      const r = await fetch("http://localhost:8090/api/forge-agent/install", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(installBody),
      });

      if (!r.ok) {
        setPhase("error");
        setStatusLine(`Agent returned ${r.status}`);
        return;
      }

      const reader = r.body?.getReader();
      if (!reader) {
        setPhase("error");
        setStatusLine("No response stream");
        return;
      }

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
              const msg = evt.message || "";

              if (evt.type === "installed") {
                setProgress(100);
                setStatusLine("Installed successfully!");
                setPhase("done");
                appendLog(`✓ ${msg}`);
                succeeded = true;
              } else if (evt.type === "error") {
                setProgress(100);
                setStatusLine(msg || "Install failed");
                setPhase("error");
                appendLog(`✕ ${msg}`);
                failed = true;
              } else {
                setStatusLine(msg);
                setProgress(Math.min(5 + lineCount * 3, 95));
                if (msg) appendLog(msg);
              }
            } catch {
              // skip malformed
            }
          }
        }
      } catch {
        // Stream ended
      }

      if (succeeded) {
        try {
          await installApp(toolId);
          onInstalled?.();
        } catch {
          // shelf add failed, install still worked
        }
        return;
      }
      if (failed) return;

      setPhase("error");
      setStatusLine("Install ended unexpectedly");
    } catch {
      setPhase("error");
      setStatusLine("Could not connect to Forge Agent");
    }
  }, [toolId, slug, installCommand, installMeta, onInstalled, appendLog]);

  // Auto-install
  const autoTriggered = useRef(false);
  useEffect(() => {
    if (
      autoInstall &&
      agentAvailable &&
      !autoTriggered.current &&
      phase === "idle"
    ) {
      autoTriggered.current = true;
      handleInstall();
    }
  }, [autoInstall, agentAvailable, phase, handleInstall]);

  // --- Idle ---
  if (phase === "idle") {
    return (
      <div className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-5">
        <h4 className="text-[13px] font-semibold text-foreground">Installation</h4>
        {agentAvailable && installCommand && (
          <Button onClick={handleInstall} className="w-full">
            <Download data-icon="inline-start" />
            Install {slug}
          </Button>
        )}
        {installCommand && (
          <div className="flex flex-col gap-2">
            <span className="text-xs font-medium text-text-muted">
              {agentAvailable ? "Or install manually:" : "Install command"}
            </span>
            <CopyBlock text={installCommand} copied={copied} onCopy={() => {
              setCopied(true);
              setTimeout(() => setCopied(false), 2000);
            }} />
          </div>
        )}
      </div>
    );
  }

  // --- Installing / Done / Error ---
  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-5">
      {/* Status header */}
      <div className="flex items-center gap-3">
        {phase === "done" ? (
          <div className="flex size-8 items-center justify-center rounded-full bg-green-500/10 ring-1 ring-green-500/20">
            <Check className="size-4 text-green-500" />
          </div>
        ) : phase === "error" ? (
          <div className="flex size-8 items-center justify-center rounded-full bg-destructive/10 ring-1 ring-destructive/20">
            <AlertCircle className="size-4 text-destructive" />
          </div>
        ) : (
          <div className="flex size-8 items-center justify-center rounded-full bg-primary/10 ring-1 ring-primary/20">
            <Loader2 className="size-4 animate-spin text-primary" />
          </div>
        )}
        <div className="flex flex-col gap-0.5">
          <span className="text-[13px] font-semibold text-foreground">
            {phase === "done" ? "Installation complete" : phase === "error" ? "Installation failed" : "Installing..."}
          </span>
          <span className="text-xs text-text-muted">{statusLine}</span>
        </div>
      </div>

      {/* Progress bar — force 100% on done/error regardless of state race */}
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
        <div
          className={`h-full rounded-full transition-all duration-500 ease-out ${
            phase === "done"
              ? "bg-green-500"
              : phase === "error"
                ? "bg-destructive"
                : "bg-primary"
          }`}
          style={{ width: `${phase === "done" || phase === "error" ? 100 : progress}%` }}
        />
      </div>

      {/* Live log */}
      {logLines.length > 0 && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-1.5">
            <Terminal className="size-3 text-text-muted" />
            <span className="text-[11px] font-medium text-text-muted">Output</span>
          </div>
          <div
            ref={logRef}
            className="max-h-40 overflow-y-auto rounded-xl bg-surface-2 px-4 py-3 font-mono text-[11px] leading-relaxed text-text-muted ring-1 ring-border"
          >
            {logLines.map((line, i) => (
              <div key={i} className="py-0.5">{line}</div>
            ))}
          </div>
        </div>
      )}

      {/* Success: next step */}
      {phase === "done" && (
        <div className="flex items-center gap-3 border-t border-border pt-4">
          <Button
            size="sm"
            onClick={() => window.location.reload()}
          >
            Continue to app
          </Button>
          <span className="text-xs text-text-muted">
            App installed — reload to see configuration options
          </span>
        </div>
      )}

      {/* Error fallback */}
      {phase === "error" && installCommand && (
        <div className="flex flex-col gap-2 border-t border-border pt-4">
          <span className="text-xs font-medium text-text-muted">
            Install manually instead:
          </span>
          <CopyBlock text={installCommand} copied={copied} onCopy={() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
          }} />
        </div>
      )}
    </div>
  );
}

function CopyBlock({ text, copied, onCopy }: { text: string; copied: boolean; onCopy: () => void }) {
  return (
    <div className="flex items-start gap-2 rounded-xl bg-surface-2 p-3 ring-1 ring-border">
      <code className="flex-1 font-mono text-xs leading-relaxed text-foreground/80 whitespace-pre-wrap">
        {text}
      </code>
      <Button
        variant="ghost"
        size="icon-sm"
        className="shrink-0"
        onClick={async () => {
          await navigator.clipboard.writeText(text);
          toast.success("Copied to clipboard");
          onCopy();
        }}
      >
        {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
      </Button>
    </div>
  );
}
