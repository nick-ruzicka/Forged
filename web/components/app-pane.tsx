"use client";

import { ExternalLink, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AppEmbed } from "@/components/app-embed";

interface AppPaneProps {
  slug: string;
  name: string;
  onClose: () => void;
}

export function AppPane({ slug, name, onClose }: AppPaneProps) {
  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-background/90 backdrop-blur-lg animate-fade-in-up">
      {/* Top bar */}
      <div className="flex h-11 items-center justify-between border-b border-border bg-surface/80 backdrop-blur-md px-4">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-foreground">{name}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Button
            variant="ghost"
            size="xs"
            nativeButton={false}
            render={
              <a
                href={`/embed/${slug}`}
                target="_blank"
                rel="noopener noreferrer"
              />
            }
          >
            <ExternalLink data-icon="inline-start" />
            Full screen
          </Button>
          <div className="h-4 w-px bg-border" />
          <Button variant="ghost" size="icon-sm" onClick={onClose}>
            <X />
          </Button>
        </div>
      </div>

      {/* Embed */}
      <div className="flex-1">
        <AppEmbed slug={slug} className="h-full w-full" />
      </div>
    </div>
  );
}
