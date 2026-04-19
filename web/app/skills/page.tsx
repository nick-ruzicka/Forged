"use client";

import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { CategoryPills } from "@/components/category-pills";
import { EmptyState } from "@/components/empty-state";
import { SkillCard } from "@/components/skill-card";
import { SubmitSkillDialog } from "@/components/submit-skill-dialog";
import { useSkills } from "@/lib/hooks";

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

  // Sort
  const [sort, setSort] = useState<SortOption>("upvotes");

  // Build API filters
  const filters = useMemo(() => {
    const f: Record<string, string> = {};
    if (debouncedQuery) f.q = debouncedQuery;
    if (activeCategory) f.category = activeCategory;
    if (sort) f.sort = sort;
    return Object.keys(f).length > 0 ? f : undefined;
  }, [debouncedQuery, activeCategory, sort]);

  const { data: skills, isLoading, mutate } = useSkills(filters);

  // Sort client-side as fallback
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

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold text-foreground">Skills</h1>
          <p className="text-sm text-text-secondary">
            Community SKILL.md files that teach Claude new capabilities.
          </p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>+ Submit a Skill</Button>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-text-muted" />
        <Input
          placeholder="Search skills..."
          className="bg-surface pl-9"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {/* Filters row */}
      <div className="flex items-center gap-4">
        <div className="flex-1 overflow-hidden">
          <CategoryPills
            categories={SKILL_CATEGORIES}
            active={activeCategory}
            onSelect={setActiveCategory}
          />
        </div>
        <Select value={sort} onValueChange={(v) => v && setSort(v as SortOption)}>
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

      {/* Loading */}
      {isLoading && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-[280px] rounded-xl" />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && sortedSkills.length === 0 && (
        <EmptyState
          icon={<span className="text-3xl">✨</span>}
          title="No skills found"
          message="Try adjusting your search or filters, or submit a new skill."
          actionLabel="Submit a Skill"
          onAction={() => setDialogOpen(true)}
        />
      )}

      {/* Grid */}
      {!isLoading && sortedSkills.length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {sortedSkills.map((skill) => (
            <SkillCard key={skill.id} skill={skill} />
          ))}
        </div>
      )}

      {/* Submit dialog */}
      <SubmitSkillDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onSubmitted={() => mutate()}
      />
    </div>
  );
}
