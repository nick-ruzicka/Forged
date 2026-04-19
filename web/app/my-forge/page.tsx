"use client";

import { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { ExternalLink, LogOut, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyState } from "@/components/empty-state";
import { AppPane } from "@/components/app-pane";
import { useMyItems, useMyStars, useMySkills, useMySubmissions, useAgentAvailable, useRunningApps, uninstallApp } from "@/lib/hooks";
import { launchItem, removeStar, launchApp, unsubscribeSkill } from "@/lib/api";
import { useUser } from "@/lib/user-context";
import type { UserItem, Star, Skill } from "@/lib/types";

export default function MyForgePage() {
  const { name, email, clearIdentity, setIdentity } = useUser();
  const { data: items, mutate: mutateItems } = useMyItems();
  const { data: stars, mutate: mutateStars } = useMyStars();
  const { data: skills, mutate: mutateSkills } = useMySkills();
  const { data: submissions } = useMySubmissions();
  const { data: agentAvail } = useAgentAvailable(true);
  const { data: runningData } = useRunningApps(agentAvail ?? false);

  // App pane state
  const [paneSlug, setPaneSlug] = useState<string | null>(null);
  const [paneName, setPaneName] = useState("");

  const openPane = useCallback((slug: string, appName: string) => {
    setPaneSlug(slug);
    setPaneName(appName);
  }, []);

  const handleRemoveItem = useCallback(
    async (toolId: number) => {
      try {
        await uninstallApp(toolId);
        toast("App removed");
      } catch {
        toast.error("Failed to remove");
        mutateItems();
      }
    },
    [mutateItems],
  );

  const handleLaunch = useCallback(async (toolId: number, slug: string, name: string) => {
    try {
      await Promise.all([
        launchItem(toolId),
        launchApp(slug, name),
      ]);
    } catch {
      toast.error("Failed to launch");
    }
  }, []);

  const handleUnsave = useCallback(
    async (toolId: number) => {
      try {
        await removeStar(toolId);
        mutateStars();
        toast("Removed from saved");
      } catch {
        toast.error("Failed to remove");
      }
    },
    [mutateStars],
  );

  const handleUnsubscribeSkill = useCallback(
    async (skillId: number) => {
      try {
        await unsubscribeSkill(skillId);
        mutateSkills();
        toast("Unsubscribed from skill");
      } catch {
        toast.error("Failed to unsubscribe");
      }
    },
    [mutateSkills],
  );

  const handleSetEmail = useCallback(() => {
    const newEmail = prompt("Enter your email:");
    if (newEmail) {
      setIdentity(name || "User", newEmail);
      toast("Identity updated");
    }
  }, [name, setIdentity]);

  return (
    <div className="flex flex-col gap-8 p-6 md:p-8">
      {/* Header */}
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">My Forge</h1>
        <p className="text-[15px] text-text-secondary">
          Everything you've installed, saved, and subscribed to.
        </p>
      </div>

      {/* Identity row */}
      <div className="flex items-center gap-3 rounded-2xl border border-border bg-card p-4">
        <div className="flex size-10 items-center justify-center rounded-full bg-gradient-to-br from-primary/30 to-primary/10 text-sm font-semibold text-primary ring-1 ring-primary/20">
          {(name || email || "U").slice(0, 2).toUpperCase()}
        </div>
        {name || email ? (
          <div className="flex flex-1 items-center justify-between">
            <div className="flex flex-col">
              {name && <span className="text-sm font-medium text-foreground">{name}</span>}
              {email && <span className="text-xs text-text-muted">{email}</span>}
            </div>
            <Button variant="ghost" size="xs" onClick={clearIdentity}>
              <LogOut data-icon="inline-start" />
              Sign out
            </Button>
          </div>
        ) : (
          <Button variant="outline" size="sm" onClick={handleSetEmail}>
            Set email
          </Button>
        )}
      </div>

      {/* Tabs */}
      <Tabs defaultValue="installed">
        <TabsList>
          <TabsTrigger value="installed">
            Installed
            {items && items.length > 0 && (
              <Badge variant="secondary" className="ml-1">
                {items.length}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="saved">
            Saved
            {stars && stars.length > 0 && (
              <Badge variant="secondary" className="ml-1">
                {stars.length}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="skills">
            Skills
            {skills && skills.length > 0 && (
              <Badge variant="secondary" className="ml-1">
                {skills.length}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="submissions">
            Submissions
            {submissions && submissions.length > 0 && (
              <Badge variant="secondary" className="ml-1">
                {submissions.length}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>

        {/* Installed tab */}
        <TabsContent value="installed">
          {(!items || items.length === 0) ? (
            <EmptyState
              icon={<span className="text-3xl">📦</span>}
              title="No apps installed"
              message="Browse the catalog and install your first app."
              actionLabel="Browse Apps"
              actionHref="/"
            />
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {items.map((item) => (
                <InstalledTile
                  key={item.id}
                  item={item}
                  isRunning={item.delivery === "external" && !!runningData?.apps.find(a => a.slug === item.slug && a.running)}
                  onOpen={() => {
                    if (item.delivery === "external" && item.slug) {
                      handleLaunch(item.tool_id ?? item.id, item.slug, item.name || item.slug);
                    } else if (item.slug) {
                      openPane(item.slug, item.name || item.slug);
                    }
                  }}
                  onRemove={() => handleRemoveItem(item.tool_id ?? item.id)}
                />
              ))}
            </div>
          )}
        </TabsContent>

        {/* Saved tab */}
        <TabsContent value="saved">
          {(!stars || stars.length === 0) ? (
            <EmptyState
              icon={<span className="text-3xl">⭐</span>}
              title="No saved apps"
              message="Star apps from the catalog to save them here."
              actionLabel="Browse Apps"
              actionHref="/"
            />
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {stars.map((star) => (
                <SavedTile
                  key={star.id}
                  star={star}
                  onUnsave={() => handleUnsave(star.tool_id ?? star.id)}
                />
              ))}
            </div>
          )}
        </TabsContent>

        {/* Skills tab */}
        <TabsContent value="skills">
          {(!skills || skills.length === 0) ? (
            <EmptyState
              icon={<span className="text-3xl">📄</span>}
              title="No skills yet"
              message="Subscribe to skills to build your prompt library. Share them with your team."
              actionLabel="Browse Skills"
              actionHref="/skills"
            />
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {skills.map((skill) => (
                <SkillTile
                  key={skill.id}
                  skill={skill}
                  onUnsubscribe={() => handleUnsubscribeSkill(skill.id)}
                />
              ))}
            </div>
          )}
        </TabsContent>

        {/* Submissions tab */}
        <TabsContent value="submissions">
          {(!submissions || submissions.length === 0) ? (
            <EmptyState
              icon={<span className="text-3xl">📝</span>}
              title="No submissions"
              message="Submit a skill from the Skills page to see it here."
              actionLabel="Browse Skills"
              actionHref="/skills"
            />
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {submissions.map((skill) => (
                <SubmissionTile key={skill.id} skill={skill} />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* App Pane overlay */}
      {paneSlug && (
        <AppPane
          slug={paneSlug}
          name={paneName}
          onClose={() => setPaneSlug(null)}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function InstalledTile({
  item,
  isRunning,
  onOpen,
  onRemove,
}: {
  item: UserItem;
  isRunning?: boolean;
  onOpen: () => void;
  onRemove: () => void;
}) {
  const lastOpened = item.last_opened_at
    ? formatTimeAgo(item.last_opened_at)
    : null;

  return (
    <div className="group flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 transition-all duration-150 hover:border-border-strong hover:shadow-[0_4px_20px_rgba(0,0,0,0.2)]">
      <div className="flex items-start gap-3">
        <div className="relative shrink-0">
          <div className="flex size-11 items-center justify-center rounded-xl bg-surface-2 text-xl ring-1 ring-border">
            {item.icon || "📦"}
          </div>
          {item.delivery === "external" && (
            <span className={cn(
              "absolute -right-0.5 -top-0.5 size-2.5 rounded-full ring-2 ring-card",
              isRunning ? "bg-green-500 shadow-[0_0_6px_theme(colors.green.500)] animate-pulse" : "bg-neutral-600"
            )} />
          )}
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="truncate text-[14px] font-semibold text-foreground">
            {item.name || item.slug}
          </span>
          {item.tagline && (
            <span className="truncate text-[12px] text-text-secondary">
              {item.tagline}
            </span>
          )}
        </div>
        <Button
          variant="ghost"
          size="icon-xs"
          className="shrink-0 opacity-0 group-hover:opacity-100 hover:text-destructive transition-opacity"
          onClick={onRemove}
        >
          <Trash2 />
        </Button>
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-[11px] text-text-muted">
          {lastOpened && <span>Opened {lastOpened}</span>}
          {!lastOpened && item.open_count != null && item.open_count > 0 && (
            <span>{item.open_count} opens</span>
          )}
          {item.delivery === "external" && (
            <Badge variant="outline" className="text-[10px]">Desktop</Badge>
          )}
        </div>
        <Button
          variant={isRunning ? "default" : "outline"}
          size="xs"
          onClick={onOpen}
          className={isRunning ? "bg-green-500/15 text-green-400 border border-green-500/30 hover:bg-green-500/25 shadow-none" : ""}
        >
          {item.delivery === "external" ? (
            <>
              <ExternalLink data-icon="inline-start" />
              {isRunning ? "Focus" : "Launch"}
            </>
          ) : (
            "Open"
          )}
        </Button>
      </div>
    </div>
  );
}

function SavedTile({
  star,
  onUnsave,
}: {
  star: Star;
  onUnsave: () => void;
}) {
  return (
    <div className="group flex items-center gap-3 rounded-2xl border border-border bg-card p-4 transition-all duration-150 hover:border-border-strong hover:shadow-[0_4px_20px_rgba(0,0,0,0.2)]">
      <div className="flex size-10 items-center justify-center rounded-xl bg-surface-2 text-xl ring-1 ring-border">
        {star.icon || "📦"}
      </div>
      <div className="flex min-w-0 flex-1 flex-col">
        <Link
          href={star.slug ? `/apps/${star.slug}` : "#"}
          className="truncate text-sm font-medium text-foreground hover:underline"
        >
          {star.name || star.slug || `#${star.tool_id ?? star.id}`}
        </Link>
        {star.tagline && (
          <span className="truncate text-xs text-text-secondary">
            {star.tagline}
          </span>
        )}
      </div>
      <Button
        variant="ghost"
        size="xs"
        className="opacity-0 group-hover:opacity-100 hover:text-destructive"
        onClick={onUnsave}
      >
        <X data-icon="inline-start" />
        Unsave
      </Button>
    </div>
  );
}

function SubmissionTile({ skill }: { skill: Skill }) {
  const statusConfig: Record<string, { label: string; className: string }> = {
    approved: { label: "Approved", className: "bg-green-500/10 text-green-500 ring-green-500/20" },
    pending: { label: "Pending review", className: "bg-yellow-500/10 text-yellow-500 ring-yellow-500/20" },
    needs_revision: { label: "Needs revision", className: "bg-orange-500/10 text-orange-500 ring-orange-500/20" },
    blocked: { label: "Blocked", className: "bg-red-500/10 text-red-500 ring-red-500/20" },
  };
  const status = statusConfig[skill.review_status || "pending"] || statusConfig.pending;

  return (
    <div className="flex items-center gap-3 rounded-2xl border border-border bg-card p-4">
      <div className="flex size-10 items-center justify-center rounded-xl bg-surface-2 text-xl ring-1 ring-border">
        📄
      </div>
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-sm font-medium text-foreground">
          {skill.title}
        </span>
        <div className="flex items-center gap-2 text-xs text-text-muted">
          {skill.category && <span>{skill.category}</span>}
          <Badge variant="outline" className={cn("text-[10px] ring-1", status.className)}>
            {status.label}
          </Badge>
        </div>
      </div>
    </div>
  );
}

function SkillTile({ skill, onUnsubscribe }: { skill: Skill; onUnsubscribe: () => void }) {
  const preview = skill.prompt_text
    ? skill.prompt_text.slice(0, 120).replace(/\n/g, " ") + (skill.prompt_text.length > 120 ? "…" : "")
    : null;

  return (
    <Link
      href={`/skills/${skill.id}`}
      className="group flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 transition-all duration-150 hover:border-border-strong hover:-translate-y-0.5 hover:shadow-[0_4px_20px_rgba(0,0,0,0.2)]"
    >
      <div className="flex items-start gap-3">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-surface-2 text-xl ring-1 ring-border">
          📄
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="truncate text-[14px] font-semibold text-foreground">
            {skill.title}
          </span>
          <div className="flex items-center gap-2 text-[11px] text-text-muted">
            {skill.category && <Badge variant="secondary" className="text-[10px]">{skill.category}</Badge>}
            {skill.author_name && <span>by {skill.author_name}</span>}
          </div>
        </div>
        <Button
          variant="ghost"
          size="icon-xs"
          className="shrink-0 opacity-0 group-hover:opacity-100 hover:text-destructive transition-opacity"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onUnsubscribe();
          }}
        >
          <Trash2 />
        </Button>
      </div>
      {preview && (
        <p className="line-clamp-2 rounded-lg bg-surface-2/50 px-3 py-2 font-mono text-[11px] leading-relaxed text-text-muted ring-1 ring-border/50">
          {preview}
        </p>
      )}
      <div className="flex items-center justify-between text-[11px] text-text-muted">
        <span>{skill.upvotes} upvotes · {skill.copy_count} downloads</span>
        {skill.subscribed_at && (
          <span>Subscribed {formatTimeAgo(skill.subscribed_at)}</span>
        )}
      </div>
    </Link>
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
