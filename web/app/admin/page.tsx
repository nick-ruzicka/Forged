"use client";

import { useCallback } from "react";
import Link from "next/link";
import { ArrowRight, Check, ExternalLink, X } from "lucide-react";
import { toast } from "sonner";
import { mutate } from "swr";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { AdminGate } from "@/components/admin-gate";
import { EmptyState } from "@/components/empty-state";
import { useAdminQueue, useAdminStats } from "@/lib/hooks";
import { approveApp, rejectApp } from "@/lib/api";
import type { QueueItem } from "@/lib/types";

function AdminDashboard() {
  const { data: queue, isLoading: queueLoading } = useAdminQueue();
  const { data: stats, isLoading: statsLoading } = useAdminStats();

  const handleApprove = useCallback(async (item: QueueItem) => {
    if (!confirm(`Approve "${item.name}"?`)) return;
    try {
      await approveApp(item.id);
      toast.success("Approved");
      await mutate("/admin/queue");
      await mutate("/admin/stats");
    } catch {
      toast.error("Failed to approve app");
    }
  }, []);

  const handleReject = useCallback(async (item: QueueItem) => {
    const reason = prompt("Rejection reason:");
    if (!reason) return;
    try {
      await rejectApp(item.id, reason);
      toast.info("Rejected");
      await mutate("/admin/queue");
      await mutate("/admin/stats");
    } catch {
      toast.error("Failed to reject app");
    }
  }, []);

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-semibold text-foreground">Admin</h1>
        <div className="flex gap-2">
          <span className="rounded-lg bg-white/[0.06] px-3 py-1.5 text-sm font-medium text-white/90">
            Dashboard
          </span>
          <Link
            href="/admin/skills"
            className="rounded-lg px-3 py-1.5 text-sm font-medium text-text-muted hover:text-foreground hover:bg-white/[0.04] transition-colors"
          >
            Company Skills
          </Link>
          <Link
            href="/admin/runs"
            className="rounded-lg px-3 py-1.5 text-sm font-medium text-text-muted hover:text-foreground hover:bg-white/[0.04] transition-colors"
          >
            Claude Runs
          </Link>
        </div>
      </div>

      {/* Stats row */}
      {statsLoading ? (
        <div className="grid grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-20 rounded-xl" />
          ))}
        </div>
      ) : stats ? (
        <div className="grid grid-cols-3 gap-4">
          <StatCard label="Apps live" value={stats.apps_live} />
          <StatCard label="Pending review" value={stats.apps_pending} />
          <StatCard label="Skills total" value={stats.skills_total} />
        </div>
      ) : null}

      {/* Queue header */}
      <h2 className="text-base font-medium text-foreground">Review queue</h2>

      {/* Loading */}
      {queueLoading && (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!queueLoading && queue && queue.length === 0 && (
        <EmptyState
          icon={<span className="text-3xl">{"\uD83C\uDF89"}</span>}
          title="Queue is empty"
          message="All apps have been reviewed. Nice work!"
        />
      )}

      {/* Queue tiles */}
      {!queueLoading && queue && queue.length > 0 && (
        <div className="flex flex-col gap-3">
          {queue.map((item) => (
            <QueueTile
              key={item.id}
              item={item}
              onApprove={handleApprove}
              onReject={handleReject}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-1 py-2">
        <span className="text-2xl font-bold text-primary">{value}</span>
        <span className="text-xs uppercase text-muted-foreground">{label}</span>
      </CardContent>
    </Card>
  );
}

function QueueTile({
  item,
  onApprove,
  onReject,
}: {
  item: QueueItem;
  onApprove: (item: QueueItem) => void;
  onReject: (item: QueueItem) => void;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4">
        {/* Icon */}
        <div className="flex size-10 shrink-0 items-center justify-center rounded-lg border text-lg">
          {item.icon || "\u2699"}
        </div>

        {/* Info */}
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="truncate font-medium text-foreground">
            {item.name}
          </span>
          {item.tagline && (
            <span className="truncate text-xs text-muted-foreground">
              {item.tagline}
            </span>
          )}
          <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
            {item.category && <span>{item.category}</span>}
            {item.author_name && (
              <span>
                by {item.author_name}
                {item.author_email ? ` <${item.author_email}>` : ""}
              </span>
            )}
            {item.html_length != null && (
              <span>{(item.html_length / 1024).toFixed(1)} KB</span>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex shrink-0 items-center gap-2">
          <Button
            size="sm"
            className="bg-green-600 text-white hover:bg-green-700"
            onClick={() => onApprove(item)}
          >
            <Check className="size-3.5" data-icon="inline-start" />
            Approve
          </Button>
          <Button
            size="sm"
            variant="destructive"
            onClick={() => onReject(item)}
          >
            <X className="size-3.5" data-icon="inline-start" />
            Reject
          </Button>
          <Button
            size="sm"
            variant="ghost"
            nativeButton={false}
            render={
              <a
                href={`/embed/${item.slug}`}
                target="_blank"
                rel="noopener noreferrer"
              />
            }
          >
            <ExternalLink className="size-3.5" data-icon="inline-start" />
            Preview
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default function AdminPage() {
  return (
    <AdminGate>
      <AdminDashboard />
    </AdminGate>
  );
}
