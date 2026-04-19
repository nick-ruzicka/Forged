"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowUp,
  Check,
  Copy,
  Download,
  ExternalLink,
  Search,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CategoryPills } from "@/components/category-pills";
import { EmptyState } from "@/components/empty-state";
import { SubmitSkillDialog } from "@/components/submit-skill-dialog";
import { useSkills, useMySkills } from "@/lib/hooks";
import {
  subscribeSkill,
  unsubscribeSkill,
  downloadSkillUrl,
  upvoteSkill,
} from "@/lib/api";
import type { Skill } from "@/lib/types";

const SKILL_CATEGORIES = [
  "Development",
  "Testing",
  "Debugging",
  "Planning",
  "Code Review",
  "Documents",
  "Other",
];

type SortOption = "upvotes" | "newest" | "downloads";

export default function SkillsPage() {
  const [dialogOpen, setDialogOpen] = useState(false);

  // Search with debounce
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 300);
    return () => clearTimeout(timer);
  }, [query]);

  // Category filter
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [sort, setSort] = useState<SortOption>("upvotes");

  const filters = useMemo(() => {
    const f: Record<string, string> = {};
    if (debouncedQuery) f.q = debouncedQuery;
    if (activeCategory) f.category = activeCategory;
    if (sort) f.sort = sort;
    return Object.keys(f).length > 0 ? f : undefined;
  }, [debouncedQuery, activeCategory, sort]);

  const { data: skills, isLoading, mutate } = useSkills(filters);
  const { data: mySkills, mutate: mutateMySkills } = useMySkills();

  const subscribedIds = useMemo(
    () => new Set((mySkills ?? []).map((s) => s.id)),
    [mySkills],
  );

  const sortedSkills = useMemo(() => {
    if (!skills) return [];
    const s = [...skills];
    switch (sort) {
      case "upvotes":
        return s.sort((a, b) => b.upvotes - a.upvotes);
      case "newest":
        return s.sort(
          (a, b) =>
            new Date(b.created_at ?? 0).getTime() -
            new Date(a.created_at ?? 0).getTime(),
        );
      case "downloads":
        return s.sort((a, b) => b.copy_count - a.copy_count);
      default:
        return s;
    }
  }, [skills, sort]);

  const isSearching = !!debouncedQuery || !!activeCategory;

  return (
    <div className="flex flex-col gap-8 p-6 md:p-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex flex-col gap-2">
          <h1 className="text-3xl font-bold tracking-tight text-foreground">
            Skills
          </h1>
          <p className="text-[15px] text-text-secondary">
            Your prompt library. Subscribe, share, and teach Claude new tricks.
          </p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>+ Submit a Skill</Button>
      </div>

      {/* My Skills — library section */}
      {!isSearching && mySkills && mySkills.length > 0 && (
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-[13px] font-semibold uppercase tracking-widest text-text-muted/70">
              My Skills
            </h2>
            <span className="text-xs text-text-muted tabular-nums">
              {mySkills.length} subscribed
            </span>
          </div>
          <div className="flex flex-col rounded-2xl border border-border bg-card divide-y divide-border">
            {mySkills.map((skill) => (
              <SkillRow key={skill.id} skill={skill} subscribed onToggle={() => {
                unsubscribeSkill(skill.id).then(() => {
                  mutateMySkills();
                  toast("Unsubscribed");
                });
              }} />
            ))}
          </div>
        </div>
      )}

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-text-muted" />
        <input
          placeholder="Search all skills..."
          className="h-10 w-full rounded-xl border border-border bg-surface-2/50 pl-10 pr-4 text-sm text-foreground placeholder:text-text-muted outline-none transition-all duration-200 focus:border-primary/50 focus:bg-surface focus:ring-2 focus:ring-primary/20"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="flex-1 overflow-hidden">
          <CategoryPills
            categories={SKILL_CATEGORIES}
            active={activeCategory}
            onSelect={setActiveCategory}
          />
        </div>
        <Select
          value={sort}
          onValueChange={(v) => v && setSort(v as SortOption)}
        >
          <SelectTrigger size="sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="upvotes">Most Upvoted</SelectItem>
            <SelectItem value="newest">Newest</SelectItem>
            <SelectItem value="downloads">Most Downloaded</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Discover header */}
      {!isSearching && (
        <h2 className="text-[13px] font-semibold uppercase tracking-widest text-text-muted/70">
          Discover
        </h2>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="flex flex-col rounded-2xl border border-border bg-card divide-y divide-border">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4 px-5 py-4">
              <Skeleton className="size-9 rounded-lg" />
              <div className="flex flex-1 flex-col gap-1.5">
                <Skeleton className="h-4 w-40 rounded-md" />
                <Skeleton className="h-3 w-64 rounded-md" />
              </div>
              <Skeleton className="h-7 w-20 rounded-lg" />
            </div>
          ))}
        </div>
      )}

      {/* Empty */}
      {!isLoading && sortedSkills.length === 0 && (
        <EmptyState
          icon={<span className="text-3xl">✨</span>}
          title="No skills found"
          message="Try adjusting your search or filters, or submit a new skill."
          actionLabel="Submit a Skill"
          onAction={() => setDialogOpen(true)}
        />
      )}

      {/* Browse rows */}
      {!isLoading && sortedSkills.length > 0 && (
        <div className="flex flex-col rounded-2xl border border-border bg-card divide-y divide-border">
          {sortedSkills.map((skill) => (
            <SkillRow
              key={skill.id}
              skill={skill}
              subscribed={subscribedIds.has(skill.id)}
              onToggle={async () => {
                const isSub = subscribedIds.has(skill.id);
                try {
                  if (isSub) {
                    await unsubscribeSkill(skill.id);
                    toast("Unsubscribed");
                  } else {
                    await subscribeSkill(skill.id);
                    toast.success(`Added ${skill.title} to your skills`);
                  }
                  mutateMySkills();
                } catch {
                  toast.error(isSub ? "Failed to unsubscribe" : "Failed to subscribe");
                }
              }}
            />
          ))}
        </div>
      )}

      <SubmitSkillDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onSubmitted={() => mutate()}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// SkillRow — the core component, used for both library and browse
