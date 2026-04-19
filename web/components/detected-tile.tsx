"use client";

import { EyeOff } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { UserItem } from "@/lib/types";

export function DetectedTile({
  item,
  onHide,
}: {
  item: UserItem;
  onHide: () => void;
}) {
  return (
    <div className="group flex items-center gap-3 rounded-xl border border-dashed border-border bg-card p-3 transition-colors hover:border-border-strong">
      <span className="text-2xl">📦</span>
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-sm font-medium text-foreground">
          {item.name || item.detected_bundle_id || "Unknown app"}
        </span>
        <span className="truncate text-xs text-text-secondary">
          Detected on your machine
        </span>
        <Badge variant="outline" className="mt-1 w-fit text-[10px]">
          Detected
        </Badge>
      </div>
      <Button
        variant="ghost"
        size="icon-xs"
        className="opacity-0 group-hover:opacity-100 hover:text-destructive"
        onClick={onHide}
        aria-label="Hide"
      >
        <EyeOff />
      </Button>
    </div>
  );
}
