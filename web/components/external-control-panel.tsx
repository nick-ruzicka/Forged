"use client";

import { useState, useCallback } from "react";
import { FolderOpen, ExternalLink, Trash2 } from "lucide-react";
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

  const runningApp = runningData?.apps.find((a) => a.slug === slug);
  const isRunning = runningApp?.running ?? false;

  // Parse install type
  let installType = "external";
  try {
    const meta =
      typeof app.install_meta === "string"
        ? JSON.parse(app.install_meta as string)
        : (app as Record<string, unknown>).install_meta;
    if (meta && typeof meta === "object" && "type" in meta)
      installType = (meta as { type: string }).type;
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
    <div className="flex flex-col gap-5">
      {/* Header with status */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span
            className={`inline-block size-2 rounded-full ${
              isRunning
                ? "bg-green-500 shadow-[0_0_4px_theme(colors.green.500)] animate-pulse"
                : "bg-neutral-600"
            }`}
          />
          <span className="text-sm text-text-secondary">
            {isRunning
              ? `Running${runningApp?.uptime_sec ? ` · ${formatUptime(runningApp.uptime_sec)}` : ""}`
              : "Not running"}
          </span>
          <Badge variant="secondary" className="text-[10px] uppercase">
            {installType}
          </Badge>
        </div>
        <Button
          size="sm"
          disabled={launching}
          onClick={handleLaunch}
          className={
            isRunning
              ? "bg-green-500/15 text-green-500 border border-green-500/30 hover:bg-green-500/25"
              : ""
          }
        >
          {launching ? "Opening…" : isRunning ? "Focus" : "Launch"}
        </Button>
      </div>

      {/* Cards row */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {/* Usage card */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-[10px] font-medium uppercase tracking-wider text-text-muted">
              Your usage
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!usage || !usage.session_count_7d ? (
              <p className="text-xs text-text-muted">
                Not used yet — click Launch above
              </p>
            ) : (
              <div className="flex flex-col gap-2">
                <UsageChart sessions={usage.sessions_7d} />
                <p className="text-xs text-text-secondary">
                  {formatDuration(usage.total_sec_7d)} this week ·{" "}
                  {usage.session_count_7d} sessions · last opened{" "}
                  {timeAgo(usage.last_opened)}
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Team card */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-[10px] font-medium uppercase tracking-wider text-text-muted">
              Team
            </CardTitle>
          </CardHeader>
          <CardContent>
            {/* Future: add heartbeat system for live presence. See VISION.md social features roadmap. */}
            {!social || !social.team_install_count ? (
              <p className="text-xs text-text-muted">
                Be the first on your team to use this
              </p>
            ) : (
              <div className="flex flex-col gap-1">
                <p className="text-sm font-medium text-foreground">
                  {social.team_install_count} teammate
                  {social.team_install_count > 1 ? "s" : ""} installed this
                </p>
                {social.role_concentration && (
                  <p className="text-xs text-text-muted">
                    Popular with {social.role_concentration.role}s —{" "}
                    {social.role_concentration.count} of{" "}
                    {social.role_concentration.total} installs from{" "}
                    {social.role_concentration.role}s
                  </p>
                )}
                {social.installs_this_week > 0 && (
                  <p className="text-xs text-text-muted">
                    {social.installs_this_week} new install
                    {social.installs_this_week > 1 ? "s" : ""} this week
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Co-installs */}
      <CoInstallCards toolId={app.id} toolName={app.name} />

      {/* Quick actions */}
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" onClick={handleReveal}>
          <FolderOpen className="mr-1.5 size-3.5" />
          Show in Finder
        </Button>
        {app.source_url && (
          <Button
            variant="outline"
            size="sm"
            render={
              <a
                href={app.source_url}
                target="_blank"
                rel="noopener noreferrer"
              />
            }
          >
            <ExternalLink className="mr-1.5 size-3.5" />
            View source
          </Button>
        )}
        <Button variant="outline" size="sm" onClick={handleUninstall}>
          <Trash2 className="mr-1.5 size-3.5" />
          Uninstall
        </Button>
      </div>

      {/* About */}
      <details className="text-sm">
        <summary className="cursor-pointer text-[11px] font-medium uppercase tracking-wider text-text-muted">
          About
        </summary>
        <p className="mt-2 whitespace-pre-wrap text-text-secondary">
          {app.description || "No description available."}
        </p>
        <p className="mt-1 text-xs text-text-muted">
          by {app.author_name || "Unknown"}
        </p>
      </details>

      {/* Privacy footer */}
      <div className="border-t border-border pt-3 text-[11px] text-text-muted/40">
        Forge monitors: process name only · Not tracked: window titles, URLs,
        keystrokes{" "}
        <button
          onClick={handlePrivacy}
          className="text-text-muted/30 underline hover:text-text-muted"
        >
          Privacy details
        </button>
      </div>

      {/* Privacy modal */}
      {privacyOpen && privacyData && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-6"
          onClick={(e) => {
            if (e.target === e.currentTarget) setPrivacyOpen(false);
          }}
        >
          <div className="max-h-[80vh] w-full max-w-lg overflow-auto rounded-xl border border-border bg-surface p-6">
            <h3 className="mb-3 text-base font-semibold text-foreground">
              Privacy Details
            </h3>
            <div className="flex flex-col gap-3 text-xs text-text-secondary">
              <p>
                <strong className="text-foreground">Scope:</strong>{" "}
                {privacyData.scope}
              </p>
              <p>
                <strong className="text-foreground">Method:</strong>{" "}
                {privacyData.method}
              </p>
              <div>
                <strong className="text-foreground">Data collected:</strong>
                <ul className="mt-1 list-inside list-disc text-text-muted">
                  {privacyData.data_collected.map((d) => (
                    <li key={d}>{d}</li>
                  ))}
                </ul>
              </div>
              <div>
                <strong className="text-foreground">Data NOT collected:</strong>
                <ul className="mt-1 list-inside list-disc text-text-muted">
                  {privacyData.data_not_collected.map((d) => (
                    <li key={d}>{d}</li>
                  ))}
                </ul>
              </div>
              <p className="text-text-muted">Storage: {privacyData.storage}</p>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="mt-4"
              onClick={() => setPrivacyOpen(false)}
            >
              Close
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
