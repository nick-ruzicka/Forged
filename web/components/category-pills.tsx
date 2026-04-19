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
  const pillClass = (isActive: boolean) =>
    cn(
      "shrink-0 rounded-full border px-3.5 py-1.5 text-xs font-medium transition-all duration-150",
      isActive
        ? "border-primary/50 bg-primary/15 text-primary shadow-[0_0_8px_rgba(0,128,255,0.15)]"
        : "border-transparent bg-surface-2 text-text-muted hover:text-foreground hover:bg-white/[0.06]",
    );

  return (
    <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
      <button onClick={() => onSelect(null)} className={pillClass(active === null)}>
        All
      </button>
      {categories.map((cat) => (
        <button key={cat} onClick={() => onSelect(cat)} className={pillClass(active === cat)}>
          {cat}
        </button>
      ))}
    </div>
  );
}
