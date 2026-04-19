"use client";

import { useState } from "react";
import { Star } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { postReview } from "@/lib/api";

interface ReviewFormProps {
  toolId: number;
  onSubmitted: () => void;
}

export function ReviewForm({ toolId, onSubmitted }: ReviewFormProps) {
  const [rating, setRating] = useState(0);
  const [hovered, setHovered] = useState(0);
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (rating === 0) {
      toast.error("Please select a rating");
      return;
    }

    setLoading(true);
    try {
      await postReview(toolId, rating, text);
      toast.success("Review submitted");
      setRating(0);
      setText("");
      onSubmitted();
    } catch {
      toast.error("Failed to submit review");
    } finally {
      setLoading(false);
    }
  }

  const starLabels = ["Poor", "Fair", "Good", "Great", "Excellent"];
  const activeValue = hovered || rating;

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-4 rounded-2xl border border-border bg-card p-5"
    >
      <span className="text-[13px] font-medium text-foreground">
        Leave a review
      </span>

      {/* Star input */}
      <div className="flex items-center gap-3">
        <div className="flex gap-1">
          {Array.from({ length: 5 }).map((_, i) => {
            const value = i + 1;
            const active = value <= activeValue;
            return (
              <button
                key={i}
                type="button"
                onClick={() => setRating(value)}
                onMouseEnter={() => setHovered(value)}
                onMouseLeave={() => setHovered(0)}
                className="rounded-md p-1 transition-transform hover:scale-110 active:scale-95"
              >
                <Star
                  className={`size-6 transition-colors duration-100 ${
                    active
                      ? "fill-yellow-400 text-yellow-400"
                      : "text-border-strong hover:text-text-muted"
                  }`}
                />
              </button>
            );
          })}
        </div>
        {activeValue > 0 && (
          <span className="text-xs font-medium text-text-muted animate-fade-in-up">
            {starLabels[activeValue - 1]}
          </span>
        )}
      </div>

      <Textarea
        placeholder="What was your experience like?"
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={3}
      />

      <Button
        type="submit"
        disabled={loading}
        size="sm"
        className="self-start"
      >
        {loading ? "Submitting..." : "Submit Review"}
      </Button>
    </form>
  );
}
