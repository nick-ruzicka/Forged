"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogOverlay,
  DialogPortal,
} from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { X, ChevronLeft, ChevronRight, Check, Loader2, Sparkles } from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SchemaField {
  key: string;
  prompt: string;
  type: "string" | "url" | "list" | "freeform_file";
  source?: string;
  required?: boolean;
  validation?: string;
}

interface ProfileField {
  key: string;
  prompt: string;
  type: string;
  source?: string;
  required?: boolean;
}

interface ConfigFileSection {
  name: string;
  prompt?: string;
  fields: {
    key: string;
    prompt: string;
    type: string;
    required?: boolean;
    validation?: string;
  }[];
}

interface ConfigFile {
  path: string;
  template?: string;
  format?: string;
  sections?: ConfigFileSection[];
}

export interface ParsedSchema {
  profile_fields?: ProfileField[];
  config_files?: ConfigFile[];
  verification?: {
    command: string;
    success_pattern: string;
  };
}

export interface ConfigWizardProps {
  schema: ParsedSchema;
  slug: string;
  userProfile: { name?: string; email?: string };
  onComplete: () => void;
  onClose: () => void;
}

// ---------------------------------------------------------------------------
// Group fields into sections (3-6 fields per screen)
// ---------------------------------------------------------------------------

interface WizardSection {
  title: string;
  subtitle?: string;
  fields: SchemaField[];
}

function buildSections(schema: ParsedSchema): WizardSection[] {
  const sections: WizardSection[] = [];

  // Profile fields as one section
  if (schema.profile_fields && schema.profile_fields.length > 0) {
    sections.push({
      title: "Your Profile",
      subtitle: "Basic information used across your apps",
      fields: schema.profile_fields.map((pf) => ({
        key: pf.key,
        prompt: pf.prompt,
        type: (pf.type as SchemaField["type"]) || "string",
        source: pf.source,
        required: pf.required,
      })),
    });
  }

  // Config file sections
  if (schema.config_files) {
    for (const cf of schema.config_files) {
      if (cf.sections) {
        for (const sec of cf.sections) {
          // Each schema section becomes one wizard section
          const fields: SchemaField[] = sec.fields.map((f) => ({
            key: `${sec.name}.${f.key}`,
            prompt: f.prompt,
            type: (f.type as SchemaField["type"]) || "string",
            required: f.required,
            validation: f.validation,
          }));
          if (fields.length > 0) {
            sections.push({
              title: formatSectionTitle(sec.name),
              subtitle: sec.prompt,
              fields,
            });
          }
        }
      }
    }
  }

  return sections;
}

