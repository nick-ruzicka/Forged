"use client";

import { cn } from "@/lib/utils";
import { getUserId } from "@/lib/api";

interface AppEmbedProps {
  slug: string;
  preview?: boolean;
  className?: string;
}

export function AppEmbed({ slug, preview, className }: AppEmbedProps) {
  const userId = getUserId();
  const params = new URLSearchParams();
  if (userId) params.set("user", userId);
  if (preview) params.set("preview", "true");
  const qs = params.toString();

  return (
    <iframe
      src={`/embed/${slug}${qs ? `?${qs}` : ""}`}
      className={cn("h-full w-full border-0", className)}
      sandbox="allow-scripts allow-forms allow-modals allow-downloads"
      title={`App: ${slug}`}
    />
  );
}
