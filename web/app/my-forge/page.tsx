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
import { useMyItems, useMyStars, useMySkills, useAgentAvailable, uninstallApp } from "@/lib/hooks";
import { launchItem, removeStar } from "@/lib/api";
import { useUser } from "@/lib/user-context";
import type { UserItem, Star, Skill } from "@/lib/types";

export default function MyForgePage() {
  const { name, email, clearIdentity, setIdentity } = useUser();
  const { data: items, mutate: mutateItems } = useMyItems();
  const { data: stars, mutate: mutateStars } = useMyStars();
  const { data: skills } = useMySkills();
  useAgentAvailable(true);

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

  const handleLaunch = useCallback(async (toolId: number) => {
    try {
      await launchItem(toolId);
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

  const handleSetEmail = useCallback(() => {
    const newEmail = prompt("Enter your email:");
    if (newEmail) {
      setIdentity(name || "User", newEmail);
      toast("Identity updated");
    }
  }, [name, setIdentity]);

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold text-foreground">My Forge</h1>
        <p className="text-sm text-text-secondary">
          Your installed apps, saved items, and skills.
        </p>
      </div>

      {/* Identity row */}
      <div className="flex items-center gap-2">
        {name || email ? (
          <>
            <span className="text-sm text-foreground">
              {name || email}
            </span>
            <Button variant="ghost" size="xs" onClick={clearIdentity}>
              <LogOut data-icon="inline-start" />
              Sign out
            </Button>
          </>
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
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
              {items.map((item) => (
                <InstalledTile
                  key={item.id}
                  item={item}
                  onOpen={() => {
                    if (item.delivery === "external") {
                      handleLaunch(item.tool_id);
                    } else if (item.slug) {
                      openPane(item.slug, item.name || item.slug);
                    }
                  }}
                  onRemove={() => handleRemoveItem(item.tool_id)}
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
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
              {stars.map((star) => (
                <SavedTile
                  key={star.id}
                  star={star}
                  onUnsave={() => handleUnsave(star.tool_id)}
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
              message="Subscribe to skills from the Skills page."
              actionLabel="Browse Skills"
              actionHref="/skills"
            />
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
              {skills.map((skill) => (
                <SkillTile key={skill.id} skill={skill} />
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
  onOpen,
  onRemove,
}: {
  item: UserItem;
  onOpen: () => void;
  onRemove: () => void;
}) {
  return (
    <div className="group flex items-center gap-3 rounded-xl border border-border bg-card p-3 transition-colors hover:border-border-strong">
      <span className="text-2xl">{item.icon || "📦"}</span>
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-sm font-medium text-foreground">
          {item.name || item.slug}
        </span>
        {item.tagline && (
          <span className="truncate text-xs text-text-secondary">
            {item.tagline}
          </span>
        )}
        <div className="flex items-center gap-2 text-xs text-text-muted">
          {item.open_count != null && <span>{item.open_count} opens</span>}
          {item.delivery === "external" && (
            <Badge variant="outline" className="text-[10px]">
              External
            </Badge>
          )}
        </div>
      </div>
      <div className="flex items-center gap-1">
        <Button variant="outline" size="xs" onClick={onOpen}>
          {item.delivery === "external" ? (
            <>
              <ExternalLink data-icon="inline-start" />
              Launch
            </>
          ) : (
            "Open"
          )}
        </Button>
        <Button
          variant="ghost"
          size="icon-xs"
          className="opacity-0 group-hover:opacity-100 hover:text-destructive"
          onClick={onRemove}
        >
          <Trash2 />
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
    <div className="group flex items-center gap-3 rounded-xl border border-border bg-card p-3 transition-colors hover:border-border-strong">
      <span className="text-2xl">{star.icon || "📦"}</span>
      <div className="flex min-w-0 flex-1 flex-col">
        <Link
          href={star.slug ? `/apps/${star.slug}` : "#"}
          className="truncate text-sm font-medium text-foreground hover:underline"
        >
          {star.name || star.slug || `#${star.tool_id}`}
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

function SkillTile({ skill }: { skill: Skill }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-border bg-card p-3">
      <span className="text-2xl">📄</span>
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-sm font-medium text-foreground">
          {skill.title}
        </span>
        <div className="flex items-center gap-2 text-xs text-text-muted">
          {skill.category && <span>{skill.category}</span>}
          {skill.author_name && <span>by {skill.author_name}</span>}
        </div>
      </div>
    </div>
  );
}
