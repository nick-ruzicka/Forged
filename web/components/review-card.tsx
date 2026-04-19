import { Star } from "lucide-react";

interface ReviewCardProps {
  rating: number;
  userName?: string;
  date?: string;
  text?: string;
}

export function ReviewCard({ rating, userName, date, text }: ReviewCardProps) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
      <div className="flex items-center justify-between">
        <div className="flex gap-0.5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Star
              key={i}
              className={`size-4 ${
                i < rating
                  ? "fill-yellow-400 text-yellow-400"
                  : "text-text-muted"
              }`}
            />
          ))}
        </div>
        {date && (
          <span className="text-xs text-text-muted">
            {new Date(date).toLocaleDateString()}
          </span>
        )}
      </div>
      {text && (
        <p className="text-sm text-text-secondary">{text}</p>
      )}
      <span className="text-xs text-text-muted">
        {userName || "Anonymous"}
      </span>
    </div>
  );
}
