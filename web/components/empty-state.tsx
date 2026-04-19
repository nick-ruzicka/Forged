import Link from "next/link";
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
    <div className="relative flex flex-col items-center justify-center gap-5 py-20 text-center">
      {/* Atmospheric glow */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="size-40 rounded-full bg-primary/[0.03] blur-3xl" />
      </div>

      {icon && (
        <div className="relative flex size-16 items-center justify-center rounded-2xl bg-surface-2 ring-1 ring-border text-text-muted">
          {icon}
        </div>
      )}
      <div className="relative flex flex-col gap-1.5">
        <h3 className="text-base font-semibold text-foreground">{title}</h3>
        <p className="text-sm text-text-secondary max-w-sm leading-relaxed">{message}</p>
      </div>
      {actionLabel && actionHref && (
        <Button variant="default" size="sm" nativeButton={false} render={<Link href={actionHref} />}>
          {actionLabel}
        </Button>
      )}
      {actionLabel && onAction && !actionHref && (
        <Button variant="default" size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
