"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import {
  LayoutGrid,
  Sparkles,
  Box,
  Upload,
} from "lucide-react";
import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
} from "@/components/ui/command";
import { useApps } from "@/lib/hooks";
import { useSkills } from "@/lib/hooks";

interface CommandMenuProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CommandMenu({ open, onOpenChange }: CommandMenuProps) {
  const router = useRouter();
  const { data: apps } = useApps();
  const { data: skills } = useSkills();
  const [search, setSearch] = useState("");

  const navigate = useCallback(
    (path: string) => {
      onOpenChange(false);
      router.push(path);
    },
    [onOpenChange, router],
  );

  const handleOpenChange = useCallback(
    (next: boolean) => {
      if (!next) setSearch("");
      onOpenChange(next);
    },
    [onOpenChange],
  );

  return (
    <CommandDialog open={open} onOpenChange={handleOpenChange}>
      <CommandInput
        placeholder="Search apps, skills, pages..."
        value={search}
        onValueChange={setSearch}
      />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>

        <CommandGroup heading="Pages">
          <CommandItem onSelect={() => navigate("/")}>
            <LayoutGrid className="size-4" />
            <span>Apps</span>
          </CommandItem>
          <CommandItem onSelect={() => navigate("/skills")}>
            <Sparkles className="size-4" />
            <span>Skills</span>
          </CommandItem>
          <CommandItem onSelect={() => navigate("/my-forge")}>
            <Box className="size-4" />
            <span>My Forge</span>
          </CommandItem>
          <CommandItem onSelect={() => navigate("/publish")}>
            <Upload className="size-4" />
            <span>Publish</span>
          </CommandItem>
        </CommandGroup>

        {apps && apps.length > 0 && (
          <CommandGroup heading="Apps">
            {apps.map((app) => (
              <CommandItem
                key={app.id}
                onSelect={() => navigate(`/apps/${app.slug}`)}
              >
                <span className="text-base">{app.icon || "📦"}</span>
                <div className="flex flex-col">
                  <span>{app.name}</span>
                  {app.tagline && (
                    <span className="text-xs text-muted-foreground">
                      {app.tagline}
                    </span>
                  )}
                </div>
              </CommandItem>
            ))}
          </CommandGroup>
        )}

        {skills && skills.length > 0 && (
          <CommandGroup heading="Skills">
            {skills.map((skill) => (
              <CommandItem
                key={skill.id}
                onSelect={() => navigate(`/skills#skill-${skill.id}`)}
              >
                <Sparkles className="size-4" />
                <span>{skill.title}</span>
              </CommandItem>
            ))}
          </CommandGroup>
        )}
      </CommandList>
    </CommandDialog>
  );
}
