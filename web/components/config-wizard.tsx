"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
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
  section?: string;
  configPath?: string;
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
// Flatten schema into linear steps
// ---------------------------------------------------------------------------

function flattenFields(schema: ParsedSchema): SchemaField[] {
  const fields: SchemaField[] = [];

  if (schema.profile_fields) {
    for (const pf of schema.profile_fields) {
      fields.push({
        key: pf.key,
        prompt: pf.prompt,
        type: (pf.type as SchemaField["type"]) || "string",
        source: pf.source,
        required: pf.required,
        section: "Profile",
      });
    }
  }

  if (schema.config_files) {
    for (const cf of schema.config_files) {
      if (cf.sections) {
        for (const sec of cf.sections) {
          for (const f of sec.fields) {
            fields.push({
              key: f.key,
              prompt: f.prompt,
              type: (f.type as SchemaField["type"]) || "string",
              required: f.required,
              validation: f.validation,
              section: sec.name,
              configPath: cf.path,
            });
          }
        }
      }
    }
  }

  return fields;
}

// ---------------------------------------------------------------------------
// Resolve auto-fill value from profile
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
  const fields = flattenFields(schema);
  const totalSteps = fields.length;

  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const f of fields) {
      const auto = resolveSource(f.source, userProfile);
      if (auto) init[f.key] = auto;
    }
    return init;
  });
  const [autoFilled, setAutoFilled] = useState<Set<string>>(() => {
    const s = new Set<string>();
    for (const f of fields) {
      if (resolveSource(f.source, userProfile)) s.add(f.key);
    }
    return s;
  });
  const [showSummary, setShowSummary] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; message?: string } | null>(null);

  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement>(null);

  // Focus input on step change
  useEffect(() => {
    const timer = setTimeout(() => inputRef.current?.focus(), 100);
    return () => clearTimeout(timer);
  }, [step, showSummary]);

  const current = fields[step];

  const setValue = useCallback(
    (val: string) => {
      if (!current) return;
      setAnswers((prev) => ({ ...prev, [current.key]: val }));
      // Clear auto-fill tag once user edits
      if (autoFilled.has(current.key)) {
        setAutoFilled((prev) => {
          const next = new Set(prev);
          next.delete(current.key);
          return next;
        });
      }
    },
    [current, autoFilled],
  );

  const canAdvance = () => {
    if (!current) return false;
    const val = answers[current.key] ?? "";
    if (current.required && val.trim() === "") return false;
    return true;
  };

  const handleNext = () => {
    if (!canAdvance()) return;
    if (step < totalSteps - 1) {
      setStep(step + 1);
    } else {
      setShowSummary(true);
    }
  };

  const handleBack = () => {
    if (showSummary) {
      setShowSummary(false);
      return;
    }
    if (step > 0) setStep(step - 1);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey && current?.type !== "list" && current?.type !== "freeform_file") {
      e.preventDefault();
      handleNext();
    }
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const res = await api<{ message?: string; output?: string }>(
        `/tools/${slug}/configure`,
        {
          method: "POST",
          body: JSON.stringify({ answers }),
        },
      );
      setResult({ ok: true, message: res?.message || res?.output || "Configuration saved successfully." });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Configuration failed";
      setResult({ ok: false, message: msg });
    } finally {
      setSubmitting(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Progress bar
  // ---------------------------------------------------------------------------
  const progress = showSummary ? 100 : ((step + 1) / totalSteps) * 100;

  // Handle empty schema
  if (totalSteps === 0) {
    return (
      <Dialog open onOpenChange={(open) => !open && onClose()}>
        <DialogPortal>
          <DialogOverlay />
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="w-full max-w-lg rounded-2xl border border-border bg-card p-8 text-center shadow-[0_20px_60px_rgba(0,0,0,0.4)]">
              <p className="text-text-secondary">No configuration fields found in schema.</p>
              <Button className="mt-4" onClick={onClose}>Close</Button>
            </div>
          </div>
        </DialogPortal>
      </Dialog>
    );
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogPortal>
        <DialogOverlay />
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="relative flex w-full max-w-lg flex-col rounded-2xl border border-border bg-card shadow-[0_20px_60px_rgba(0,0,0,0.4)]">
            {/* Close button */}
            <button
              onClick={onClose}
              className="absolute top-4 right-4 rounded-lg p-1.5 text-text-muted transition-colors hover:bg-surface-2 hover:text-foreground"
            >
              <X className="size-4" />
            </button>

            {/* Progress bar */}
            <div className="px-6 pt-6 pb-2">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-medium uppercase tracking-widest text-text-muted">
                  {showSummary
                    ? "Review & Confirm"
                    : `Step ${step + 1} of ${totalSteps}`}
                </span>
                {current?.section && !showSummary && (
                  <span className="text-[11px] text-text-muted">{current.section}</span>
                )}
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
                <div
                  className="h-full rounded-full bg-primary transition-all duration-300 ease-out"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>

            {/* Content */}
            <div className="flex-1 px-6 py-6">
              {result ? (
                /* Result screen */
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
                    <p className="text-[13px] text-text-secondary max-w-sm">
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
                /* Summary */
                <div className="flex flex-col gap-4">
                  <h3 className="text-lg font-semibold text-foreground">
                    Review your configuration
                  </h3>
                  <div className="max-h-72 overflow-y-auto rounded-xl border border-border bg-surface-2/30 p-4">
                    <div className="flex flex-col gap-3">
                      {fields.map((f) => (
                        <div key={f.key} className="flex flex-col gap-0.5">
                          <span className="text-[11px] font-medium uppercase tracking-wider text-text-muted">
                            {f.key}
                          </span>
                          <span className="text-[13px] text-foreground break-words whitespace-pre-wrap">
                            {answers[f.key] || <span className="italic text-text-muted">empty</span>}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                /* Field step */
                <div className="flex flex-col gap-4" onKeyDown={handleKeyDown}>
                  <h3 className="text-lg font-semibold text-foreground leading-snug pr-8">
                    {current.prompt}
                  </h3>

                  {current.required && (
                    <span className="text-[11px] text-primary font-medium -mt-2">Required</span>
                  )}

                  {current.type === "list" || current.type === "freeform_file" ? (
                    <Textarea
                      ref={inputRef as React.Ref<HTMLTextAreaElement>}
                      value={answers[current.key] ?? ""}
                      onChange={(e) => setValue(e.target.value)}
                      rows={current.type === "freeform_file" ? 10 : 5}
                      placeholder={
                        current.type === "list"
                          ? "Enter one item per line..."
                          : "Enter content..."
                      }
                      className="resize-y"
                    />
                  ) : (
                    <Input
                      ref={inputRef as React.Ref<HTMLInputElement>}
                      type={current.type === "url" ? "url" : "text"}
                      value={answers[current.key] ?? ""}
                      onChange={(e) => setValue(e.target.value)}
                      placeholder={
                        current.type === "url"
                          ? "https://..."
                          : "Type your answer..."
                      }
                    />
                  )}

                  {autoFilled.has(current.key) && (
                    <span className="text-[11px] text-text-muted italic -mt-2">
                      (auto-filled from your profile)
                    </span>
                  )}

                  {current.validation && (
                    <span className="text-[11px] text-text-muted -mt-2">
                      {current.validation}
                    </span>
                  )}
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
                  disabled={step === 0 && !showSummary}
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
                    {step < totalSteps - 1 ? (
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
