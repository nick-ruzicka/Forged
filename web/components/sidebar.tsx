"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutGrid,
  Sparkles,
  Box,
  Upload,
  Shield,
  Search,
  ChevronLeft,
  ChevronRight,
  Menu,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useMyItems } from "@/lib/hooks";
import { useUser } from "@/lib/user-context";

interface SidebarProps {
  onOpenCommandMenu: () => void;
}

const NAV_ITEMS = [
  { label: "Apps", href: "/", icon: LayoutGrid },
  { label: "Skills", href: "/skills", icon: Sparkles },
  { label: "My Forge", href: "/my-forge", icon: Box },
  { label: "Publish", href: "/publish", icon: Upload },
] as const;

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname.startsWith(href);
}

export function Sidebar({ onOpenCommandMenu }: SidebarProps) {
  const pathname = usePathname();
  const { adminKey, name, email } = useUser();
  const { data: myItems } = useMyItems();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  // Hydrate collapsed state from localStorage
  useEffect(() => {
    const stored = localStorage.getItem("forge_sidebar_collapsed");
    if (stored === "true") setCollapsed(true);
  }, []);

  const toggleCollapsed = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem("forge_sidebar_collapsed", String(next));
      return next;
    });
  }, []);

  // Close mobile sidebar on navigation
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const itemsArray = Array.isArray(myItems) ? myItems : [];
  const installedApps = [...itemsArray]
    .sort((a, b) => {
      const aTime = a.last_opened_at ? new Date(a.last_opened_at).getTime() : 0;
      const bTime = b.last_opened_at ? new Date(b.last_opened_at).getTime() : 0;
      return bTime - aTime;
    })
    .slice(0, 8);

  const initials =
    name
      ?.split(" ")
      .map((w) => w[0])
      .join("")
      .toUpperCase()
      .slice(0, 2) ||
    email?.slice(0, 2).toUpperCase() ||
    "U";

  const sidebarContent = (
    <TooltipProvider>
      <div
        className={cn(
          "flex h-full flex-col bg-surface border-r border-border",
          collapsed ? "w-14" : "w-56",
        )}
      >
        {/* Logo */}
        <div className="flex h-12 items-center px-3">
          <Link
            href="/"
            className="flex items-center gap-2 text-foreground hover:text-foreground/80 transition-colors"
          >
            <span className="text-lg">&#9874;</span>
            {!collapsed && (
              <span className="font-mono text-sm font-semibold tracking-tight">
                Forge
              </span>
            )}
          </Link>
        </div>

        {/* Search trigger */}
        <div className="px-2 mb-1">
          <NavItem
            collapsed={collapsed}
            label="Search"
            icon={Search}
            active={false}
            onClick={onOpenCommandMenu}
            trailing={
              !collapsed ? (
                <kbd className="ml-auto rounded border border-border-strong bg-surface-2 px-1.5 py-0.5 text-[10px] text-text-muted font-mono">
                  &#8984;K
                </kbd>
              ) : undefined
            }
          />
        </div>

        {/* Main nav */}
        <nav className="flex flex-col gap-0.5 px-2">
          {NAV_ITEMS.map((item) => (
            <NavItem
              key={item.href}
              collapsed={collapsed}
              label={item.label}
              icon={item.icon}
              href={item.href}
              active={isActive(pathname, item.href)}
            />
          ))}
        </nav>

        <div className="px-3 py-2">
          <Separator />
        </div>

        {/* Installed apps */}
        {installedApps && installedApps.length > 0 && (
          <div className="flex flex-col gap-0.5 px-2 overflow-y-auto">
            {!collapsed && (
              <span className="px-2 py-1 text-[11px] font-medium text-text-muted uppercase tracking-wider">
                Installed
              </span>
            )}
            {installedApps.map((item) => (
              <NavItem
                key={item.id}
                collapsed={collapsed}
                label={item.name || "App"}
                icon={() => (
                  <span className="text-sm leading-none">
                    {item.icon || "📦"}
                  </span>
                )}
                href={`/apps/${item.slug}`}
                active={pathname === `/apps/${item.slug}`}
              />
            ))}
          </div>
        )}

        {/* Spacer */}
        <div className="flex-1" />

        {/* Admin */}
        {adminKey && (
          <div className="px-2 mb-1">
            <NavItem
              collapsed={collapsed}
              label="Admin"
              icon={Shield}
              href="/admin"
              active={pathname.startsWith("/admin")}
            />
          </div>
        )}

        {/* User avatar + collapse toggle */}
        <div className="flex items-center justify-between px-2 pb-3 pt-1">
          <div
            className={cn(
              "flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/20 text-xs font-medium text-primary",
            )}
          >
            {initials}
          </div>
          {!collapsed && (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={toggleCollapsed}
              aria-label="Collapse sidebar"
            >
              <ChevronLeft className="size-4" />
            </Button>
          )}
          {collapsed && (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={toggleCollapsed}
              aria-label="Expand sidebar"
              className="sr-only group-hover/sidebar:not-sr-only"
            >
              <ChevronRight className="size-4" />
            </Button>
          )}
        </div>
      </div>
    </TooltipProvider>
  );

  return (
    <>
      {/* Mobile top bar */}
      <div className="fixed inset-x-0 top-0 z-40 flex h-12 items-center border-b border-border bg-surface px-3 md:hidden">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label={mobileOpen ? "Close menu" : "Open menu"}
        >
          {mobileOpen ? <X className="size-5" /> : <Menu className="size-5" />}
        </Button>
        <Link
          href="/"
          className="ml-2 flex items-center gap-1.5 text-foreground"
        >
          <span className="text-lg">&#9874;</span>
          <span className="font-mono text-sm font-semibold">Forge</span>
        </Link>
      </div>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Mobile sidebar */}
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-50 transform transition-transform duration-200 md:hidden",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        {sidebarContent}
      </div>

      {/* Desktop sidebar */}
      <div className="group/sidebar hidden md:flex h-full shrink-0">
        {sidebarContent}
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// NavItem
// ---------------------------------------------------------------------------

interface NavItemProps {
  collapsed: boolean;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  href?: string;
  active?: boolean;
  onClick?: () => void;
  trailing?: React.ReactNode;
}

function NavItem({
  collapsed,
  label,
  icon: Icon,
  href,
  active,
  onClick,
  trailing,
}: NavItemProps) {
  const content = (
    <span
      className={cn(
        "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors",
        active
          ? "bg-primary/10 text-primary"
          : "text-text-secondary hover:bg-muted hover:text-foreground",
        collapsed && "justify-center px-0",
      )}
    >
      <Icon className="size-4 shrink-0" />
      {!collapsed && <span className="truncate">{label}</span>}
      {!collapsed && trailing}
    </span>
  );

  const wrapped = collapsed ? (
    <Tooltip>
      <TooltipTrigger className="w-full">
        {href ? (
          <Link href={href} onClick={onClick} className="block w-full">
            {content}
          </Link>
        ) : (
          <button onClick={onClick} className="block w-full">
            {content}
          </button>
        )}
      </TooltipTrigger>
      <TooltipContent side="right">{label}</TooltipContent>
    </Tooltip>
  ) : href ? (
    <Link href={href} onClick={onClick} className="block w-full">
      {content}
    </Link>
  ) : (
    <button onClick={onClick} className="block w-full">
      {content}
    </button>
  );

  return wrapped;
}
