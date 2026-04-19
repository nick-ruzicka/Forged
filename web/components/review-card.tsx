import { Star } from "lucide-react";

interface ReviewCardProps {
  rating: number;
  userName?: string;
  date?: string;
  text?: string;
}

export function ReviewCard({ rating, userName, date, text }: ReviewCardProps) {
  const initials = userName
    ? userName
        .split(" ")
        .map((w) => w[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "A";

  const formattedDate = date
    ? new Date(date).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : null;

  return (
    <div className="flex gap-3.5 rounded-2xl border border-border bg-card p-4">
      {/* Avatar */}
      <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-surface-2 text-xs font-semibold text-text-muted ring-1 ring-border">
        {initials}
      </div>

      <div className="flex flex-1 flex-col gap-2">
        {/* Header row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-[13px] font-medium text-foreground">
              {userName || "Anonymous"}
            </span>
            {formattedDate && (
              <>
                <span className="text-text-muted/40">·</span>
                <span className="text-xs text-text-muted">{formattedDate}</span>
              </>
            )}
          </div>
          <div className="flex gap-0.5">
            {Array.from({ length: 5 }).map((_, i) => (
              <Star
                key={i}
                className={`size-3.5 ${
                  i < rating
                    ? "fill-yellow-400 text-yellow-400"
                    : "text-border-strong"
                }`}
              />
            ))}
          </div>
        </div>

        {/* Review text */}
        {text && (
          <p className="text-[14px] leading-relaxed text-text-secondary">
            {text}
          </p>
        )}
      </div>
    </div>
  );
}
