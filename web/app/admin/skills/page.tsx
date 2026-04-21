"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight, Shield, ArrowLeft } from "lucide-react";
import useSWR from "swr";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { api, getAdminKey } from "@/lib/api";

interface CompanySkill {
  id: number;
  slug: string;
  title: string;
  description: string;
  content: string;
  required_sections: string[];
  behavior_tests: { prompt: string; expected: string; check: string }[];
  category: string;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export default function AdminSkillsPage() {
  const adminKey = typeof window !== "undefined" ? getAdminKey() : null;

  const { data, isLoading } = useSWR<{ skills: CompanySkill[] }>(
    adminKey ? "/admin/company-skills" : null,
    () => api<{ skills: CompanySkill[] }>("/admin/company-skills"),
  );

  const skills = data?.skills || [];

  if (!adminKey) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 p-12 text-center">
        <Shield className="size-8 text-text-muted" />
        <p className="text-sm text-text-secondary">Admin access required.</p>
        <Button variant="outline" size="sm" nativeButton={false} render={<Link href="/admin" />}>
          Go to Admin
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8 p-6 md:p-8 max-w-4xl">
      {/* Header */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2 text-[13px] text-text-muted">
          <Link href="/admin" className="hover:text-foreground transition-colors">Admin</Link>
          <span>/</span>
          <span className="text-foreground">Company Skills</span>
        </div>
        <h1 className="text-[28px] font-bold tracking-[-0.03em] text-white/98">
          Company Skills
        </h1>
        <p className="text-sm text-white/55 leading-relaxed">
          Governance rules and domain knowledge that get baked into new Claude Code projects.
        </p>
      </div>

      {/* Skills list */}
      {isLoading ? (
        <div className="flex flex-col gap-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24 rounded-2xl" />
          ))}
        </div>
      ) : skills.length === 0 ? (
        <div className="text-sm text-text-muted">No company skills configured.</div>
      ) : (
        <div className="flex flex-col gap-4">
          {skills.map((skill) => (
            <SkillRow key={skill.id} skill={skill} />
          ))}
        </div>
      )}
    </div>
  );
}

function SkillRow({ skill }: { skill: CompanySkill }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-2xl border border-border bg-card">
      {/* Header — always visible */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-start gap-4 p-5 text-left"
      >
        <div className="mt-1">
          {expanded ? (
            <ChevronDown className="size-4 text-text-muted" />
          ) : (
            <ChevronRight className="size-4 text-text-muted" />
          )}
        </div>
        <div className="flex flex-1 flex-col gap-1.5">
          <div className="flex items-center gap-2">
            <span className="text-[15px] font-semibold text-foreground">{skill.title}</span>
            <Badge variant="secondary" className="text-[10px]">{skill.category}</Badge>
            {skill.is_default && (
              <Badge variant="default" className="text-[10px]">DEFAULT</Badge>
            )}
          </div>
          <span className="text-[13px] text-text-secondary leading-relaxed">
            {skill.description}
          </span>
          <div className="flex items-center gap-3 text-[11px] text-text-muted">
            <span>{skill.required_sections?.length || 0} required sections</span>
            <span>{skill.behavior_tests?.length || 0} behavior tests</span>
            <span className="font-mono">{skill.slug}</span>
          </div>
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-border px-5 pb-5 pt-4">
          <div className="flex flex-col gap-5">
            {/* Markdown content */}
            <div className="flex flex-col gap-2">
              <span className="text-[11px] font-semibold uppercase tracking-widest text-text-muted/70">
                Content
              </span>
              <pre className="max-h-64 overflow-y-auto rounded-xl bg-surface-2 p-4 font-mono text-[12px] leading-relaxed text-text-muted ring-1 ring-border whitespace-pre-wrap">
                {skill.content}
              </pre>
            </div>

            {/* Required sections */}
            {skill.required_sections && skill.required_sections.length > 0 && (
              <div className="flex flex-col gap-2">
                <span className="text-[11px] font-semibold uppercase tracking-widest text-text-muted/70">
                  Required Sections
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {skill.required_sections.map((s, i) => (
                    <span key={i} className="rounded-lg bg-surface-2 px-2.5 py-1 font-mono text-[11px] text-text-secondary ring-1 ring-border">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Behavior tests */}
            {skill.behavior_tests && skill.behavior_tests.length > 0 && (
              <div className="flex flex-col gap-2">
                <span className="text-[11px] font-semibold uppercase tracking-widest text-text-muted/70">
                  Behavior Tests
                </span>
                <div className="flex flex-col gap-2">
                  {skill.behavior_tests.map((test, i) => (
                    <div key={i} className="rounded-xl bg-surface-2/50 p-3 ring-1 ring-border">
                      <div className="flex flex-col gap-1">
                        <span className="text-[12px] font-medium text-foreground">
                          Adversarial prompt:
                        </span>
                        <span className="text-[12px] text-text-secondary italic">
                          &quot;{test.prompt}&quot;
                        </span>
                        <span className="text-[11px] text-text-muted mt-1">
                          Expected: {test.expected}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
