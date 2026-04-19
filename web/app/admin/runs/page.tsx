"use client";

import { useCallback, useState, type KeyboardEvent } from "react";
import Link from "next/link";
import { ArrowLeft, Play } from "lucide-react";
import { mutate } from "swr";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { AdminGate } from "@/components/admin-gate";
import { RunDetail } from "@/components/run-detail";
import { EmptyState } from "@/components/empty-state";
import { useClaudeRuns, useClaudeRun } from "@/lib/hooks";
import { execClaude } from "@/lib/api";
import type { ClaudeRun } from "@/lib/types";

const statusBadgeClass: Record<ClaudeRun["status"], string> = {
  running: "bg-green-500/15 text-green-400 border-green-500/30",
  complete: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  error: "bg-red-500/15 text-red-400 border-red-500/30",
};

function RunsView() {
  const { data: runs } = useClaudeRuns();
  const [selectedId, setSelectedId] = useState<number | undefined>();
  const { data: selectedRun } = useClaudeRun(selectedId);

  const [prompt, setPrompt] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleNewRun = useCallback(async () => {
    if (!prompt.trim() || submitting) return;
    setSubmitting(true);
    try {
      const run = await execClaude(prompt.trim());
      setPrompt("");
      setSelectedId(run.id);
      await mutate("/claude/runs");
    } catch {
      // error handled silently
    } finally {
      setSubmitting(false);
    }
  }, [prompt, submitting]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        handleNewRun();
      }
    },
    [handleNewRun],
  );

  return (
    <div className="flex h-full">
      {/* Left sidebar */}
      <div className="flex w-[280px] shrink-0 flex-col border-r bg-surface">
        {/* Sidebar header */}
        <div className="flex items-center justify-between border-b px-3 py-2.5">
          <h2 className="text-sm font-semibold text-foreground">Claude Runs</h2>
          <Link
            href="/admin"
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="size-3" />
            Admin
          </Link>
        </div>

        {/* Scrollable run list */}
        <div className="flex-1 overflow-y-auto">
          {(Array.isArray(runs) ? runs : []).map((run) => (
            <button
              key={run.id}
              type="button"
              onClick={() => setSelectedId(run.id)}
              className={`flex w-full flex-col gap-1 border-b px-3 py-2.5 text-left transition-colors hover:bg-muted/50 ${
                selectedId === run.id
                  ? "border-l-2 border-l-primary bg-muted/30"
                  : ""
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-foreground">
                  #{run.id}
                </span>
                <Badge
                  variant="outline"
                  className={statusBadgeClass[run.status]}
                >
                  {run.status}
                </Badge>
              </div>
              <span className="truncate text-xs text-muted-foreground">
                {run.prompt.slice(0, 80)}
              </span>
              {run.started_at && (
                <span className="text-[10px] text-muted-foreground/60">
                  {new Date(run.started_at).toLocaleString()}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* New run */}
        <div className="flex flex-col gap-2 border-t p-3">
          <Textarea
            placeholder="Enter a prompt..."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={handleKeyDown}
            className="min-h-[60px] text-xs"
          />
          <Button
            size="sm"
            onClick={handleNewRun}
            disabled={!prompt.trim() || submitting}
          >
            <Play className="size-3.5" data-icon="inline-start" />
            {submitting ? "Running\u2026" : "Run"}
          </Button>
        </div>
      </div>

      {/* Right detail pane */}
      <div className="flex-1 overflow-y-auto">
        {selectedRun ? (
          <RunDetail run={selectedRun} />
        ) : (
          <EmptyState
            icon={<ArrowLeft className="size-6" />}
            title="No run selected"
            message="Select a run from the sidebar to view its log"
          />
        )}
      </div>
    </div>
  );
}

export default function RunsPage() {
  return (
    <AdminGate>
      <RunsView />
    </AdminGate>
  );
}
