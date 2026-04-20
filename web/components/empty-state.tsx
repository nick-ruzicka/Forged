import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  message: string;
  actionLabel?: string;
  actionHref?: string;
  onAction?: () => void;
}

export function EmptyState({
  icon,
  title,
  message,
  actionLabel,
  actionHref,
  onAction,
}: EmptyStateProps) {
  return (
    <div className="relative flex flex-col items-center justify-center gap-12 py-20 text-center">
      {/* Atmospheric glow */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="size-40 rounded-full bg-primary/[0.03] blur-3xl" />
      </div>

      {icon ? (
        <div className="relative flex size-24 items-center justify-center rounded-2xl text-white/[0.08]">
          {icon}
        </div>
      ) : (
        <EmptyShelfSvg />
      )}

      <div className="relative flex flex-col gap-4">
        <h3 className="text-base font-semibold text-white/90">{title}</h3>
        <p className="text-sm text-white/55 max-w-sm leading-relaxed">{message}</p>
      </div>

      {actionLabel && actionHref && (
        <Button variant="default" size="sm" nativeButton={false} render={<Link href={actionHref} />} className="gap-1.5">
          {actionLabel}
          <ArrowRight className="size-3.5" />
        </Button>
      )}
      {actionLabel && onAction && !actionHref && (
        <Button variant="default" size="sm" onClick={onAction} className="gap-1.5">
          {actionLabel}
          <ArrowRight className="size-3.5" />
        </Button>
      )}
    </div>
  );
}

function EmptyShelfSvg() {
  return (
    <svg width="96" height="96" viewBox="0 0 96 96" fill="none" xmlns="http://www.w3.org/2000/svg" className="relative">
      {/* Anvil / shelf motif */}
      <rect x="20" y="60" width="56" height="4" rx="2" stroke="rgba(255,255,255,0.08)" strokeWidth="1.5" fill="none" />
      <rect x="28" y="64" width="4" height="16" rx="1" stroke="rgba(255,255,255,0.08)" strokeWidth="1.5" fill="none" />
      <rect x="64" y="64" width="4" height="16" rx="1" stroke="rgba(255,255,255,0.08)" strokeWidth="1.5" fill="none" />
      {/* Empty box outline */}
      <rect x="36" y="36" width="24" height="24" rx="4" stroke="rgba(255,255,255,0.08)" strokeWidth="1.5" fill="none" strokeDasharray="4 3" />
      {/* Small accent */}
      <circle cx="48" cy="48" r="4" stroke="rgba(255,255,255,0.06)" strokeWidth="1" fill="none" />
    </svg>
  );
}
