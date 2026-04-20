"use client";

import {
  Briefcase,
  Code,
  Users,
  Sparkles,
  Calendar,
  BarChart,
  Layers,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface CategoryPillsProps {
  categories: string[];
  active: string | null;
  onSelect: (category: string | null) => void;
}

const CATEGORY_ICONS: Record<string, LucideIcon> = {
  "Account Research": Briefcase,
  "Developer Tools": Code,
  Meetings: Users,
  Other: Sparkles,
  Planning: Calendar,
  Reporting: BarChart,
};

export function CategoryPills({
  categories,
  active,
  onSelect,
}: CategoryPillsProps) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
      <Pill isActive={active === null} onClick={() => onSelect(null)} icon={Layers}>
        All
      </Pill>
      {categories.map((cat) => (
        <Pill
          key={cat}
          isActive={active === cat}
          onClick={() => onSelect(cat)}
          icon={CATEGORY_ICONS[cat]}
        >
          {cat}
        </Pill>
      ))}
    </div>
  );
}

function Pill({
  isActive,
  onClick,
  icon: Icon,
  children,
}: {
  isActive: boolean;
  onClick: () => void;
  icon?: LucideIcon;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-[13px] font-medium transition-all duration-150",
        isActive
          ? "border-[rgba(91,159,255,0.25)] bg-[rgba(0,102,255,0.12)] text-[#5B9FFF]"
          : "border-white/[0.08] bg-transparent text-white/55 hover:bg-white/[0.04] hover:text-white/80",
      )}
    >
      {Icon && <Icon className="size-3.5" />}
      {children}
    </button>
  );
}
