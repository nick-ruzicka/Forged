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
  BookOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { AppIcon } from "@/components/app-icon";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useMyItems, useMySkills } from "@/lib/hooks";
import { useUser } from "@/lib/user-context";

interface SidebarProps {
  onOpenCommandMenu: () => void;
}

const NAV_ITEMS = [
  { label: "Apps", href: "/", icon: LayoutGrid },
  { label: "Skills", href: "/skills", icon: Sparkles },
  { label: "My Forge", href: "/my-forge", icon: Box },
  { label: "Publish", href: "/publish", icon: Upload },
  { label: "Methodology", href: "/methodology", icon: BookOpen },
] as const;

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname.startsWith(href);
}

export function Sidebar({ onOpenCommandMenu }: SidebarProps) {
  const pathname = usePathname();
  const { adminKey, name, email } = useUser();
  const { data: myItems } = useMyItems();
  const { data: mySkills } = useMySkills();
  // Start expanded for SSR + first client render (matches server HTML), then
  // hydrate from localStorage in the mount effect below. Reading localStorage
  // in a useState initializer produces a hydration mismatch when the stored
  // preference differs from the SSR default.
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  // Hydrate collapsed state from localStorage and subscribe to toggle events.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    setCollapsed(localStorage.getItem("forge_sidebar_collapsed") === "true");
    const handleToggle = () => {
      setCollapsed(localStorage.getItem("forge_sidebar_collapsed") === "true");
    };
    window.addEventListener("forge-sidebar-toggle", handleToggle);
    return () => window.removeEventListener("forge-sidebar-toggle", handleToggle);
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect */

  const toggleCollapsed = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem("forge_sidebar_collapsed", String(next));
      return next;
    });
  }, []);

  // Close mobile sidebar on navigation. This syncs local UI to the router's
  // pathname, which is external state — not an intra-render cascade.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
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

  const subscribedSkills = (Array.isArray(mySkills) ? mySkills : []).slice(0, 6);

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
          "flex h-full flex-col bg-surface border-r border-border transition-[width] duration-200 ease-out",
          collapsed ? "w-14" : "w-56",
        )}
      >
        {/* Logo */}
        <div className="flex h-14 items-center px-3">
          <Link
            href="/"
            className="flex items-center gap-2.5 text-foreground hover:text-foreground/80 transition-colors"
          >
            <div className="flex size-8 items-center justify-center rounded-lg overflow-hidden">
              <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
                <defs>
                  <linearGradient id="forge-logo-bg" x1="0" y1="0" x2="32" y2="32">
                    <stop offset="0%" stopColor="hsl(217 92% 55%)" stopOpacity="0.2" />
                    <stop offset="100%" stopColor="hsl(217 92% 40%)" stopOpacity="0.1" />
                  </linearGradient>
                </defs>
                <rect width="32" height="32" rx="8" fill="url(#forge-logo-bg)" />
                <text x="16" y="21" textAnchor="middle" fill="rgba(255,255,255,0.92)" fontSize="16" fontWeight="700" fontFamily="var(--font-sans), system-ui, sans-serif">F</text>
              </svg>
            </div>
            {!collapsed && (
              <span className="text-sm font-bold tracking-tight text-white/90">
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
                <kbd className="ml-auto rounded border border-white/[0.08] bg-white/[0.03] px-1.5 py-0.5 text-[10px] text-white/40 font-mono">
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
              <span className="px-2.5 py-1.5 text-[11px] font-semibold text-white/35 uppercase tracking-[0.12em]">
                Installed
              </span>
            )}
            {installedApps.map((item) => (
              <NavItem
                key={item.id}
                collapsed={collapsed}
                label={item.name || "App"}
                icon={() => (
                  <AppIcon
                    name={item.name || "App"}
                    slug={item.slug || "app"}
                    icon={item.icon}
                    size={16}
                  />
                )}
                href={`/apps/${item.slug}`}
                active={pathname === `/apps/${item.slug}`}
              />
            ))}
          </div>
        )}

        {/* Subscribed skills */}
        {subscribedSkills && subscribedSkills.length > 0 && (
          <>
            <div className="px-3 py-2">
              <Separator />
            </div>
            <div className="flex flex-col gap-0.5 px-2 overflow-y-auto">
              {!collapsed && (
                <span className="px-2.5 py-1.5 text-[11px] font-semibold text-white/35 uppercase tracking-[0.12em]">
                  Skills
                </span>
              )}
              {subscribedSkills.map((skill) => (
                <NavItem
                  key={skill.id}
                  collapsed={collapsed}
                  label={skill.title}
                  icon={() => (
                    <span className="text-sm leading-none">📄</span>
                  )}
                  href={`/skills/${skill.id}`}
                  active={pathname === `/skills/${skill.id}`}
                />
              ))}
            </div>
          </>
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
        <div className="flex items-center justify-between border-t border-border px-2 pb-3 pt-3">
          <div
            className={cn(
              "flex size-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary/30 to-primary/10 text-xs font-semibold text-primary ring-1 ring-primary/20",
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
          <svg width="20" height="20" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs><linearGradient id="forge-m" x1="0" y1="0" x2="32" y2="32"><stop offset="0%" stopColor="hsl(217 92% 55%)" stopOpacity="0.2" /><stop offset="100%" stopColor="hsl(217 92% 40%)" stopOpacity="0.1" /></linearGradient></defs>
            <rect width="32" height="32" rx="8" fill="url(#forge-m)" />
            <text x="16" y="21" textAnchor="middle" fill="rgba(255,255,255,0.92)" fontSize="16" fontWeight="700" fontFamily="var(--font-sans), system-ui, sans-serif">F</text>
          </svg>
          <span className="text-sm font-bold tracking-tight text-white/90">Forge</span>
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
        "relative flex w-full items-center gap-2.5 rounded-lg px-2.5 text-[13px] font-medium transition-all duration-150",
        active
          ? "bg-[rgba(0,102,255,0.10)] text-[#5B9FFF]"
          : "text-white/55 hover:bg-white/[0.04] hover:text-white/90",
        collapsed ? "justify-center px-0 py-2" : "py-[7px]",
      )}
      style={{ height: collapsed ? undefined : 36 }}
    >
      {active && (
        <span className="absolute left-0 top-1/2 -translate-y-1/2 h-4 w-[2px] rounded-full bg-[#5B9FFF]" />
      )}
      <Icon className={cn("size-4 shrink-0", active ? "text-[#5B9FFF]" : "text-white/60")} />
      {!collapsed && <span className="truncate">{label}</span>}
      {!collapsed && trailing}
    </span>
  );

  const inner = href ? (
    <Link href={href} onClick={onClick} className="block w-full">
      {content}
    </Link>
  ) : (
    <button onClick={onClick} className="block w-full">
      {content}
    </button>
  );

  const wrapped = collapsed ? (
    <Tooltip>
      <TooltipTrigger render={<div className="w-full" />}>
        {inner}
      </TooltipTrigger>
      <TooltipContent side="right">{label}</TooltipContent>
    </Tooltip>
  ) : inner;

  return wrapped;
}
