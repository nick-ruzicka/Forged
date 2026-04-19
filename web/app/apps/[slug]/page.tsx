"use client";

import { use, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ExternalLink } from "lucide-react";
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

  const isExternal = app?.delivery === "external";
  const { data: agentAvailable } = useAgentAvailable(isExternal);

  const installedIds = useMemo(
    () => new Set((Array.isArray(items) ? items : []).map((i) => i.tool_id)),
    [items],
  );
  const starredIds = useMemo(
    () => new Set((Array.isArray(stars) ? stars : []).map((s) => s.tool_id)),
    [stars],
  );

  const isInstalled = app ? installedIds.has(app.id) : false;
  const isStarred = app ? starredIds.has(app.id) : false;

  // Loading state
  if (isLoading) {
    return (
      <div className="flex flex-col gap-6 p-6">
        <Skeleton className="h-5 w-20" />
        <div className="flex items-start gap-4">
          <Skeleton className="size-12 rounded-lg" />
          <div className="flex flex-col gap-2">
            <Skeleton className="h-7 w-48" />
            <Skeleton className="h-4 w-64" />
            <Skeleton className="h-4 w-32" />
          </div>
        </div>
        <Skeleton className="h-64 w-full rounded-lg" />
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

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Back link */}
      <Link
        href="/"
        className="text-sm text-text-muted hover:text-foreground transition-colors w-fit"
      >
        ← Apps
      </Link>

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-4">
          <span className="text-4xl">{app.icon || "📦"}</span>
          <div className="flex flex-col gap-1">
            <h1 className="text-2xl font-semibold text-foreground">
              {app.name}
            </h1>
            {app.tagline && (
              <p className="text-sm text-text-secondary">{app.tagline}</p>
            )}
            <div className="flex flex-wrap items-center gap-2 text-xs text-text-muted">
              <span>{app.author_name || "Unknown"}</span>
              {app.category && (
                <Badge variant="secondary">{app.category}</Badge>
              )}
              {app.install_count != null && (
                <span>{app.install_count} installs</span>
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

      {/* Tabs */}
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="open">Open App</TabsTrigger>
        </TabsList>

        {/* Overview tab */}
        <TabsContent value="overview">
          <div className="flex flex-col gap-6 pt-4">
            {/* Description */}
            {app.description && (
              <p className="whitespace-pre-wrap text-sm text-text-secondary">
                {app.description}
              </p>
            )}

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

            {/* Co-installs */}
            <CoInstallCards toolId={app.id} toolName={app.name} />

            {/* Reviews */}
            <div className="flex flex-col gap-4">
              <h2 className="text-lg font-semibold text-foreground">Reviews</h2>
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
                <p className="text-sm text-text-muted">No reviews yet.</p>
              )}
            </div>
          </div>
        </TabsContent>

        {/* Open App tab */}
        <TabsContent value="open">
          <div className="flex flex-col gap-4 pt-4">
            {!isInstalled && (
              <div className="flex items-center justify-between rounded-lg border border-border bg-surface p-3">
                <span className="text-sm text-text-secondary">
                  Sample data — install to make this yours
                </span>
                <InstallButton
                  toolId={app.id}
                  slug={app.slug}
                  isInstalled={isInstalled}
                  delivery={app.delivery}
                />
              </div>
            )}
            <div className="h-[600px] overflow-hidden rounded-lg border border-border">
              <AppEmbed slug={slug} />
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
