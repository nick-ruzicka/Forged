"use client";

import { useState, type ReactNode } from "react";
import { UserProvider } from "@/lib/user-context";
import { Sidebar } from "@/components/sidebar";
import { CommandMenu } from "@/components/command-menu";
import { KeyboardShortcuts } from "@/components/keyboard-shortcuts";
import { ToasterProvider } from "@/components/toaster-provider";

export function Providers({ children }: { children: ReactNode }) {
  const [commandOpen, setCommandOpen] = useState(false);

  return (
    <UserProvider>
      <div className="flex h-screen">
        <Sidebar onOpenCommandMenu={() => setCommandOpen(true)} />
        <main className="flex-1 overflow-y-auto pt-12 md:pt-0 animate-fade-in-up">
          {children}
        </main>
      </div>
      <CommandMenu open={commandOpen} onOpenChange={setCommandOpen} />
      <KeyboardShortcuts onOpenCommandMenu={() => setCommandOpen(true)} />
      <ToasterProvider />
    </UserProvider>
  );
}
