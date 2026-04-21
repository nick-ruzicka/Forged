"use client";

import { X } from "lucide-react";
import { useUser } from "@/lib/user-context";

interface RolePickerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const ROLES = [
  "AE",
  "SDR",
  "RevOps",
  "CS",
  "Product",
  "Eng",
  "Recruiter",
  "Other",
] as const;

export function RolePicker({ open, onOpenChange }: RolePickerProps) {
  const { setRole } = useUser();

  if (!open) return null;

  function handleSelect(role: string) {
    setRole(role);
    onOpenChange(false);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={() => onOpenChange(false)}
      />
      {/* Card */}
      <div className="relative z-10 w-full max-w-sm rounded-2xl border border-border bg-card p-6 shadow-[0_20px_60px_rgba(0,0,0,0.5)]">
        <button
          type="button"
          onClick={() => onOpenChange(false)}
          className="absolute top-4 right-4 rounded-lg p-1 text-text-muted hover:text-foreground transition-colors"
        >
          <X className="size-4" />
        </button>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <h2 className="text-[16px] font-semibold text-foreground">Welcome to Forge</h2>
            <p className="text-[13px] text-text-secondary">
              Select your role to personalize your experience.
            </p>
          </div>
          <div className="grid grid-cols-4 gap-2">
            {ROLES.map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => handleSelect(r)}
                className="flex items-center justify-center rounded-lg border border-border bg-surface px-3 py-3 text-sm font-medium text-foreground transition-colors hover:border-border-strong hover:bg-surface-2 active:scale-95"
              >
                {r}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
