"use client";

import { useState, useEffect, useCallback } from "react";
import { X, Check, Loader2, FolderPlus, ChevronDown, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogOverlay,
  DialogPortal,
} from "@/components/ui/dialog";
import { api } from "@/lib/api";

interface CompanySkill {
  slug: string;
  title: string;
  description: string;
  is_default: boolean;
  category: string;
}

interface NewProjectModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function NewProjectModal({ open, onOpenChange }: NewProjectModalProps) {
  // Form state
  const [slug, setSlug] = useState("");
  const [slugError, setSlugError] = useState("");
  const [description, setDescription] = useState("");
  const [selectedSkills, setSelectedSkills] = useState<Set<string>>(new Set());

  // Company skills
  const [skills, setSkills] = useState<CompanySkill[]>([]);
  const [skillsLoading, setSkillsLoading] = useState(true);

  // Submission
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // Success state
  const [result, setResult] = useState<{
    path: string;
    slug: string;
    skills: string[];
    files: string[];
    claudeMdPreview?: string;
  } | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);

  // Load company skills
  useEffect(() => {
    if (!open) return;
    setSkillsLoading(true);
    api<{ skills: CompanySkill[] }>("/company-skills")
      .then((data) => {
        const s = data.skills || [];
        setSkills(s);
        // Pre-select defaults
        const defaults = new Set(s.filter((sk) => sk.is_default).map((sk) => sk.slug));
        setSelectedSkills(defaults);
      })
      .catch(() => setSkills([]))
      .finally(() => setSkillsLoading(false));
  }, [open]);

  // Reset on close
  useEffect(() => {
    if (!open) {
      setSlug("");
      setSlugError("");
      setDescription("");
      setError("");
      setResult(null);
      setPreviewOpen(false);
    }
  }, [open]);

  // Validate slug
  const validateSlug = useCallback((val: string) => {
    if (!val) {
      setSlugError("");
      return;
    }
    if (!/^[a-z0-9][a-z0-9-]{0,48}[a-z0-9]?$/.test(val)) {
      setSlugError("Lowercase letters, numbers, and hyphens only (3-50 chars)");
    } else {
      setSlugError("");
    }
  }, []);

  const toggleSkill = (skillSlug: string) => {
    setSelectedSkills((prev) => {
      const next = new Set(prev);
      if (next.has(skillSlug)) {
        next.delete(skillSlug);
      } else {
        next.add(skillSlug);
      }
      return next;
    });
  };

  const handleSubmit = async () => {
    setError("");
    if (!slug || slug.length < 3) {
      setError("Project name must be at least 3 characters");
      return;
    }
    if (slugError) return;

    setSubmitting(true);
    try {
      const res = await api<{
        project_id: number;
        slug: string;
        path: string;
        skills_applied: string[];
        files_created: string[];
      }>("/projects/scaffold", {
        method: "POST",
        body: JSON.stringify({
          slug,
          description,
          skills: Array.from(selectedSkills),
        }),
      });

      // Try to read the CLAUDE.md preview
      let preview = "";
      try {
        const previewRes = await fetch(`/api/projects/scaffold/preview?path=${encodeURIComponent(res.path)}`);
        if (previewRes.ok) {
          const data = await previewRes.json();
          preview = data.preview || "";
        }
      } catch {
        // Preview is optional
      }

      setResult({
        path: res.path,
        slug: res.slug,
        skills: res.skills_applied,
        files: res.files_created,
        claudeMdPreview: preview,
      });

      // Try to open terminal
      try {
        await fetch("/api/forge-agent/open-terminal", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Forge-User-Id": localStorage.getItem("forge_user_id") || "",
          },
          body: JSON.stringify({ command: `cd ${res.path} && npx claude`, cwd: res.path }),
        });
      } catch {
        // Terminal launch is best-effort
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Scaffolding failed";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPortal>
        <DialogOverlay />
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="relative flex w-full max-w-lg flex-col rounded-2xl border border-border bg-card shadow-[0_20px_60px_rgba(0,0,0,0.4)]">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border px-6 py-4">
              <div className="flex items-center gap-3">
                <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10">
                  <FolderPlus className="size-4 text-primary" />
                </div>
                <h2 className="text-[16px] font-semibold text-foreground">
                  {result ? "Project Created" : "New Claude Code Project"}
                </h2>
              </div>
              <button
                onClick={() => onOpenChange(false)}
                className="rounded-lg p-1.5 text-text-muted hover:bg-surface-2 hover:text-foreground transition-colors"
              >
                <X className="size-4" />
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto px-6 py-5" style={{ maxHeight: "70vh" }}>
              {result ? (
                /* ── Success state ── */
                <div className="flex flex-col gap-5">
                  <div className="flex items-center gap-3">
                    <div className="flex size-10 items-center justify-center rounded-full bg-green-500/10 ring-1 ring-green-500/20">
                      <Check className="size-5 text-green-400" />
                    </div>
                    <div className="flex flex-col gap-0.5">
                      <span className="text-[14px] font-semibold text-foreground">
                        Project scaffolded
                      </span>
                      <span className="text-[12px] text-text-muted font-mono">
                        {result.path}
                      </span>
                    </div>
                  </div>

                  <div className="rounded-xl bg-surface-2/50 p-4 text-[13px] text-text-secondary leading-relaxed">
                    Terminal opening with Claude Code. Start building — the governance rules
                    are already loaded in CLAUDE.md.
                  </div>

                  {/* Skills applied */}
                  {result.skills.length > 0 && (
                    <div className="flex flex-col gap-2">
                      <span className="text-[11px] font-semibold uppercase tracking-widest text-text-muted/70">
                        Governance skills applied
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {result.skills.map((s) => (
                          <span key={s} className="rounded-full bg-primary/10 px-2.5 py-0.5 text-[11px] font-medium text-primary">
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* CLAUDE.md preview */}
                  {result.claudeMdPreview && (
                    <div className="flex flex-col gap-2">
                      <button
                        onClick={() => setPreviewOpen(!previewOpen)}
                        className="flex items-center gap-1.5 text-[12px] font-medium text-text-secondary hover:text-foreground transition-colors"
                      >
                        {previewOpen ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
                        Here&apos;s what got scaffolded
                      </button>
                      {previewOpen && (
                        <pre className="max-h-64 overflow-y-auto rounded-xl bg-surface-2 p-4 font-mono text-[11px] leading-relaxed text-text-muted ring-1 ring-border">
                          {result.claudeMdPreview}
                        </pre>
                      )}
                    </div>
                  )}

                  {/* Files created */}
                  <div className="flex flex-col gap-1.5">
                    <span className="text-[11px] font-semibold uppercase tracking-widest text-text-muted/70">
                      Files created
                    </span>
                    <div className="flex flex-col gap-0.5">
                      {result.files.map((f) => (
                        <span key={f} className="font-mono text-[11px] text-text-muted">{f}</span>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                /* ── Form ── */
                <div className="flex flex-col gap-5">
                  {/* Project name */}
                  <div className="flex flex-col gap-1.5">
                    <label className="text-[13px] font-medium text-foreground/80">
                      Project name <span className="text-primary">*</span>
                    </label>
                    <Input
                      value={slug}
                      onChange={(e) => {
                        const val = e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "");
                        setSlug(val);
                      }}
                      onBlur={() => validateSlug(slug)}
                      placeholder="my-deal-scorer"
                      className="font-mono text-sm"
                    />
                    {slugError && (
                      <span className="text-[11px] text-destructive">{slugError}</span>
                    )}
                    <span className="text-[11px] text-text-muted">
                      Creates ~/forge-projects/{slug || "..."}
                    </span>
                  </div>

                  {/* Description */}
                  <div className="flex flex-col gap-1.5">
                    <label className="text-[13px] font-medium text-foreground/80">
                      What does this tool do?
                    </label>
                    <Textarea
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      placeholder="Scores enterprise deals across 6 dimensions using Salesforce opportunity data..."
                      rows={2}
                      className="text-sm"
                    />
                  </div>

                  {/* Company skills */}
                  <div className="flex flex-col gap-2">
                    <label className="text-[13px] font-medium text-foreground/80">
                      Governance skills
                    </label>
                    {skillsLoading ? (
                      <div className="flex items-center gap-2 text-[12px] text-text-muted">
                        <Loader2 className="size-3 animate-spin" />
                        Loading skills...
                      </div>
                    ) : skills.length === 0 ? (
                      <span className="text-[12px] text-text-muted">No company skills configured</span>
                    ) : (
                      <div className="flex flex-col gap-2">
                        {skills.map((skill) => (
                          <button
                            key={skill.slug}
                            onClick={() => toggleSkill(skill.slug)}
                            className={`flex items-start gap-3 rounded-xl border p-3 text-left transition-colors ${
                              selectedSkills.has(skill.slug)
                                ? "border-primary/30 bg-primary/[0.06]"
                                : "border-border bg-transparent hover:border-border-strong"
                            }`}
                          >
                            <div className={`mt-0.5 flex size-4 shrink-0 items-center justify-center rounded border transition-colors ${
                              selectedSkills.has(skill.slug)
                                ? "border-primary bg-primary text-primary-foreground"
                                : "border-border-strong"
                            }`}>
                              {selectedSkills.has(skill.slug) && <Check className="size-2.5" />}
                            </div>
                            <div className="flex flex-col gap-0.5">
                              <span className="text-[13px] font-medium text-foreground">
                                {skill.title}
                                {skill.is_default && (
                                  <span className="ml-1.5 text-[10px] text-primary font-semibold">DEFAULT</span>
                                )}
                              </span>
                              <span className="text-[11px] text-text-muted leading-relaxed">
                                {skill.description}
                              </span>
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  {error && (
                    <div className="rounded-xl bg-destructive/10 px-4 py-3 text-[13px] text-destructive">
                      {error}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-end gap-3 border-t border-border px-6 py-4">
              {result ? (
                <Button onClick={() => onOpenChange(false)}>
                  Close
                </Button>
              ) : (
                <>
                  <Button variant="ghost" onClick={() => onOpenChange(false)}>
                    Cancel
                  </Button>
                  <Button onClick={handleSubmit} disabled={submitting || !slug || slug.length < 3}>
                    {submitting ? (
                      <>
                        <Loader2 className="size-3.5 animate-spin" />
                        Creating...
                      </>
                    ) : (
                      <>
                        <FolderPlus className="size-3.5" />
                        Create Project
                      </>
                    )}
                  </Button>
                </>
              )}
            </div>
          </div>
        </div>
      </DialogPortal>
    </Dialog>
  );
}
