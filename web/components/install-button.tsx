"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Download, ArrowRight, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { installApp } from "@/lib/hooks";
import { trackMilestone } from "@/lib/milestones";

interface InstallButtonProps {
  toolId: number;
  slug: string;
  isInstalled: boolean;
  delivery?: string;
  size?: "sm" | "default" | "lg";
}

export function InstallButton({
  toolId,
  slug,
  isInstalled,
  delivery,
  size = "sm",
}: InstallButtonProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const isExternal = delivery === "external";

  const handleClick = useCallback(
    async (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();

      if (isInstalled) {
        router.push(`/apps/${slug}`);
        return;
      }

      if (isExternal) {
        router.push(`/apps/${slug}?install=1`);
        return;
      }

      setLoading(true);
      try {
        await installApp(toolId);
        const msg = trackMilestone("first_install");
        if (msg) toast.success(msg);
        router.push(`/apps/${slug}`);
      } catch {
        toast.error("Failed to install app");
      } finally {
        setLoading(false);
      }
    },
    [isInstalled, toolId, slug, router, isExternal],
  );

  if (isInstalled) {
    return (
      <Button
        variant="secondary"
        size={size}
        onClick={handleClick}
        className="gap-1.5"
      >
        <Check className="size-3.5 text-green-400" />
        Installed
        <ArrowRight className="size-3 text-text-muted" />
      </Button>
    );
  }

  if (loading) {
    return (
      <Button variant="default" size={size} disabled className="gap-1.5">
        <Loader2 className="size-3.5 animate-spin" />
        Installing…
      </Button>
    );
  }

  return (
    <Button
      variant="default"
      size={size}
      onClick={handleClick}
      className="gap-1.5"
    >
      {isExternal ? (
        <>
          <Download className="size-3.5" />
          Install
        </>
      ) : (
        <>
          <ArrowRight className="size-3.5" />
          Get App
        </>
      )}
    </Button>
  );
}
