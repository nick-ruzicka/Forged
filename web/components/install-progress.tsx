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
    // Auto-scroll
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
                // progress, installing, pulling, etc.
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
        // Stream ended — OK if already succeeded/failed
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

      // Stream ended with no terminal event
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

  // --- Idle: show install button + manual command ---
  if (phase === "idle") {
    return (
      <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
        {agentAvailable && installCommand && (
          <Button onClick={handleInstall} className="w-full">
            <Download className="mr-2 size-4" />
            Install {slug}
          </Button>
        )}
        {installCommand && (
          <div className="flex flex-col gap-2">
            <span className="text-xs text-text-muted">
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
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
      {/* Status line */}
      <div className="flex items-center gap-2">
        {phase === "done" ? (
          <Check className="size-4 shrink-0 text-green-500" />
        ) : phase === "error" ? (
          <span className="shrink-0 text-sm text-destructive">✕</span>
        ) : (
          <Loader2 className="size-4 shrink-0 animate-spin text-primary" />
        )}
        <span
          className={`text-sm ${phase === "error" ? "text-destructive" : phase === "done" ? "text-green-500" : "text-foreground"}`}
        >
          {statusLine}
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface">
        <div
          className={`h-full rounded-full transition-all duration-300 ${
            phase === "done"
              ? "bg-green-500"
              : phase === "error"
                ? "bg-destructive"
                : "bg-primary"
          }`}
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Live log */}
      {logLines.length > 0 && (
        <div
          ref={logRef}
          className="max-h-36 overflow-y-auto rounded-md bg-black/30 px-3 py-2 font-mono text-[11px] leading-relaxed text-text-muted"
        >
          {logLines.map((line, i) => (
            <div key={i}>{line}</div>
          ))}
        </div>
      )}

      {/* Error fallback */}
      {phase === "error" && installCommand && (
        <div className="mt-1 flex flex-col gap-2">
          <span className="text-xs text-text-muted">
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
    <div className="flex items-start gap-2">
      <code className="flex-1 rounded bg-surface px-3 py-2 font-mono text-xs text-foreground whitespace-pre-wrap">
        {text}
      </code>
      <Button
        variant="ghost"
        size="icon"
        className="shrink-0 mt-1"
        onClick={async () => {
          await navigator.clipboard.writeText(text);
          toast.success("Copied to clipboard");
          onCopy();
        }}
      >
        {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
      </Button>
    </div>
  );
}