// ---------------------------------------------------------------------------

function SkillRow({
  skill,
  subscribed,
  onToggle,
}: {
  skill: Skill;
  subscribed: boolean;
  onToggle: () => void;
}) {
  const preview = skill.prompt_text
    ? skill.prompt_text.slice(0, 80).replace(/\n/g, " ").trim()
    : null;

  return (
    <div className="group flex items-center gap-4 px-5 py-3.5 transition-colors hover:bg-white/[0.02]">
      {/* Icon */}
      <Link
        href={`/skills/${skill.id}`}
        className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-surface-2 text-base ring-1 ring-border transition-colors group-hover:ring-border-strong"
      >
        {skill.category === "Development" ? "⚡" :
         skill.category === "Testing" ? "🧪" :
         skill.category === "Debugging" ? "🐛" :
         skill.category === "Planning" ? "📋" :
         skill.category === "Code Review" ? "👁" :
         skill.category === "Documents" ? "📝" : "📄"}
      </Link>

      {/* Content */}
      <Link
        href={`/skills/${skill.id}`}
        className="flex min-w-0 flex-1 flex-col gap-0.5"
      >
        <div className="flex items-center gap-2">
          <span className="truncate text-[14px] font-semibold text-foreground group-hover:text-primary transition-colors">
            {skill.title}
          </span>
          {skill.category && (
            <Badge variant="secondary" className="hidden sm:flex text-[10px] shrink-0">
              {skill.category}
            </Badge>
          )}
        </div>
        <span className="truncate text-[12px] text-text-muted">
          {skill.use_case || preview || "No description"}
        </span>
      </Link>

      {/* Stats */}
      <div className="hidden md:flex items-center gap-3 shrink-0 text-[11px] tabular-nums text-text-muted">
        <span className="flex items-center gap-1">
          <ArrowUp className="size-3" />
          {skill.upvotes}
        </span>
        <span className="flex items-center gap-1">
          <Download className="size-3" />
          {skill.copy_count}
        </span>
      </div>

      {/* Author */}
      <span className="hidden lg:block shrink-0 text-[11px] text-text-muted w-24 truncate text-right">
        {skill.author_name || "Anonymous"}
      </span>

      {/* Subscribe toggle */}
      <Button
        variant={subscribed ? "secondary" : "outline"}
        size="xs"
        className={cn("shrink-0 w-[90px]", subscribed && "text-green-400")}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          onToggle();
        }}
      >
        {subscribed ? (
          <>
            <Check className="size-3" />
            Saved
          </>
        ) : (
          "+ Save"
        )}
      </Button>
    </div>
  );
}
