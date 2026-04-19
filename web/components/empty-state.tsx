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
    <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
      {icon && (
        <div className="text-text-muted">{icon}</div>
      )}
      <div className="flex flex-col gap-1">
        <h3 className="text-sm font-medium text-foreground">{title}</h3>
        <p className="text-sm text-text-secondary max-w-sm">{message}</p>
      </div>
      {actionLabel && actionHref && (
        <Button variant="default" size="sm" render={<Link href={actionHref} />}>
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
