"use client";

import { use, useCallback, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowUp,
  Check,
  Copy,
  Download,
  ExternalLink,
  Link2,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { useMySkills, useSkills } from "@/lib/hooks";
import {
  downloadSkillUrl,
  unsubscribeSkill,
  upvoteSkill,
  subscribeSkill,
} from "@/lib/api";
export default function SkillDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const skillId = Number(id);
  const router = useRouter();
  const { data: mySkills, isLoading: loadingMy, mutate } = useMySkills();
  const { data: allSkills, isLoading: loadingAll } = useSkills();
  const isLoading = loadingMy && loadingAll;
  const found = mySkills?.find((s) => s.id === skillId)
    ?? allSkills?.find((s) => s.id === skillId);
  const isSubscribed = !!mySkills?.find((s) => s.id === skillId);

  const [copied, setCopied] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);
  const [upvoted, setUpvoted] = useState(false);

  const handleCopyPrompt = useCallback(async () => {
    if (!found?.prompt_text) return;
    await navigator.clipboard.writeText(found.prompt_text);
    setCopied(true);
    toast.success("Prompt copied to clipboard");
    setTimeout(() => setCopied(false), 2000);
  }, [found]);

  const handleCopyLink = useCallback(async () => {
    await navigator.clipboard.writeText(window.location.href);
    setLinkCopied(true);
    toast.success("Link copied");
    setTimeout(() => setLinkCopied(false), 2000);
  }, []);

  const handleUpvote = useCallback(async () => {
    if (upvoted) return;
    try {
      await upvoteSkill(skillId);
      setUpvoted(true);
      toast.success("Upvoted");
    } catch {
      toast.error("Failed to upvote");
    }
  }, [skillId, upvoted]);

  const handleUnsubscribe = useCallback(async () => {
    try {
      await unsubscribeSkill(skillId);
      toast("Unsubscribed");
      mutate();
      router.push("/my-forge");
    } catch {
      toast.error("Failed to unsubscribe");
    }
  }, [skillId, mutate, router]);

  const handleSubscribe = useCallback(async () => {
    try {
      await subscribeSkill(skillId);
      toast.success("Subscribed! This skill is now in your collection.");
      mutate();
    } catch {
      toast.error("Failed to subscribe");
    }
  }, [skillId, mutate]);

  if (isLoading) {
    return (
      <div className="flex flex-col">
        <div className="flex flex-col gap-6 border-b border-border bg-gradient-to-b from-surface-2/80 to-transparent p-6 md:p-8">
          <Skeleton className="h-4 w-24 rounded-lg" />
          <div className="flex flex-col gap-3">
            <Skeleton className="h-8 w-64 rounded-lg" />
            <Skeleton className="h-4 w-96 rounded-lg" />
            <div className="flex gap-2">
              <Skeleton className="h-6 w-20 rounded-full" />
              <Skeleton className="h-6 w-24 rounded-full" />
            </div>
          </div>
        </div>
        <div className="p-6 md:p-8">
          <Skeleton className="h-96 w-full rounded-xl" />
        </div>
      </div>
    );
  }

  if (!found) {
    return (
      <div className="p-6 md:p-8">
        <EmptyState
          icon={<span className="text-3xl">📄</span>}
          title="Skill not found"
          message="This skill doesn't exist or you haven't subscribed to it yet."
          actionLabel="Browse Skills"
          actionHref="/skills"
        />
      </div>
    );
  }

  const promptLines = found.prompt_text?.split("\n").length ?? 0;
  const promptChars = found.prompt_text?.length ?? 0;

  return (
    <div className="flex flex-col">
      {/* Hero */}
      <div className="relative flex flex-col gap-6 border-b border-border bg-gradient-to-b from-surface-2/80 via-surface-2/30 to-transparent p-6 md:p-8">
        <div className="absolute top-12 left-12 size-32 rounded-full bg-primary/[0.04] blur-3xl pointer-events-none" />

        <Link
          href={isSubscribed ? "/my-forge" : "/skills"}
          className="relative text-[13px] text-text-muted hover:text-foreground transition-colors w-fit"
        >
          ← {isSubscribed ? "My Skills" : "Browse Skills"}
        </Link>

        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-5">
            <div className="flex size-14 items-center justify-center rounded-2xl bg-card text-3xl ring-1 ring-border shadow-lg">
              {found.category === "Development" ? "⚡" :
               found.category === "Testing" ? "🧪" :
               found.category === "Debugging" ? "🐛" :
               found.category === "Planning" ? "📋" :
               found.category === "Code Review" ? "👁" :
               found.category === "Documents" ? "📝" : "📄"}
            </div>
            <div className="flex flex-col gap-2">
              <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
                {found.title}
              </h1>
              {found.use_case && (
                <p className="text-[15px] leading-relaxed text-text-secondary max-w-xl">
                  {found.use_case}
                </p>
              )}
              <div className="flex flex-wrap items-center gap-2">
                {found.category && (
                  <Badge variant="secondary">{found.category}</Badge>
                )}
                <span className="text-xs text-text-muted">
                  by {found.author_name || "Anonymous"}
                </span>
                {found.subscribed_at && (
                  <>
                    <span className="text-text-muted/40">·</span>
                    <span className="text-xs text-text-muted">
                      Subscribed {formatTimeAgo(found.subscribed_at)}
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleUpvote} disabled={upvoted}>
              <ArrowUp data-icon="inline-start" />
              {upvoted ? "Upvoted" : "Upvote"}
            </Button>
            <Button
              variant="default"
              size="sm"
              nativeButton={false}
              render={<a href={downloadSkillUrl(skillId)} download />}
            >
              <Download data-icon="inline-start" />
              Download .md
            </Button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-col gap-8 p-6 md:p-8 lg:flex-row">
        {/* Main: prompt content */}
        <div className="flex flex-1 flex-col gap-5 min-w-0">
          <div className="flex items-center justify-between">
            <h3 className="text-[13px] font-semibold uppercase tracking-widest text-text-muted/70">
              Prompt
            </h3>
            <Button
              variant="ghost"
              size="xs"
              onClick={handleCopyPrompt}
              className="gap-1.5"
            >
              {copied ? (
                <Check className="size-3.5 text-green-400" />
              ) : (
                <Copy className="size-3.5" />
              )}
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
          <div className="rounded-2xl border border-border bg-card p-6 ring-1 ring-border/50">
            <pre className="whitespace-pre-wrap font-mono text-[13px] leading-[1.8] text-text-secondary selection:bg-primary/20">
              {found.prompt_text || "No prompt content available."}
            </pre>
          </div>
        </div>

        {/* Sidebar */}
        <div className="flex flex-col gap-4 lg:w-64 lg:shrink-0">
          {/* Stats card */}
          <div className="flex flex-col rounded-2xl border border-border bg-card p-5">
            <h4 className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-text-muted/70">
              Details
            </h4>
            <SidebarRow label="Upvotes" value={String(found.upvotes + (upvoted ? 1 : 0))} />
            <SidebarRow label="Downloads" value={String(found.copy_count)} />
            <SidebarRow label="Lines" value={String(promptLines)} />
            <SidebarRow label="Characters" value={formatNumber(promptChars)} />
            {found.created_at && (
              <SidebarRow label="Published" value={formatDate(found.created_at)} />
            )}
          </div>

          {/* Quick actions */}
          <div className="flex flex-col gap-2">
            <Button variant="outline" size="sm" onClick={handleCopyPrompt} className="w-full justify-start gap-2">
              <Copy className="size-3.5" />
              Copy prompt to clipboard
            </Button>
            <Button variant="outline" size="sm" onClick={handleCopyLink} className="w-full justify-start gap-2">
              {linkCopied ? <Check className="size-3.5 text-green-400" /> : <Link2 className="size-3.5" />}
              {linkCopied ? "Link copied" : "Copy share link"}
            </Button>
            {found.source_url && (
              <Button
                variant="outline"
                size="sm"
                nativeButton={false}
                render={<a href={found.source_url} target="_blank" rel="noopener noreferrer" />}
                className="w-full justify-start gap-2"
              >
                <ExternalLink className="size-3.5" />
                View source
              </Button>
            )}
            {isSubscribed ? (
              <Button
                variant="outline"
                size="sm"
                onClick={handleUnsubscribe}
                className="w-full justify-start gap-2 hover:border-destructive/40 hover:text-destructive"
              >
                <Trash2 className="size-3.5" />
                Unsubscribe
              </Button>
            ) : (
              <Button
                variant="default"
                size="sm"
                onClick={handleSubscribe}
                className="w-full justify-start gap-2"
              >
                <Download className="size-3.5" />
                Add to my skills
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function SidebarRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
      <span className="text-xs text-text-muted">{label}</span>
      <span className="text-xs font-medium text-foreground tabular-nums">{value}</span>
    </div>
  );
}

function formatTimeAgo(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return Math.floor(diff / 60) + "m ago";
  if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
  if (diff < 604800) return Math.floor(diff / 86400) + "d ago";
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function formatNumber(n: number): string {
  if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, "") + "k";
  return String(n);
}
