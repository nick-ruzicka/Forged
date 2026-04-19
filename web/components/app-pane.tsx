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
    <div className="fixed inset-0 z-50 flex flex-col bg-background/80 backdrop-blur">
      {/* Top bar */}
      <div className="flex items-center justify-between border-b border-border bg-background px-4 py-2">
        <span className="text-sm font-medium text-foreground">{name}</span>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="xs"
            render={
              <a
                href={`/apps/${slug}`}
                target="_blank"
                rel="noopener noreferrer"
              />
            }
          >
            <ExternalLink data-icon="inline-start" />
            Full screen
          </Button>
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
