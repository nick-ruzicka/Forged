"use client";

import { useCallback, useState } from "react";
import { ArrowUp, ChevronRight, Copy, Download, ExternalLink } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { upvoteSkill, subscribeSkill, downloadSkillUrl } from "@/lib/api";
import type { Skill } from "@/lib/types";

interface SkillCardProps {
  skill: Skill;
}

export function SkillCard({ skill }: SkillCardProps) {
  const [upvoted, setUpvoted] = useState(false);
  const [localUpvotes, setLocalUpvotes] = useState(skill.upvotes);
  const [subscribed, setSubscribed] = useState(false);
  const [installOpen, setInstallOpen] = useState(false);

  const handleUpvote = useCallback(async () => {
    if (upvoted) {
      toast("Already upvoted");
      return;
    }
    try {
      await upvoteSkill(skill.id);
      setUpvoted(true);
      setLocalUpvotes((c) => c + 1);
    } catch {
      toast.error("Failed to upvote");
    }
  }, [upvoted, skill.id]);

  const handleSubscribe = useCallback(async () => {
    if (subscribed) return;
    try {
      await subscribeSkill(skill.id);
      setSubscribed(true);
      toast(`Subscribed to ${skill.title}. Run forge sync to install.`);
    } catch {
      toast.error("Failed to subscribe");
    }
  }, [subscribed, skill.id, skill.title]);

  const installCommand = `curl -sL ${typeof window !== "undefined" ? window.location.origin : ""}${downloadSkillUrl(skill.id)} -o SKILL.md`;

  const handleCopyInstall = useCallback(async () => {
    await navigator.clipboard.writeText(installCommand);
    toast("Install command copied");
  }, [installCommand]);

  const promptPreview = skill.prompt_text
    ? skill.prompt_text.slice(0, 300)
    : "";

  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-5 transition-all duration-200 hover:border-border-strong hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.3)]">
      {/* Header */}
      <div className="flex items-start justify-between">
        {skill.category && (
          <Badge variant="secondary">{skill.category}</Badge>
        )}
        <span className="text-[11px] text-text-muted tabular-nums">
          {skill.copy_count} downloads
        </span>
      </div>

      {/* Title + use case */}
      <div className="flex flex-col gap-1.5">
        <Link
          href={`/skills/${skill.id}`}
          className="text-[15px] font-semibold tracking-tight text-foreground hover:text-primary transition-colors"
          onClick={(e) => e.stopPropagation()}
        >
          {skill.title}
        </Link>
        {skill.use_case && (
          <span className="text-[13px] leading-snug text-text-secondary">{skill.use_case}</span>
        )}
      </div>

      {/* Prompt preview */}
      {promptPreview && (
        <pre className="line-clamp-4 whitespace-pre-wrap rounded-lg bg-surface-2 p-3 font-mono text-xs leading-relaxed text-text-muted ring-1 ring-border">
          {promptPreview}
        </pre>
      )}

      {/* Install command collapsible */}
      <div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setInstallOpen(!installOpen)}
            className="flex items-center gap-1 text-xs text-text-muted hover:text-foreground transition-colors"
          >
            <ChevronRight
              className={cn(
                "size-3 transition-transform",
                installOpen && "rotate-90",
              )}
            />
            Install with curl
          </button>
          {installOpen && (
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={handleCopyInstall}
            >
              <Copy />
            </Button>
          )}
        </div>
        {installOpen && (
          <pre className="mt-1 overflow-x-auto rounded-md bg-muted p-2 font-mono text-xs text-text-secondary">
            {installCommand}
          </pre>
        )}
      </div>

      {/* Footer */}
      <div className="mt-auto flex flex-wrap items-center gap-2 border-t border-border pt-4">
        {/* Upvote */}
        <Button
          variant={upvoted ? "default" : "outline"}
          size="xs"
          onClick={handleUpvote}
        >
          <ArrowUp data-icon="inline-start" />
          {localUpvotes}
        </Button>

        {/* Author */}
        <span className="text-xs text-text-muted">
          {skill.source_url ? (
            <a
              href={skill.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-foreground inline-flex items-center gap-0.5"
              onClick={(e) => e.stopPropagation()}
            >
              {skill.author_name || "Source"}
              <ExternalLink className="size-3" />
            </a>
          ) : (
            <>by {skill.author_name || "Anonymous"}</>
          )}
        </span>

        <div className="ml-auto flex items-center gap-1">
          {/* Subscribe */}
          <Button
            variant={subscribed ? "ghost" : "outline"}
            size="xs"
            onClick={handleSubscribe}
            className={subscribed ? "text-green-500" : ""}
          >
            {subscribed ? "✓ Subscribed" : "+ Subscribe"}
          </Button>

          {/* Download */}
          <Button
            variant="ghost"
            size="icon-xs"
            nativeButton={false}
            render={
              <a
                href={downloadSkillUrl(skill.id)}
                download
              />
            }
          >
            <Download />
          </Button>
        </div>
      </div>
    </div>
  );
}
