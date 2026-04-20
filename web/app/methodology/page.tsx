export default function MethodologyPage() {
  return (
    <div className="flex flex-col gap-16 p-6 md:p-8 max-w-3xl">
      {/* Hero */}
      <div className="flex flex-col gap-4">
        <h1 className="text-[32px] font-bold tracking-[-0.03em] text-white/98">
          Methodology & Vision
        </h1>
        <p className="text-[16px] leading-[1.7] text-white/60">
          How we think about AI enablement, why Forge is built this way,
          and where it&apos;s going.
        </p>
      </div>

      {/* The Problem */}
      <Section title="The Problem">
        <p>
          Every company is building internal AI tools. The problem isn&apos;t building — it&apos;s
          everything after. Your teammate built a deal scorecard last Tuesday. You don&apos;t
          know it exists. You build your own on Thursday.
        </p>
        <p>
          Someone pastes HTML into a shared tool. Does it exfiltrate data? Nobody checks.
          The tool exists but nobody uses it because onboarding is &quot;read the README.&quot;
          Which tools are actually useful? Nobody knows.
        </p>
        <p>
          This is the AI enablement gap: the distance between &quot;we have AI tools&quot; and
          &quot;our team actually uses AI tools effectively.&quot;
        </p>
      </Section>

      {/* The Thesis */}
      <Section title="Our Thesis">
        <Callout>
          AI tools are only as valuable as their adoption rate. A tool nobody
          can find, trust, or configure is a tool nobody uses.
        </Callout>
        <p>
          Forge closes this gap with three layers:
        </p>
        <NumberedList items={[
          {
            title: "Discovery through social signals",
            body: "What your team installs, what gets forked, what gets high reviews. Not taxonomies — behavior.",
          },
          {
            title: "Trust through automated governance",
            body: "Every submission goes through a 6-agent security review. No committee, no bottleneck, no manual process.",
          },
          {
            title: "Adoption through guided onboarding",
            body: "Config schemas, setup wizards, usage examples. The gap between 'installed' and 'productive' should be 90 seconds, not 90 minutes.",
          },
        ]} />
      </Section>

      {/* AI Enablement */}
      <Section title="AI Enablement, Practically">
        <p>
          &quot;AI enablement&quot; usually means training sessions and prompt libraries.
          We think it means something more concrete:
        </p>
        <Grid items={[
          {
            icon: "🔧",
            title: "Tools, not training",
            body: "An employee doesn't need a workshop on 'how to use AI.' They need a deal scorecard that works. Build the tool, distribute it, track whether people use it.",
          },
          {
            icon: "📄",
            title: "Skills as institutional knowledge",
            body: "Every team has workflows they repeat — debugging patterns, analysis steps, review checklists. Skills capture this knowledge as reusable prompts. The barrier to contribute is writing English, not code.",
          },
          {
            icon: "📊",
            title: "Measurement, not vibes",
            body: "Which tools do people actually open? How often? Which teams adopt fastest? Usage data tells you where AI is landing and where it isn't. You can't improve what you don't measure.",
          },
          {
            icon: "🛡️",
            title: "Governance as enablement",
            body: "The biggest blocker to AI adoption isn't technology — it's permission. When IT trusts the governance layer, they greenlight the platform. Governance doesn't slow teams down; it's the reason teams get to move fast.",
          },
        ]} />
      </Section>

      {/* The Governance Model */}
      <Section title="The Governance Model">
        <p>
          Every app and skill submitted to Forge goes through a 6-agent review pipeline
          before reaching the catalog. This runs automatically — no human review committee required.
        </p>
        <Pipeline steps={[
          { agent: "Classifier", job: "Identifies what the submission is — category, type, confidence" },
          { agent: "Security Scanner", job: "Checks for XSS, data exfiltration, eval patterns, PII risk" },
          { agent: "Red Team", job: "Actively tries to break it — 5 attack templates, adversarial testing" },
          { agent: "Hardener", job: "Patches what it can — CSP headers, input sanitization, safe defaults" },
          { agent: "QA Tester", job: "Verifies it actually works — renders, loads, handles edge cases" },
          { agent: "Synthesizer", job: "Aggregates all results — single verdict with confidence score" },
        ]} />
        <p>
          The point: when someone installs a tool from the catalog, they know it&apos;s been
          reviewed. They don&apos;t have to trust the author. They trust the process.
        </p>
      </Section>

      {/* Two Kinds of Apps */}
      <Section title="Two Ways to Build">
        <div className="flex flex-col gap-6">
          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6">
            <h4 className="text-[15px] font-semibold text-white/90 mb-2">Embedded Apps</h4>
            <p className="text-[14px] text-white/55 leading-[1.7]">
              Self-contained HTML that runs inside Forge. No server, no Docker, no infrastructure.
              An employee writes HTML in Claude Code, publishes it, teammates use it immediately.
              This is how most internal tools should be built — simple, fast, zero-maintenance.
            </p>
          </div>
          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6">
            <h4 className="text-[15px] font-semibold text-white/90 mb-2">External Apps</h4>
            <p className="text-[14px] text-white/55 leading-[1.7]">
              Desktop software, CLI tools, open-source projects. Forge installs them (via brew, git clone, etc.),
              provides step-by-step setup guides, tracks usage, and monitors health. The app runs on your machine;
              Forge is the control plane.
            </p>
          </div>
        </div>
      </Section>

      {/* The Onboarding Problem */}
      <Section title="The Onboarding Problem">
        <Callout>
          An installed app that nobody can configure is an uninstalled app.
        </Callout>
        <p>
          Most software dies in the first 5 minutes. The user installs it, sees a config
          file they don&apos;t understand, and closes the tab. README-driven onboarding has
          a near-zero completion rate for non-developers.
        </p>
        <p>
          Forge&apos;s approach: <strong>config schemas</strong>. Each app declares its configuration
          surface in a structured format. A universal wizard reads the schema and walks the
          user through setup — one question at a time, auto-filling from their profile where
          possible. The user answers questions; the platform writes config files.
        </p>
        <p>
          For external apps, a &quot;Run in Terminal&quot; button opens your terminal with the
          command pre-filled. No copy-paste, no guessing what to type.
        </p>
      </Section>

      {/* Where This Goes */}
      <Section title="Where This Goes">
        <NumberedList items={[
          {
            title: "Auto-generated onboarding from GitHub",
            body: "Point Forge at a GitHub URL. It reads the README, generates a config schema, and produces an onboarding wizard. Any open-source tool becomes one-click install with guided setup.",
          },
          {
            title: "The app builder skill",
            body: "A skill that generates self-contained HTML apps from a description. 'Build me a deal scorecard.' The skill knows Forge's design system, produces polished HTML. Every employee becomes a tool builder.",
          },
          {
            title: "Cross-app credential sharing",
            body: "Set your OpenAI key once. Every app that needs it auto-fills. Rotate a token and all apps update. Credentials become platform-level, not per-app.",
          },
          {
            title: "Behavioral analytics for leadership",
            body: "'Reps who use the ICP Qualification tool before calls create 3x more pipeline.' Usage data that connects tool adoption to business outcomes — the kind of closed-loop measurement most AI programs skip.",
          },
          {
            title: "Fork lineage as institutional knowledge",
            body: "When someone forks a signal engine for a new vertical, the catalog shows the family tree. Over time: which patterns spread? Which tools evolve? This is how institutional knowledge compounds.",
          },
        ]} />
      </Section>

      {/* Open Questions */}
      <Section title="Open Questions & Active Experiments">
        <div className="flex flex-col gap-4">
          <Question
            q="Should Forge detect what software you use, or should users declare it?"
            a="Detection is powerful but feels like surveillance. Declaration is voluntary but has low adoption. We're leaning toward 'team stacks' — voluntary profiles of what you use, like a public dotfiles repo. Social proof without the privacy cost."
          />
          <Question
            q="How do you govern apps that make external API calls?"
            a="Config schemas declare capabilities: network access, file system writes, credential requirements. The governance pipeline can validate these claims. An app that says 'file converter' but calls 10 external APIs gets flagged. Not built yet — this is the next enforcement layer."
          />
          <Question
            q="Can non-developers really build tools?"
            a="With Claude Code, yes — if the output format is constrained. Self-contained HTML is the right constraint. The 'app builder' skill would go further: describe what you want, get a polished app. The barrier drops from 'can write code' to 'can describe a workflow.'"
          />
          <Question
            q="Does this work at 10,000 employees?"
            a="The catalog scales. The governance pipeline scales (it's automated). The identity system doesn't scale yet — it needs real auth, per-team isolation, and role-based access. That's the enterprise unlock."
          />
        </div>
      </Section>

      {/* Footer */}
      <div className="border-t border-white/[0.06] pt-8 text-[13px] text-white/40">
        Built by Nick Ruzicka · April 2026 · This document is a living artifact — it changes as the product evolves.
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Components
// ---------------------------------------------------------------------------

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-5">
      <h2 className="text-[22px] font-bold tracking-[-0.02em] text-white/95">{title}</h2>
      <div className="flex flex-col gap-4 text-[15px] leading-[1.75] text-white/60">
        {children}
      </div>
    </div>
  );
}

