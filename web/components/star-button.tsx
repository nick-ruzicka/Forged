"use client";

import { useCallback, useState } from "react";
import { Star } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { toggleStar } from "@/lib/hooks";
import { trackMilestone } from "@/lib/milestones";

interface StarButtonProps {
  toolId: number;
  isStarred: boolean;
  size?: "sm" | "icon";
}

export function StarButton({
  toolId,
  isStarred,
  size = "icon",
}: StarButtonProps) {
  const [optimistic, setOptimistic] = useState(isStarred);
  const [loading, setLoading] = useState(false);

  // Sync optimistic state when prop changes
  if (isStarred !== optimistic && !loading) {
    setOptimistic(isStarred);
  }

  const handleClick = useCallback(
    async (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setLoading(true);
      const prev = optimistic;
      setOptimistic(!prev);

      try {
        await toggleStar(toolId, prev);
        if (!prev) {
          const msg = trackMilestone("first_star");
          if (msg) toast.success(msg);
        }
      } catch {
        setOptimistic(prev);
        toast.error("Failed to update star");
      } finally {
        setLoading(false);
      }
    },
    [toolId, optimistic],
  );

  return (
    <Button
      variant="ghost"
      size={size === "sm" ? "icon-sm" : "icon"}
      onClick={handleClick}
      disabled={loading}
      aria-label={optimistic ? "Unstar" : "Star"}
    >
      <Star
        className={cn(
          "size-4",
          optimistic
            ? "fill-yellow-400 text-yellow-400"
            : "text-text-muted",
        )}
      />
    </Button>
  );
}
