"use client";

import { useCallback, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { submitSkill } from "@/lib/api";

const SKILL_CATEGORIES = [
  "Development",
  "Testing",
  "Debugging",
  "Planning",
  "Code Review",
  "Documents",
  "Other",
];

interface SubmitSkillDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmitted?: () => void;
}

export function SubmitSkillDialog({
  open,
  onOpenChange,
  onSubmitted,
}: SubmitSkillDialogProps) {
  const [title, setTitle] = useState("");
  const [useCase, setUseCase] = useState("");
  const [category, setCategory] = useState("Development");
  const [promptText, setPromptText] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [authorName, setAuthorName] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const resetForm = useCallback(() => {
    setTitle("");
    setUseCase("");
    setCategory("Development");
    setPromptText("");
    setSourceUrl("");
    setAuthorName("");
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!title.trim() || !useCase.trim() || !promptText.trim()) {
      toast.error("Please fill in all required fields");
      return;
    }
    setSubmitting(true);
    try {
      await submitSkill({
        title: title.trim(),
        use_case: useCase.trim(),
        category,
        prompt_text: promptText,
        source_url: sourceUrl.trim() || undefined,
        author_name: authorName.trim() || undefined,
      });
      toast.success("Skill submitted for review. You'll see it in My Forge \u2192 Submissions once approved.", {
        duration: 5000,
      });
      resetForm();
      onOpenChange(false);
      onSubmitted?.();
    } catch {
      toast.error("Failed to submit skill");
    } finally {
      setSubmitting(false);
    }
  }, [
    title,
    useCase,
    category,
    promptText,
    sourceUrl,
    authorName,
    resetForm,
    onOpenChange,
    onSubmitted,
  ]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Submit a Skill</DialogTitle>
          <DialogDescription>
            Share a SKILL.md file with the community.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-text-secondary">
              Title <span className="text-destructive">*</span>
            </label>
            <Input
              placeholder="e.g. TDD Coach"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-text-secondary">
              Use this when... <span className="text-destructive">*</span>
            </label>
            <Input
              placeholder="e.g. you want to write tests before code"
              value={useCase}
              onChange={(e) => setUseCase(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-text-secondary">
              Category
            </label>
            <Select value={category} onValueChange={(v) => v && setCategory(v)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SKILL_CATEGORIES.map((cat) => (
                  <SelectItem key={cat} value={cat}>
                    {cat}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-text-secondary">
              SKILL.md contents <span className="text-destructive">*</span>
            </label>
            <Textarea
              className="min-h-[160px] font-mono text-xs"
              placeholder="Paste your SKILL.md content here..."
              value={promptText}
              onChange={(e) => setPromptText(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-text-secondary">
              GitHub URL
            </label>
            <Input
              placeholder="https://github.com/..."
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-text-secondary">
              GitHub handle
            </label>
            <Input
              placeholder="@username"
              value={authorName}
              onChange={(e) => setAuthorName(e.target.value)}
            />
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
          >
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting ? "Submitting..." : "Submit"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
