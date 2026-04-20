"use client";

import { cn } from "@/lib/utils";
import { getUserId } from "@/lib/api";

interface AppEmbedProps {
  slug: string;
  preview?: boolean;
  className?: string;
  allowSameOrigin?: boolean;
}

export function AppEmbed({ slug, preview, className, allowSameOrigin }: AppEmbedProps) {
  const userId = getUserId();
  const params = new URLSearchParams();
  if (userId) params.set("user", userId);
  if (preview) params.set("preview", "true");
  const qs = params.toString();

  // Apps that iframe to external VPS/servers need allow-same-origin
  // for the inner iframe to load. User-submitted HTML apps do NOT
  // get this — it would let them access Forge's cookies/storage.
  const sandbox = allowSameOrigin
    ? "allow-scripts allow-forms allow-modals allow-downloads allow-same-origin"
    : "allow-scripts allow-forms allow-modals allow-downloads";

  return (
    <iframe
      src={`/embed/${slug}${qs ? `?${qs}` : ""}`}
      className={cn("h-full w-full border-0", className)}
      sandbox={sandbox}
      title={`App: ${slug}`}
    />
  );
}
