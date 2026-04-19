"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Download, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { installApp } from "@/lib/hooks";
import { trackMilestone } from "@/lib/milestones";

interface InstallButtonProps {
  toolId: number;
  slug: string;
  isInstalled: boolean;
  delivery?: string;
}

export function InstallButton({
  toolId,
  slug,
  isInstalled,
  delivery,
}: InstallButtonProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  const handleClick = useCallback(
    async (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();

      if (isInstalled) {
        router.push(`/apps/${slug}`);
        return;
      }

      // External apps: navigate to detail page and auto-trigger install
      if (delivery === "external") {
        router.push(`/apps/${slug}?install=1`);
        return;
      }

      setLoading(true);
      try {
        await installApp(toolId);
        const msg = trackMilestone("first_install");
        if (msg) toast.success(msg);
      } catch {
        toast.error("Failed to install app");
      } finally {
        setLoading(false);
      }
    },
    [isInstalled, toolId, slug, router],
  );

  if (isInstalled) {
    return (
      <Button variant="secondary" size="sm" onClick={handleClick}>
        <Check className="size-3.5" data-icon="inline-start" />
        Open
      </Button>
    );
  }

  const isExternal = delivery === "external";

  return (
    <Button
      variant="default"
      size="sm"
      onClick={handleClick}
      disabled={loading}
    >
      {isExternal ? (
        <Download className="size-3.5" data-icon="inline-start" />
      ) : (
        <ExternalLink className="size-3.5" data-icon="inline-start" />
      )}
      {isExternal ? "Install" : "Open"}
    </Button>
  );
}
