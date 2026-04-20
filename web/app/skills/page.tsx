"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowUp,
  Check,
  Download,
  Search,
  Sparkles,
  Zap,
  FlaskConical,
  Bug,
  ClipboardList,
  Eye,
  FileText,
  FileCode,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
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
import { subscribeSkill, unsubscribeSkill } from "@/lib/api";
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

const SKILL_CATEGORY_ICONS: Record<string, typeof Zap> = {
  Development: Zap,
  Testing: FlaskConical,
  Debugging: Bug,
  Planning: ClipboardList,
  "Code Review": Eye,
  Documents: FileText,
  Other: Sparkles,
};

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
          <h1 className="text-[28px] font-bold tracking-[-0.03em] text-white/98">
            Skills
          </h1>
          <p className="text-sm text-white/55 leading-relaxed">
            Your prompt library. Subscribe, share, and teach Claude new tricks.
          </p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>+ Submit a Skill</Button>
      </div>

      {/* My Skills — library section */}
      {!isSearching && mySkills && mySkills.length > 0 && (
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/40">
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
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/40">
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

  const SkillIcon = SKILL_CATEGORY_ICONS[skill.category || "Other"] || FileCode;

  return (
    <div className="group flex items-center gap-4 px-4 transition-colors hover:bg-white/[0.025] border-l-2 border-l-transparent hover:border-l-[rgba(0,102,255,0.4)]" style={{ height: 56 }}>
      {/* Icon */}
      <Link
        href={`/skills/${skill.id}`}
        className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-white/[0.03] ring-1 ring-white/[0.06] transition-colors group-hover:ring-white/[0.10]"
      >
        <SkillIcon className="size-4 text-white/60" />
      </Link>

      {/* Content */}
      <Link
        href={`/skills/${skill.id}`}
        className="flex min-w-0 flex-1 flex-col gap-0.5"
      >
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-semibold text-white/95 group-hover:text-[#5B9FFF] transition-colors">
            {skill.title}
          </span>
          {skill.category && (
            <span className="hidden sm:inline shrink-0 text-[10px] font-medium uppercase tracking-[0.08em] text-white/35">
              {skill.category}
            </span>
          )}
        </div>
        <span className="truncate text-[13px] text-white/60">
          {skill.use_case || preview || "No description"}
        </span>
      </Link>

      {/* Stats */}
      <div className="hidden md:flex items-center gap-3 shrink-0 text-[11px] tabular-nums text-white/45">
        <button
          className="flex items-center gap-1 hover:text-[#5B9FFF] transition-colors"
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); }}
        >
          <ArrowUp className="size-3" />
          {skill.upvotes}
        </button>
        <span className="flex items-center gap-1">
          <Download className="size-3" />
          {skill.copy_count}
        </span>
      </div>

      {/* Author */}
      <span className="hidden lg:block shrink-0 text-xs text-white/45 w-24 truncate text-right">
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
