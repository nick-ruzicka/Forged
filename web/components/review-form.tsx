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

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      {/* Star input */}
      <div className="flex gap-1">
        {Array.from({ length: 5 }).map((_, i) => {
          const value = i + 1;
          const active = value <= (hovered || rating);
          return (
            <button
              key={i}
              type="button"
              onClick={() => setRating(value)}
              onMouseEnter={() => setHovered(value)}
              onMouseLeave={() => setHovered(0)}
              className="p-0.5"
            >
              <Star
                className={`size-5 transition-colors ${
                  active
                    ? "fill-yellow-400 text-yellow-400"
                    : "text-text-muted"
                }`}
              />
            </button>
          );
        })}
      </div>

      <Textarea
        placeholder="Write a review..."
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={3}
      />

      <Button type="submit" disabled={loading} size="sm" className="self-start">
        {loading ? "Submitting..." : "Submit Review"}
      </Button>
    </form>
  );
}
