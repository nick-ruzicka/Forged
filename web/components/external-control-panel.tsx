"use client";

import { useState, useCallback } from "react";
import { FolderOpen, ExternalLink, Trash2, ChevronDown, Shield } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { UsageChart, formatDuration, timeAgo, formatUptime } from "@/components/usage-chart";
import { CoInstallCards } from "@/components/co-install-cards";
import { useAgentUsage, useRunningApps, useSocial } from "@/lib/hooks";
import { launchApp, revealApp, uninstallAgent, getAgentPrivacy } from "@/lib/api";
import type { App } from "@/lib/types";
import type { PrivacyData } from "@/lib/types";

interface ExternalControlPanelProps {
  app: App;
  isInstalled: boolean;
  onUninstall?: () => void;
}

export function ExternalControlPanel({
  app,
  isInstalled,
  onUninstall,
}: ExternalControlPanelProps) {
  const slug = app.slug || "";
  const { data: runningData } = useRunningApps(isInstalled);
  const { data: usage } = useAgentUsage(isInstalled ? slug : undefined);
  const { data: social } = useSocial(app.id);
  const [privacyOpen, setPrivacyOpen] = useState(false);
  const [privacyData, setPrivacyData] = useState<PrivacyData | null>(null);
  const [launching, setLaunching] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);

  const runningApp = runningData?.apps.find((a) => a.slug === slug);
  const isRunning = runningApp?.running ?? false;

  let installType = "external";
  try {
    if (app.install_meta) {
      const meta = JSON.parse(app.install_meta);
      if (meta && meta.type) installType = meta.type;
    }
  } catch {
    // keep default
  }

  const handleLaunch = useCallback(async () => {
    setLaunching(true);
    try {
      await launchApp(slug, app.name);
    } catch {
      // ignore
    }
    setLaunching(false);
  }, [slug, app.name]);

  const handleReveal = useCallback(async () => {
    try {
      await revealApp(slug, app.name);
    } catch {
      // ignore
    }
  }, [slug, app.name]);

  const handleUninstall = useCallback(async () => {
    if (!confirm(`Uninstall ${app.name}?`)) return;
    try {
      await uninstallAgent(slug);
      onUninstall?.();
    } catch {
      // ignore
    }
  }, [slug, app.name, onUninstall]);

  const handlePrivacy = useCallback(async () => {
    try {
      const data = await getAgentPrivacy();
      setPrivacyData(data);
      setPrivacyOpen(true);
    } catch {
      // ignore
    }
  }, []);

  return (
    <div className="flex flex-col gap-6">
      {/* Status + Launch bar */}
      <div className="flex items-center justify-between rounded-2xl border border-border bg-card p-4">
        <div className="flex items-center gap-3">
          <div className="relative flex size-10 items-center justify-center rounded-xl bg-surface-2 ring-1 ring-border">
            <span className="text-lg">{app.icon || "📦"}</span>
            <span
              className={`absolute -right-0.5 -top-0.5 size-2.5 rounded-full ring-2 ring-card ${
                isRunning
                  ? "bg-green-500 shadow-[0_0_6px_theme(colors.green.500)]"
                  : "bg-neutral-600"
              }`}
            />
          </div>
          <div className="flex flex-col gap-0.5">
            <div className="flex items-center gap-2">
              <span className="text-[14px] font-semibold text-foreground">
                {isRunning ? "Running" : "Not running"}
              </span>
              {isRunning && runningApp?.uptime_sec && (
                <span className="text-xs text-text-muted tabular-nums">
                  {formatUptime(runningApp.uptime_sec)} uptime
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="secondary" className="text-[10px] uppercase">
                {installType}
              </Badge>
            </div>
          </div>
        </div>
        <Button
          size="sm"
          disabled={launching}
          onClick={handleLaunch}
          className={
            isRunning
              ? "bg-green-500/15 text-green-500 border border-green-500/30 hover:bg-green-500/25 shadow-none"
              : ""
          }
        >
          {launching ? "Opening…" : isRunning ? "Focus" : "Launch"}
        </Button>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {/* Usage card */}
        <div className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-5">
          <h4 className="text-[11px] font-semibold uppercase tracking-widest text-text-muted/70">
            Your Usage
          </h4>
          {!usage || !usage.session_count_7d ? (
            <div className="flex flex-col items-center justify-center gap-2 py-4 text-center">
              <span className="text-2xl">📊</span>
              <p className="text-xs text-text-muted leading-relaxed">
                No usage data yet.<br />Launch the app to start tracking.
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <UsageChart sessions={usage.sessions_7d} />
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
                <span className="text-text-secondary">
                  <span className="font-semibold text-foreground tabular-nums">{formatDuration(usage.total_sec_7d)}</span> this week
                </span>
                <span className="text-text-secondary">
                  <span className="font-semibold text-foreground tabular-nums">{usage.session_count_7d}</span> sessions
                </span>
                {usage.last_opened && (
                  <span className="text-text-muted">
                    Last used {timeAgo(usage.last_opened)}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Team card */}
        <div className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-5">
          <h4 className="text-[11px] font-semibold uppercase tracking-widest text-text-muted/70">
            Team Activity
          </h4>
          {!social || !social.team_install_count ? (
            <div className="flex flex-col items-center justify-center gap-2 py-4 text-center">
              <span className="text-2xl">👥</span>
              <p className="text-xs text-text-muted leading-relaxed">
                Be the first on your team<br />to use this app.
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <div className="flex items-baseline gap-1">
                <span className="text-2xl font-bold tabular-nums text-foreground">
                  {social.team_install_count}
                </span>
                <span className="text-sm text-text-secondary">
                  teammate{social.team_install_count > 1 ? "s" : ""}
                </span>
              </div>
              <div className="flex flex-col gap-1.5">
                {social.role_concentration && (
                  <p className="text-xs text-text-muted leading-relaxed">
                    Popular with {social.role_concentration.role}s — {social.role_concentration.count} of {social.role_concentration.total} installs
                  </p>
                )}
                {social.installs_this_week > 0 && (
                  <p className="text-xs text-text-muted">
                    <span className="font-medium text-text-secondary">+{social.installs_this_week}</span> new this week
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Co-installs */}
      <CoInstallCards toolId={app.id} toolName={app.name} />

      {/* Quick actions */}
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" onClick={handleReveal}>
          <FolderOpen data-icon="inline-start" />
          Show in Finder
        </Button>
        {app.source_url && (
          <Button
            variant="outline"
            size="sm"
            nativeButton={false}
            render={
              <a
                href={app.source_url}
                target="_blank"
                rel="noopener noreferrer"
              />
            }
          >
            <ExternalLink data-icon="inline-start" />
            View source
          </Button>
        )}
        <Button variant="outline" size="sm" onClick={handleUninstall} className="hover:border-destructive/40 hover:text-destructive">
          <Trash2 data-icon="inline-start" />
          Uninstall
        </Button>
      </div>

      {/* About collapsible */}
      <div className="rounded-2xl border border-border bg-card">
        <button
          onClick={() => setAboutOpen(!aboutOpen)}
          className="flex w-full items-center justify-between p-4 text-left"
        >
          <span className="text-[13px] font-semibold text-foreground">About this app</span>
          <ChevronDown
            className={`size-4 text-text-muted transition-transform duration-200 ${aboutOpen ? "rotate-180" : ""}`}
          />
        </button>
        {aboutOpen && (
          <div className="border-t border-border px-4 pb-4 pt-3">
            <p className="whitespace-pre-wrap text-[14px] leading-relaxed text-text-secondary">
              {app.description || "No description available."}
            </p>
            <p className="mt-2 text-xs text-text-muted">
              by {app.author_name || "Unknown"}
            </p>
          </div>
        )}
      </div>

      {/* Privacy footer */}
      <div className="flex items-start gap-2 rounded-xl border border-border/50 bg-surface-2/50 px-4 py-3">
        <Shield className="mt-0.5 size-3.5 shrink-0 text-text-muted/50" />
        <div className="text-[11px] leading-relaxed text-text-muted/60">
          Forge monitors process name only. Not tracked: window titles, URLs, keystrokes.{" "}
          <button
            onClick={handlePrivacy}
            className="text-text-muted/50 underline underline-offset-2 hover:text-text-muted transition-colors"
          >
            Privacy details
          </button>
        </div>
      </div>

      {/* Privacy modal */}
      {privacyOpen && privacyData && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-6"
          onClick={(e) => {
            if (e.target === e.currentTarget) setPrivacyOpen(false);
          }}
        >
          <div className="max-h-[80vh] w-full max-w-lg overflow-auto rounded-2xl border border-border bg-card p-6 shadow-[0_24px_80px_rgba(0,0,0,0.5)]">
            <div className="flex items-center gap-2 mb-4">
              <Shield className="size-4 text-primary" />
              <h3 className="text-base font-semibold text-foreground">
                Privacy Details
              </h3>
            </div>
            <div className="flex flex-col gap-4 text-[13px] text-text-secondary">
              <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-2">
                <span className="font-medium text-foreground">Scope</span>
                <span>{privacyData.scope}</span>
                <span className="font-medium text-foreground">Method</span>
                <span>{privacyData.method}</span>
                <span className="font-medium text-foreground">Storage</span>
                <span>{privacyData.storage}</span>
              </div>

              <div className="flex flex-col gap-2">
                <span className="font-medium text-foreground">Data collected</span>
                <ul className="flex flex-col gap-1 pl-4">
                  {privacyData.data_collected.map((d) => (
                    <li key={d} className="list-disc text-text-muted">{d}</li>
                  ))}
                </ul>
              </div>

              <div className="flex flex-col gap-2">
                <span className="font-medium text-foreground">Data NOT collected</span>
                <ul className="flex flex-col gap-1 pl-4">
                  {privacyData.data_not_collected.map((d) => (
                    <li key={d} className="list-disc text-text-muted">{d}</li>
                  ))}
                </ul>
              </div>
            </div>
            <div className="mt-5 flex justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPrivacyOpen(false)}
              >
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
