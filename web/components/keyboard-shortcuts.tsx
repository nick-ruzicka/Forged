"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

interface KeyboardShortcutsProps {
  onOpenCommandMenu: () => void;
}

export function KeyboardShortcuts({
  onOpenCommandMenu,
}: KeyboardShortcutsProps) {
  const router = useRouter();
  const lastKeyRef = useRef<{ key: string; time: number } | null>(null);

  useEffect(() => {
    function isTyping() {
      const el = document.activeElement;
      if (!el) return false;
      const tag = el.tagName.toLowerCase();
      return (
        tag === "input" ||
        tag === "textarea" ||
        (el as HTMLElement).isContentEditable
      );
    }

    function handleKeyDown(e: KeyboardEvent) {
      // Cmd/Ctrl+K -> command menu
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        onOpenCommandMenu();
        return;
      }

      if (isTyping()) return;

      // / -> command menu (when not typing)
      if (e.key === "/" && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        onOpenCommandMenu();
        return;
      }

      // g-chord shortcuts (900ms timeout)
      const now = Date.now();
      const last = lastKeyRef.current;

      if (last && last.key === "g" && now - last.time < 900) {
        switch (e.key) {
          case "c":
            e.preventDefault();
            router.push("/");
            lastKeyRef.current = null;
            return;
          case "s":
          case "k":
            e.preventDefault();
            router.push("/skills");
            lastKeyRef.current = null;
            return;
          case "m":
            e.preventDefault();
            router.push("/my-forge");
            lastKeyRef.current = null;
            return;
        }
      }

      if (e.key === "g") {
        lastKeyRef.current = { key: "g", time: now };
      } else {
        lastKeyRef.current = null;
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onOpenCommandMenu, router]);

  return null;
}
