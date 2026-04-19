"use client";

import { cn } from "@/lib/utils";

interface CategoryPillsProps {
  categories: string[];
  active: string | null;
  onSelect: (category: string | null) => void;
}

export function CategoryPills({
  categories,
  active,
  onSelect,
}: CategoryPillsProps) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
      <button
        onClick={() => onSelect(null)}
        className={cn(
          "shrink-0 rounded-full border px-3 py-1 text-xs font-medium transition-colors",
          active === null
            ? "border-primary bg-primary/10 text-primary"
            : "border-border text-text-muted hover:text-text-secondary hover:border-border-strong",
        )}
      >
        All
      </button>
      {categories.map((cat) => (
        <button
          key={cat}
          onClick={() => onSelect(cat)}
          className={cn(
            "shrink-0 rounded-full border px-3 py-1 text-xs font-medium transition-colors",
            active === cat
              ? "border-primary bg-primary/10 text-primary"
              : "border-border text-text-muted hover:text-text-secondary hover:border-border-strong",
          )}
        >
          {cat}
        </button>
      ))}
    </div>
  );
}
