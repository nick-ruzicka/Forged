"use client";

import { cn } from "@/lib/utils";

interface AppEmbedProps {
  slug: string;
  className?: string;
}

export function AppEmbed({ slug, className }: AppEmbedProps) {
  return (
    <iframe
      src={`/apps/${slug}`}
      className={cn("h-full w-full border-0", className)}
      sandbox="allow-scripts allow-forms allow-modals allow-downloads"
      referrerPolicy="no-referrer"
      title={`App: ${slug}`}
    />
  );
}