function formatSectionTitle(name: string): string {
  return name
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ---------------------------------------------------------------------------
// Resolve auto-fill
// ---------------------------------------------------------------------------

function resolveSource(
  source: string | undefined,
  profile: { name?: string; email?: string },
): string | undefined {
  if (!source) return undefined;
  if (source === "forge.user.name") return profile.name;
  if (source === "forge.user.email") return profile.email;
  return undefined;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ConfigWizard({
  schema,
  slug,
  userProfile,
  onComplete,
  onClose,
}: ConfigWizardProps) {
  const sections = buildSections(schema);
  const totalSections = sections.length;

  const [sectionIdx, setSectionIdx] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const sec of sections) {
      for (const f of sec.fields) {
        const auto = resolveSource(f.source, userProfile);
        if (auto) init[f.key] = auto;
      }
    }
    return init;
  });
  const [autoFilled] = useState<Set<string>>(() => {
    const s = new Set<string>();
    for (const sec of sections) {
      for (const f of sec.fields) {
        if (resolveSource(f.source, userProfile)) s.add(f.key);
      }
    }
    return s;
  });
  const [showSummary, setShowSummary] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; message?: string } | null>(null);

  const firstInputRef = useRef<HTMLInputElement | HTMLTextAreaElement>(null);

  useEffect(() => {
    const timer = setTimeout(() => firstInputRef.current?.focus(), 150);
    return () => clearTimeout(timer);
  }, [sectionIdx, showSummary]);

  const currentSection = sections[sectionIdx];

  const setValue = useCallback(
    (key: string, val: string) => {
      setAnswers((prev) => ({ ...prev, [key]: val }));
    },
    [],
  );

  const canAdvance = () => {
    if (!currentSection) return false;
    for (const f of currentSection.fields) {
      if (f.required && !(answers[f.key] ?? "").trim()) return false;
    }
    return true;
  };

  const handleNext = () => {
    if (!canAdvance()) return;
    if (sectionIdx < totalSections - 1) {
      setSectionIdx(sectionIdx + 1);
    } else {
      setShowSummary(true);
    }
  };

  const handleBack = () => {
    if (showSummary) {
      setShowSummary(false);
      return;
    }
    if (sectionIdx > 0) setSectionIdx(sectionIdx - 1);
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const res = await api<{ success?: boolean; message?: string; files_written?: string[]; errors?: string[] }>(
        `/tools/${slug}/configure`,
        {
          method: "POST",
          body: JSON.stringify({ answers }),
        },
      );
      if (res?.success) {
        setResult({ ok: true, message: `Configuration saved. Files written: ${(res.files_written || []).join(", ")}` });
      } else {
        const errs = res?.errors || [];
        setResult({ ok: false, message: errs.length > 0 ? errs.join("\n") : "Configuration failed" });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Configuration failed";
      setResult({ ok: false, message: msg });
    } finally {
      setSubmitting(false);
    }
  };

  const progress = showSummary ? 100 : ((sectionIdx + 1) / totalSections) * 100;

  if (totalSections === 0) {
    return (
      <Dialog open onOpenChange={(open) => !open && onClose()}>
        <DialogPortal>
          <DialogOverlay />
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="w-full max-w-lg rounded-2xl border border-border bg-card p-8 text-center shadow-[0_20px_60px_rgba(0,0,0,0.4)]">
              <p className="text-text-secondary">No configuration fields found.</p>
              <Button className="mt-4" onClick={onClose}>Close</Button>
            </div>
          </div>
        </DialogPortal>
      </Dialog>
    );
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogPortal>
        <DialogOverlay />
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="relative flex w-full max-w-xl flex-col rounded-2xl border border-border bg-card shadow-[0_20px_60px_rgba(0,0,0,0.4)]">
            {/* Close */}
            <button
              onClick={onClose}
              className="absolute top-4 right-4 z-10 rounded-lg p-1.5 text-text-muted transition-colors hover:bg-surface-2 hover:text-foreground"
            >
              <X className="size-4" />
            </button>

            {/* Progress */}
            <div className="px-6 pt-6 pb-2">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-medium uppercase tracking-widest text-text-muted">
                  {showSummary
                    ? "Review & Confirm"
                    : `Section ${sectionIdx + 1} of ${totalSections}`}
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
                <div
                  className="h-full rounded-full bg-primary transition-all duration-300 ease-out"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto px-6 py-5" style={{ maxHeight: "60vh" }}>
              {result ? (
                <div className="flex flex-col items-center gap-4 py-4 text-center">
                  <div
                    className={`flex size-14 items-center justify-center rounded-2xl ${
                      result.ok
                        ? "bg-green-500/10 ring-1 ring-green-500/20"
                        : "bg-destructive/10 ring-1 ring-destructive/20"
                    }`}
                  >
                    {result.ok ? (
                      <Check className="size-7 text-green-400" />
                    ) : (
                      <X className="size-7 text-destructive" />
                    )}
                  </div>
                  <div className="flex flex-col gap-1">
                    <h3 className="text-lg font-semibold text-foreground">
                      {result.ok ? "Configuration Complete" : "Configuration Failed"}
                    </h3>
                    <p className="text-[13px] text-text-secondary max-w-sm whitespace-pre-wrap">
                      {result.message}
                    </p>
                  </div>
                  <Button
                    className="mt-2"
                    onClick={result.ok ? onComplete : () => setResult(null)}
                  >
                    {result.ok ? "Done" : "Try Again"}
                  </Button>
                </div>
              ) : showSummary ? (
                <div className="flex flex-col gap-4">
                  <h3 className="text-lg font-semibold text-foreground">
                    Review your configuration
                  </h3>
                  <div className="flex flex-col gap-4">
                    {sections.map((sec) => (
                      <div key={sec.title} className="flex flex-col gap-2">
                        <span className="text-[11px] font-semibold uppercase tracking-widest text-text-muted/70">
                          {sec.title}
                        </span>
                        <div className="rounded-xl border border-border bg-surface-2/30 p-3">
                          {sec.fields.map((f) => (
                            <div key={f.key} className="flex items-start justify-between py-1.5 border-b border-border/30 last:border-0">
                              <span className="text-xs text-text-muted">{f.prompt.replace(/\?$/, "")}</span>
                              <span className="text-xs font-medium text-foreground max-w-[50%] text-right truncate">
                                {answers[f.key] || <span className="italic text-text-muted">—</span>}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                /* Section view — multiple fields per screen */
                <div className="flex flex-col gap-5">
                  <div className="flex flex-col gap-1">
                    <h3 className="text-[18px] font-semibold text-foreground">
                      {currentSection.title}
                    </h3>
                    {currentSection.subtitle && (
                      <p className="text-[14px] text-white/60">{currentSection.subtitle}</p>
                    )}
                  </div>

                  <div className="flex flex-col gap-4">
                    {currentSection.fields.map((field, i) => (
                      <div key={field.key} className="flex flex-col gap-1.5">
                        <label className="text-[13px] font-medium text-foreground/80">
                          {field.prompt}
                          {field.required && <span className="text-primary ml-1">*</span>}
                        </label>

                        {field.type === "list" || field.type === "freeform_file" ? (
                          <Textarea
                            ref={i === 0 ? (firstInputRef as React.Ref<HTMLTextAreaElement>) : undefined}
                            value={answers[field.key] ?? ""}
                            onChange={(e) => setValue(field.key, e.target.value)}
                            rows={field.type === "freeform_file" ? 8 : 3}
                            placeholder={
                              field.type === "list"
                                ? "One item per line..."
                                : "Enter content..."
                            }
                            className="resize-y text-sm"
                          />
                        ) : (
                          <Input
                            ref={i === 0 ? (firstInputRef as React.Ref<HTMLInputElement>) : undefined}
                            type={field.type === "url" ? "url" : "text"}
                            value={answers[field.key] ?? ""}
                            onChange={(e) => setValue(field.key, e.target.value)}
                            placeholder={field.type === "url" ? "https://..." : ""}
                            className="text-sm"
                          />
                        )}

                        {autoFilled.has(field.key) && answers[field.key] && (
                          <span className="text-[11px] text-text-muted italic">
                            Auto-filled from your profile
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Footer nav */}
            {!result && (
              <div className="flex items-center justify-between border-t border-border px-6 py-4">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleBack}
                  disabled={sectionIdx === 0 && !showSummary}
                >
                  <ChevronLeft className="size-3.5" />
                  Back
                </Button>

                {showSummary ? (
                  <Button onClick={handleSubmit} disabled={submitting}>
                    {submitting ? (
                      <>
                        <Loader2 className="size-3.5 animate-spin" />
                        Configuring...
                      </>
                    ) : (
                      <>
                        <Sparkles className="size-3.5" />
                        Configure
                      </>
                    )}
                  </Button>
                ) : (
                  <Button onClick={handleNext} disabled={!canAdvance()}>
                    {sectionIdx < totalSections - 1 ? (
                      <>
                        Next
                        <ChevronRight className="size-3.5" />
                      </>
                    ) : (
                      "Review"
                    )}
                  </Button>
                )}
              </div>
            )}
          </div>
        </div>
      </DialogPortal>
    </Dialog>
  );
}