function Callout({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-xl border-l-2 border-[#6366f1] bg-[#6366f1]/[0.04] px-5 py-4 text-[15px] font-medium text-white/80 leading-[1.6]">
      {children}
    </div>
  );
}

function NumberedList({ items }: { items: { title: string; body: string }[] }) {
  return (
    <div className="flex flex-col gap-4">
      {items.map((item, i) => (
        <div key={i} className="flex gap-4">
          <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-white/[0.04] text-[13px] font-bold text-white/50 ring-1 ring-white/[0.06]">
            {i + 1}
          </span>
          <div className="flex flex-col gap-1 pt-0.5">
            <span className="text-[15px] font-semibold text-white/85">{item.title}</span>
            <span className="text-[14px] text-white/50 leading-[1.7]">{item.body}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function Grid({ items }: { items: { icon: string; title: string; body: string }[] }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {items.map((item, i) => (
        <div key={i} className="flex flex-col gap-2 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-5">
          <span className="text-xl">{item.icon}</span>
          <span className="text-[14px] font-semibold text-white/85">{item.title}</span>
          <span className="text-[13px] text-white/50 leading-[1.7]">{item.body}</span>
        </div>
      ))}
    </div>
  );
}

function Pipeline({ steps }: { steps: { agent: string; job: string }[] }) {
  return (
    <div className="flex flex-col gap-0">
      {steps.map((step, i) => (
        <div key={i} className="flex items-start gap-4 relative">
          {/* Line */}
          {i < steps.length - 1 && (
            <div className="absolute left-[13px] top-8 bottom-0 w-px bg-white/[0.06]" />
          )}
          {/* Dot */}
          <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-[#6366f1]/10 ring-1 ring-[#6366f1]/20 mt-0.5">
            <div className="size-2 rounded-full bg-[#6366f1]" />
          </div>
          {/* Content */}
          <div className="flex flex-col gap-0.5 pb-5">
            <span className="text-[14px] font-semibold text-white/85">{step.agent}</span>
            <span className="text-[13px] text-white/45">{step.job}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function Question({ q, a }: { q: string; a: string }) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-5">
      <p className="text-[14px] font-semibold text-white/80 mb-2">{q}</p>
      <p className="text-[13px] text-white/45 leading-[1.7]">{a}</p>
    </div>
  );
}
