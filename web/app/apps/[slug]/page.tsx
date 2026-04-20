"use client";

import { use, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import yaml from "js-yaml";
import { ExternalLink, PanelLeftClose, Download, Star, Clock, Users, Sparkles, Copy, Check, Settings, Share2 } from "lucide-react";
import { AppIcon } from "@/components/app-icon";
import { ConfigWizard, type ParsedSchema } from "@/components/config-wizard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { StarButton } from "@/components/star-button";
import { InstallButton } from "@/components/install-button";
import { AppEmbed } from "@/components/app-embed";
import { EmptyState } from "@/components/empty-state";
import { ReviewCard } from "@/components/review-card";
import { ReviewForm } from "@/components/review-form";
import { InstallProgress } from "@/components/install-progress";
import { ExternalControlPanel } from "@/components/external-control-panel";
import { CoInstallCards } from "@/components/co-install-cards";
import {
  useApp,
  useMyItems,
  useMyStars,
  useReviews,
  useAgentAvailable,
  uninstallApp,
} from "@/lib/hooks";

export default function AppDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = use(params);
  const searchParams = useSearchParams();
  const autoInstall = searchParams.get("install") === "1";

  const { data: app, isLoading } = useApp(slug);
  const { data: items, mutate: mutateItems } = useMyItems();
  const { data: stars } = useMyStars();
  const { data: reviews, mutate: mutateReviews } = useReviews(app?.id);

  const [wizardOpen, setWizardOpen] = useState(false);

  const isExternal = app?.delivery === "external";
  const { data: agentAvailable } = useAgentAvailable(isExternal);

  const parsedSchema: ParsedSchema | null = (() => {
    if (!app?.config_schema) return null;
    try {
      return yaml.load(app.config_schema) as ParsedSchema;
    } catch {
      return null;
    }
  })();

  const installedIds = useMemo(
    () => new Set((Array.isArray(items) ? items : []).map((i) => i.tool_id ?? i.id)),
    [items],
  );
  const starredIds = useMemo(
    () => new Set((Array.isArray(stars) ? stars : []).map((s) => s.tool_id ?? s.id)),
    [stars],
  );

  const isInstalled = app ? installedIds.has(app.id) : false;
  const isStarred = app ? starredIds.has(app.id) : false;

  // Loading state
  if (isLoading) {
    return (
      <div className="flex flex-col">
        <div className="flex flex-col gap-6 border-b border-border bg-gradient-to-b from-surface-2/80 to-transparent p-6 md:p-8">
          <Skeleton className="h-4 w-24 rounded-lg" />
          <div className="flex items-start gap-5">
            <Skeleton className="size-[72px] rounded-2xl" />
            <div className="flex flex-col gap-3">
              <Skeleton className="h-8 w-56 rounded-lg" />
              <Skeleton className="h-4 w-80 rounded-lg" />
              <div className="flex gap-2">
                <Skeleton className="h-6 w-24 rounded-lg" />
                <Skeleton className="h-6 w-20 rounded-lg" />
              </div>
            </div>
          </div>
        </div>
        <div className="p-6 md:p-8">
          <Skeleton className="h-64 w-full rounded-xl" />
        </div>
      </div>
    );
  }

  // Not found
  if (!app) {
    return (
      <div className="p-6">
        <EmptyState
          icon={<span className="text-3xl">🔍</span>}
          title="App not found"
          message="The app you are looking for does not exist or has been removed."
          actionLabel="Back to Apps"
          actionHref="/"
        />
      </div>
    );
  }

  // Full-screen embed for installed embedded apps
  if (isInstalled && !isExternal) {
    const toggleSidebar = () => {
      const stored = localStorage.getItem("forge_sidebar_collapsed");
      const next = stored !== "true";
      localStorage.setItem("forge_sidebar_collapsed", String(next));
      // Dispatch storage event so sidebar component picks it up
      window.dispatchEvent(new Event("forge-sidebar-toggle"));
    };

    return (
      <div className="flex h-full flex-col">
        {/* Chrome bar */}
        <div className="relative flex h-10 shrink-0 items-center border-b border-border bg-gradient-to-b from-surface-2/80 to-surface px-3">
          {/* Left: navigation */}
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={toggleSidebar}
              aria-label="Toggle sidebar"
              className="text-text-muted hover:text-foreground"
            >
              <PanelLeftClose className="size-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="xs"
              nativeButton={false}
              render={<Link href="/" />}
              className="text-text-muted"
            >
              ← Apps
            </Button>
          </div>

          {/* Center: app identity */}
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 flex items-center gap-2">
            <AppIcon name={app.name} slug={app.slug} icon={app.icon} size={20} />
            <span className="text-[13px] font-semibold text-foreground">{app.name}</span>
          </div>

          {/* Right: actions */}
          <div className="ml-auto flex items-center gap-1">
            <StarButton toolId={app.id} isStarred={isStarred} size="sm" />
            <Button
              variant="ghost"
              size="xs"
              nativeButton={false}
              render={<Link href={`/apps/${slug}?tab=overview`} />}
              className="text-text-muted hover:text-foreground"
            >
              Details
            </Button>
          </div>
        </div>
        <div className="flex-1">
          <AppEmbed slug={slug} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      {/* Hero section */}
      <div className="relative flex flex-col gap-6 border-b border-border bg-gradient-to-b from-surface-2/80 via-surface-2/30 to-transparent p-6 md:p-8 md:pb-8">
        {/* Subtle radial glow behind icon */}
        <div className="absolute top-12 left-12 size-32 rounded-full bg-primary/[0.04] blur-3xl pointer-events-none" />

        <div className="relative flex items-center gap-1.5 text-xs">
          <Link href="/" className="text-white/45 hover:text-white/80 transition-colors">
            Apps
          </Link>
          <span className="text-white/25">/</span>
          <span className="text-white/85 font-medium">{app.name}</span>
        </div>

        <div className="relative flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-5">
            <AppIcon name={app.name} slug={app.slug} icon={app.icon} size={64} className="shadow-[0_8px_30px_rgba(0,0,0,0.25)]" />
            <div className="flex flex-col gap-2">
              <div className="flex flex-col gap-1">
                <h1 className="text-[26px] font-bold tracking-[-0.03em] text-white/98">
                  {app.name}
                </h1>
                {app.tagline && (
                  <p className="text-[15px] font-normal leading-relaxed text-white/65 max-w-lg">
                    {app.tagline}
                  </p>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-3 text-[13px] text-text-muted">
                <span className="font-medium text-text-secondary">{app.author_name || "Unknown"}</span>
                {app.category && (
                  <Badge variant="secondary">{app.category}</Badge>
                )}
              </div>

              {/* Stat pills */}
              <div className="flex flex-wrap items-center gap-2 pt-1">
                {app.install_count != null && (
                  <StatPill icon={<Users className="size-3" />}>
                    {formatCount(app.install_count)} {app.install_count === 1 ? "install" : "installs"}
                  </StatPill>
                )}
                {reviews && reviews.length >= 3 && app.avg_rating != null && app.avg_rating > 0 && (
                  <StatPill icon={<Star className="size-3 fill-yellow-400 text-yellow-400" />}>
                    {app.avg_rating.toFixed(1)} rating
                    <span className="text-white/40 ml-0.5">({reviews.length})</span>
                  </StatPill>
                )}
                {app.delivery === "external" && (
                  <StatPill icon={<Download className="size-3" />}>
                    Desktop app
                  </StatPill>
                )}
                {app.created_at && (
                  <StatPill icon={<Clock className="size-3" />}>
                    {humanDate(app.created_at)}
                  </StatPill>
                )}
              </div>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2">
            <InstallButton
              toolId={app.id}
              slug={app.slug}
              isInstalled={isInstalled}
              delivery={app.delivery}
            />
            <ShareButton slug={app.slug} />
            <StarButton toolId={app.id} isStarred={isStarred} />
            {app.source_url && (
              <Button
                variant="ghost"
                size="icon"
                nativeButton={false}
                render={
                  <a
                    href={app.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  />
                }
              >
                <ExternalLink className="size-4" />
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-col gap-8 p-6 md:p-8">

      {/* Tabs */}
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          {!isExternal && <TabsTrigger value="open">Open App</TabsTrigger>}
        </TabsList>

        {/* Overview tab */}
        <TabsContent value="overview">
          <div className="flex flex-col gap-8 pt-6 lg:flex-row">
            {/* Main content */}
            <div className="flex flex-1 flex-col gap-8 min-w-0">
              {/* External app control panel */}
              {isExternal && isInstalled && (
                <ExternalControlPanel
                  app={app}
                  isInstalled={isInstalled}
                  onUninstall={async () => {
                    await uninstallApp(app.id);
                  }}
                />
              )}

              {/* Install progress for external apps not yet installed */}
              {isExternal && !isInstalled && (
                <InstallProgress
                  toolId={app.id}
                  slug={app.slug}
                  agentAvailable={agentAvailable ?? false}
                  installCommand={app.install_command}
                  installMeta={app.install_meta}
                  autoInstall={autoInstall}
                  onInstalled={() => mutateItems()}
                />
              )}

              {/* Config wizard or setup skill — onboarding */}
              {parsedSchema ? (
                <div className="relative overflow-hidden rounded-2xl border border-primary/20 bg-gradient-to-r from-primary/[0.06] to-primary/[0.02] p-6">
                  <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,_var(--tw-gradient-stops))] from-primary/[0.06] to-transparent pointer-events-none" />
                  <div className="relative flex flex-col gap-4">
                    <div className="flex items-center gap-3">
                      <div className="flex size-10 items-center justify-center rounded-xl bg-primary/10 ring-1 ring-primary/20">
                        <Settings className="size-5 text-primary" />
                      </div>
                      <div className="flex flex-col gap-0.5">
                        <span className="text-[15px] font-semibold text-foreground">
                          Configure {app.name}
                        </span>
                        <span className="text-[13px] text-text-secondary">
                          Set up this app with a step-by-step wizard. Your answers will generate the configuration files automatically.
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={() => setWizardOpen(true)}
                      className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-[13px] font-semibold text-primary-foreground shadow-[0_1px_2px_rgba(0,0,0,0.3),inset_0_1px_0_rgba(255,255,255,0.1)] transition-all hover:brightness-110 w-fit"
                    >
                      <Sparkles className="size-3.5" />
                      Configure
                    </button>
                  </div>
                </div>
              ) : app.setup_skill_id ? (
                <SetupSkillCard skillId={app.setup_skill_id} appName={app.name} isInstalled={isInstalled} />
              ) : null}

              {/* Config Wizard modal */}
              {wizardOpen && parsedSchema && (
                <ConfigWizard
                  schema={parsedSchema}
                  slug={slug}
                  userProfile={{ name: undefined, email: undefined }}
                  onComplete={() => {
                    setWizardOpen(false);
                    mutateItems();
                  }}
                  onClose={() => setWizardOpen(false)}
                />
              )}

              {/* About */}
              {app.description && (
                <div className="flex flex-col gap-3">
                  <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/40">
                    About this app
                  </h3>
                  <p className="whitespace-pre-wrap text-[15px] leading-[1.7] text-text-secondary">
                    {app.description}
                  </p>
                </div>
              )}

              {/* Co-installs */}
              <CoInstallCards toolId={app.id} />

              {/* Reviews */}
              <div className="flex flex-col gap-5">
                <div className="flex items-center justify-between">
                  <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/40">
                    Reviews
                  </h3>
                  {reviews && reviews.length > 0 && (
                    <span className="text-xs text-text-muted tabular-nums">
                      {reviews.length} review{reviews.length !== 1 ? "s" : ""}
                    </span>
                  )}
                </div>
                {/* Aggregate rating */}
                {reviews && reviews.length > 0 && (() => {
                  const avg = reviews.reduce((s, r) => s + r.rating, 0) / reviews.length;
                  const dist = [5, 4, 3, 2, 1].map(n => ({
                    stars: n,
                    count: reviews.filter(r => r.rating === n).length,
                    pct: (reviews.filter(r => r.rating === n).length / reviews.length) * 100,
                  }));
                  return (
                    <div className="flex gap-6 rounded-2xl border border-border bg-card p-5 items-center">
                      <div className="flex flex-col items-center gap-1 pr-2">
                        <span className="text-4xl font-bold tabular-nums text-foreground">{avg.toFixed(1)}</span>
                        <div className="flex gap-0.5">
                          {[1,2,3,4,5].map(i => (
                            <Star key={i} className={`size-3.5 ${i <= Math.round(avg) ? "fill-yellow-400 text-yellow-400" : "text-border-strong"}`} />
                          ))}
                        </div>
                        <span className="text-[11px] text-text-muted mt-0.5">{reviews.length} ratings</span>
                      </div>
                      <div className="flex flex-1 flex-col gap-1.5">
                        {dist.map(d => (
                          <div key={d.stars} className="flex items-center gap-2">
                            <span className="w-3 text-right text-[11px] tabular-nums text-text-muted">{d.stars}</span>
                            <div className="flex-1 h-1.5 rounded-full bg-surface-2 overflow-hidden">
                              <div className="h-full rounded-full bg-yellow-400/80 transition-all" style={{ width: `${d.pct}%` }} />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })()}

                <ReviewForm
                  toolId={app.id}
                  onSubmitted={() => mutateReviews()}
                />
                {reviews && reviews.length > 0 ? (
                  <div className="flex flex-col gap-3">
                    {reviews.map((review) => (
                      <ReviewCard
                        key={review.id}
                        rating={review.rating}
                        userName={review.author_name || review.user_name}
                        date={review.created_at}
                        text={review.note || review.text}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-4 rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 text-center">
                    <p className="text-sm font-medium text-white/75">Be the first to review this app</p>
                    <p className="text-xs text-white/45">Share your experience to help others decide.</p>
                  </div>
                )}
              </div>
            </div>

            {/* Metadata sidebar */}
            <div className="flex flex-col gap-4 lg:w-72 lg:shrink-0">
              <div className="flex flex-col gap-0.5 rounded-2xl border border-border bg-card p-5">
                <h4 className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-text-muted/70">
                  Details
                </h4>
                <DetailRow label="Author" value={app.author_name || "Unknown"} />
                {app.category && <DetailRow label="Category" value={app.category} />}
                <DetailRow label="Type" value={isExternal ? "Desktop app" : "Embedded"} />
                {app.install_count != null && (
                  <DetailRow label="Installs" value={formatCount(app.install_count)} />
                )}
                {reviews && reviews.length >= 3 && app.avg_rating != null && app.avg_rating > 0 && (
                  <DetailRow label="Rating" value={`${app.avg_rating.toFixed(1)} / 5 (${reviews.length} reviews)`} />
                )}
                <DetailRow label="Version" value={`v${app.version}`} />
                {app.created_at && (
                  <DetailRow
                    label="Published"
                    value={new Date(app.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                  />
                )}
                {app.deployed_at && (
                  <DetailRow
                    label="Updated"
                    value={new Date(app.deployed_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                  />
                )}
              </div>

              {app.source_url && (
                <a
                  href={app.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-2 rounded-xl border border-border bg-card px-4 py-2.5 text-[13px] font-medium text-text-secondary transition-colors hover:border-border-strong hover:text-foreground"
                >
                  <ExternalLink className="size-3.5" />
                  View source code
                </a>
              )}
            </div>
          </div>
        </TabsContent>

        {/* Open App tab */}
        <TabsContent value="open">
          <div className="flex flex-col gap-5 pt-6">
            {!isInstalled && (
              <div className="relative overflow-hidden rounded-2xl border border-primary/20 bg-gradient-to-r from-primary/[0.06] to-primary/[0.02] px-6 py-5">
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-primary/[0.08] to-transparent pointer-events-none" />
                <div className="relative flex items-center justify-between gap-4">
                  <div className="flex flex-col gap-1">
                    <span className="text-[15px] font-semibold text-foreground">
                      You&apos;re previewing {app.name}
                    </span>
                    <span className="text-[13px] text-text-secondary">
                      Install to save your data, unlock all features, and add it to your collection.
                    </span>
                  </div>
                  <InstallButton
                    toolId={app.id}
                    slug={app.slug}
                    isInstalled={isInstalled}
                    delivery={app.delivery}
                    size="default"
                  />
                </div>
              </div>
            )}
            <div className="relative">
              {/* Window frame header */}
              <div className="flex h-8 items-center gap-2 rounded-t-2xl border border-b-0 border-border bg-surface-2/80 px-3">
                <div className="flex gap-1.5">
                  <span className="size-2.5 rounded-full bg-border-strong" />
                  <span className="size-2.5 rounded-full bg-border-strong" />
                  <span className="size-2.5 rounded-full bg-border-strong" />
                </div>
                <span className="flex-1 text-center text-[11px] text-text-muted">{app.name}</span>
              </div>
              <div className="h-[620px] overflow-hidden rounded-b-2xl border border-t-0 border-border shadow-[0_12px_40px_rgba(0,0,0,0.3)]">
                <AppEmbed slug={slug} preview={!isInstalled} />
              </div>
            </div>
          </div>
        </TabsContent>
      </Tabs>
      </div>
    </div>
  );
}

function SetupSkillCard({ skillId, appName, isInstalled }: { skillId: number; appName: string; isInstalled: boolean }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    const cmd = `claude "Run the setup skill for ${appName} — read the skill at /skills/${skillId} and walk me through configuring the app"`;
    await navigator.clipboard.writeText(cmd);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative overflow-hidden rounded-2xl border border-primary/20 bg-gradient-to-r from-primary/[0.06] to-primary/[0.02] p-6">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,_var(--tw-gradient-stops))] from-primary/[0.06] to-transparent pointer-events-none" />
      <div className="relative flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-xl bg-primary/10 ring-1 ring-primary/20">
            <Sparkles className="size-5 text-primary" />
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="text-[15px] font-semibold text-foreground">
              {isInstalled ? `Set up ${appName} with AI` : `AI-assisted setup available`}
            </span>
            <span className="text-[13px] text-text-secondary">
              {isInstalled
                ? "A setup agent will configure this app for you — ask your preferences, write config files, verify everything works. Takes ~3 minutes."
                : `Install ${appName} first, then use the setup agent to configure it for your workflow. No manual config editing needed.`}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href={`/skills/${skillId}`}
            className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-[13px] font-semibold text-primary-foreground shadow-[0_1px_2px_rgba(0,0,0,0.3),inset_0_1px_0_rgba(255,255,255,0.1)] transition-all hover:brightness-110"
          >
            <Sparkles className="size-3.5" />
            View Setup Skill
          </Link>
          {isInstalled && (
            <button
              onClick={handleCopy}
              className="flex items-center gap-2 rounded-xl border border-border bg-card px-4 py-2.5 text-[13px] font-medium text-text-secondary transition-colors hover:border-border-strong hover:text-foreground"
            >
              {copied ? <Check className="size-3.5 text-green-400" /> : <Copy className="size-3.5" />}
              {copied ? "Copied!" : "Copy setup command"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function StatPill({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-1.5 rounded-lg bg-surface-2 px-2.5 py-1 text-xs text-text-secondary ring-1 ring-border">
      <span className="text-text-muted">{icon}</span>
      <span className="font-medium">{children}</span>
    </div>
  );
}

function humanDate(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 86400) return "Added today";
  if (diff < 172800) return "Added yesterday";
  if (diff < 604800) return `Added ${Math.floor(diff / 86400)}d ago`;
  if (diff < 2592000) return `Added ${Math.floor(diff / 604800)}w ago`;
  return "Added " + new Date(iso).toLocaleDateString("en-US", { month: "short", year: "numeric" });
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-white/[0.06] last:border-0">
      <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/40">{label}</span>
      <span className="text-[13px] font-medium text-white/90">{value}</span>
    </div>
  );
}

function ShareButton({ slug }: { slug: string }) {
  const [copied, setCopied] = useState(false);

  const handleShare = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const url = `${window.location.origin}/apps/${slug}`;
    await navigator.clipboard.writeText(url);
    setCopied(true);
    const { toast } = await import("sonner");
    toast.success("Link copied to clipboard");
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Button variant="outline" size="sm" onClick={handleShare} className="gap-1.5">
      {copied ? <Check className="size-3.5 text-green-400" /> : <Share2 className="size-3.5" />}
      Share
    </Button>
  );
}

function formatCount(n: number): string {
  if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, "") + "k";
  return String(n);
}
