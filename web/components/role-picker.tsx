"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
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

  function handleSelect(role: string) {
    setRole(role);
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogHeader>
        <DialogTitle>Welcome to Forge</DialogTitle>
        <DialogDescription>
          Select your role to personalize your experience.
        </DialogDescription>
      </DialogHeader>
      <DialogContent className="sm:max-w-md">
        <div className="grid grid-cols-4 gap-2">
          {ROLES.map((role) => (
            <button
              key={role}
              onClick={() => handleSelect(role)}
              className="flex items-center justify-center rounded-lg border border-border bg-surface px-3 py-3 text-sm font-medium text-foreground transition-colors hover:border-border-strong hover:bg-surface-2"
            >
              {role}
            </button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
