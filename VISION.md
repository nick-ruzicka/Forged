# Forge — Vision, Methodology & Product Strategy

*Last updated: April 20, 2026*

---

## What Forge is

Forge is an internal AI tool marketplace. Employees build small web apps and prompt-based skills, publish them to a shared catalog, install in one click, and a 6-agent governance pipeline reviews every submission before it reaches the catalog.

The short version: **an app store for your company's AI tools, with governance built in.**

---

## Why this exists

Companies are already building internal AI tools. The problem isn't building — it's everything after:

- **Discovery.** Your teammate built a deal scorecard in Claude Code last Tuesday. You don't know it exists. You build your own on Thursday.
- **Trust.** Someone pastes HTML into a shared tool. Does it exfiltrate data? Nobody checks.
- **Adoption.** The tool exists but nobody uses it because onboarding is "read the README."
- **Measurement.** Which tools are actually useful? Which are shelf-ware? Nobody knows.

Forge solves all four. One place to find, trust, use, and measure internal tools.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Next.js 16 Frontend                     │
│   Catalog · Skills · My Forge · Publish · Admin · Wizard   │
├──────────────────────────────────────────────────────────┤
│                     Flask API                              │
│   /tools · /skills · /me · /admin · /configure             │
├──────────────┬───────────────────────────────────────────┤
│  PostgreSQL  │         Forge Agent (localhost:4242)        │
│  Tools       │   Install · Launch · Monitor · Usage        │
│  Skills      │   Open Terminal · Claude Exec               │
│  Reviews     │   Process monitoring · Session tracking     │
│  Schemas     │   Config writing · Verification             │
├──────────────┴───────────────────────────────────────────┤
│              6-Agent Governance Pipeline                    │
│   Classifier → Security Scanner → Red Team →               │
│   QA Tester → Synthesizer → Human Override                 │
└──────────────────────────────────────────────────────────┘
```

## The Three Classes of Apps

### Class A — Embedded web apps (the core)
HTML + JS stored in Forge's database, served in an iframe. Zero install friction, runs anywhere Forge runs. Examples: Hebbia Signal Engine, Deal Scorecard, Pipeline Forecast, Competitive Battle Card.

This is the reason Forge exists. Employees build these in Claude Code, publish, teammates install and use them the same day.

### Class B — External/CLI apps (the ecosystem)
Desktop apps, CLI tools, Git repos. Installed via forge-agent (brew, git clone, npm). Forge tracks usage, provides onboarding, monitors processes. Examples: Fabric (40k star AI framework), OpenSuperWhisper.

The "Getting Started" card tells users exactly how to use the app — step-by-step commands with "Run in Terminal" buttons that open Terminal.app with the command pre-filled.

### Class C — Backend-aware apps (the unlock)
Frontend is a Class A app served from Forge. Backend runs on a VPS or locally in Docker. Example: Hebbia Signal Engine with a live Python backend on Hetzner.

---

## The Governance Pipeline

Every submission goes through 6 agents before reaching the catalog:

1. **Classifier** — identifies category, output type, confidence score
2. **Security Scanner** — XSS, data exfiltration, eval patterns, PII risk
3. **Red Team** — actively tries to break the app (5 attack templates)
4. **QA Tester** — verifies functionality, checks edge cases
5. **Synthesizer** — aggregates all agent outputs, verdict + confidence
6. **Human Override** — admin can approve/reject with reasoning

This is the part most people skip. Building tools is easy. Governing them at scale is the hard problem. A company with 500 employees generating AI tools needs a review process that doesn't require a committee.

---

## Skills — Institutional Knowledge Capture

Skills are SKILL.md files that teach Claude new workflows. Unlike apps, skills don't need UI — they're knowledge, packaged as text.

**Why skills matter more than apps long-term:** Building an app requires HTML/JS skills. Writing a skill requires describing a workflow in plain English. The barrier to contribution is 10x lower. Every employee has workflows they repeat — debugging patterns, data analysis steps, review checklists. Skills capture that knowledge and make it reusable across the entire company.

The catalog has 31 real skills from Anthropic's official repo and the superpowers plugin. Users subscribe, view full prompt content, fork, and share.

---

## Onboarding Architecture — The Config Schema System

The gap between "installed" and "actually useful" kills adoption of every internal tool.

### The problem
Most apps need configuration — API keys, preferences, credentials, project-specific settings. Each handles this differently. READMEs go unread. Setup scripts are intimidating. 90% of tools die in the first 5 minutes because the user can't get past setup.

### The solution: config schemas
Each app declares its configuration surface in a `forge.config.yml`:

```yaml
schema_version: 1
app: career-ops
profile_fields:
  - key: full_name
    prompt: "What's your full name?"
    source: forge.user.name  # auto-fill from Forge profile
config_files:
  - path: config/profile.yml
    template: config/profile.example.yml
    sections:
      - name: target_roles
        fields:
          - key: primary
            prompt: "What roles are you targeting?"
            type: list
verification:
  command: npm run doctor
  success_pattern: "All checks passed"
```

A universal config agent reads the schema, walks the user through a Typeform-style wizard, writes the config files, and runs verification. The user answers questions; the platform writes YAML.

### Where this goes
- **Auto-fill from profile.** First app asks your name and email. Every subsequent app auto-fills.
- **Cross-app credential sharing.** "You're installing career-ops, which needs an OpenAI key. You already configured one for Fabric. Reuse it?"
- **Config drift detection.** Weekly check: do your configs still match the schema?
- **Auto-generation from GitHub.** Point Forge at a GitHub URL, it reads the README, generates a config schema via Claude, wizard appears automatically.

---

## Design Decisions & Tradeoffs

### Self-contained HTML apps (not Docker)
Early versions used Docker for every app — 30-second cold starts, complex networking, Docker dependency. Self-contained HTML loads instantly, has no dependencies, and can be published by anyone who writes HTML. Tradeoff: no server-side logic. For dashboards and tools, this is fine. For complex apps, use the external model.

### Skills as SKILL.md (not a custom format)
Uses Claude Code's native skill format. Any skill in Forge also works in Claude Code directly. No lock-in.

### Forge-agent as local daemon (not cloud)
Runs on localhost:4242. Installs software on YOUR machine, monitors YOUR processes. Nothing leaves your machine unless you explicitly share. Privacy by architecture.

### allow-same-origin for installed apps only
Installed apps (governance-reviewed) get `allow-same-origin` so VPS iframes work. Preview mode (unapproved) stays strict. Security boundary at the trust boundary.

### Governance as agents (not rules)
A rule-based scanner misses novel attacks. An LLM-based red team reasons about intent. Tradeoff: cost (6 API calls per submission) and latency (30-60s per review).

---

## Ideas I Haven't Built (Roadmap)

### The "app builder" skill
A skill that generates self-contained HTML apps from a description. "Build me a deal scorecard." The skill knows Forge's design system, produces polished HTML. Every employee becomes an app developer. This turns Forge from a marketplace into a creation platform.

### Declared capabilities + governance enforcement
Config schemas declare what an app needs: `network: [salesforce_api]`, `writes: [local_disk]`. The governance pipeline enforces these — an app that declares "file converter" but requests network access to 10 external domains gets flagged automatically.

### Team stacks (voluntary, not surveillance)
Employees voluntarily list what tools they use — like a public dotfiles repo. "Nick's stack: Cursor, Claude Code, Linear, Fabric." Social discovery without surveillance.

### Fork lineage as institutional knowledge
When someone forks a signal engine to create a travel-tech version, the catalog shows the lineage. Over time: which forks get more installs than the original? Which patterns spread across teams?

### Usage data as behavioral signal
Every tool run is logged. "Reps who run ICP Qualification before calls create 3x more pipeline." That's the weekly digest to sales leaders. Nobody else has this data.

---

## Competing Approaches I Considered

| Approach | Why Not |
|----------|---------|
| Slack apps / ChatGPT plugins | Tied to one platform. Internal tools shouldn't require a Slack/OpenAI subscription. |
| SharePoint / Confluence | Document systems, not app platforms. Can't install, monitor, or govern. |
| Retool / Budibase | Low-code builder for one developer. Forge is a marketplace for an entire company. |
| Just use GitHub | GitHub is for code, not for non-technical employees discovering tools. |
| Ramp Glass | Glass is Ramp-only, skills-only. Forge is portable, handles apps + skills + governance. |

---

## What makes this proof-of-work, not a side project

- **Full-stack**: Flask + Next.js 16 + PostgreSQL + local daemon + headless browser testing
- **6-agent governance pipeline**: real security scanning, red teaming, QA — not a checkbox
- **Two delivery models**: embedded HTML + external installs via brew/git/Docker
- **Config schema architecture**: structured onboarding with universal wizard
- **31 real skills**: imported from Anthropic's official repo, full content
- **Social features**: installs, reviews, co-installs, team activity, usage tracking
- **8 apps with real data**: signal engines, deal scorecards, pipeline forecasts, battle cards
- **Security hardened**: 5 production-risk vulnerabilities identified and fixed
- **Built in ~2 weeks** of focused work with Claude Code

---

## Product Principles

1. **Real apps only.** The catalog is curated. Every fake or placeholder app dilutes the signal.

2. **Governance invisible when working, visible when not.** Users never see the 6-agent pipeline for approved apps. They see clean installs. When something's blocked, the reason is crystal clear.

3. **Security as architecture, not ceremony.** Sandbox isolation, CVE scanning, origin pinning, audit logs — boundaries that can't be crossed, not features to sell.

4. **Social signals drive discovery.** The primary organizing principle is "what your team uses," not taxonomies. Role-aware recommendations, install counts, fork chains, co-install patterns.

5. **Publish must be as good as install.** 60 seconds from "I have this app" to "my team can use it."

6. **Onboarding is the product.** An installed app that nobody can configure is an uninstalled app. The config wizard, getting started guides, and setup skills are as important as the catalog.

---

## The 5-Minute Pitch

> Companies use AI to build internal tools now. The bottleneck isn't building — it's governance, distribution, and adoption.
>
> Forge solves all three. An employee builds a tool, publishes it to Forge, a 6-agent pipeline reviews it for security and quality, and teammates install it in one click. Skills let anyone share prompt-based workflows without writing code.
>
> The platform tracks which tools people actually use, surfaces social signals, and provides guided onboarding so tools don't die from "read the README" friction.
>
> What's next: a config schema system that makes credentials portable across tools, auto-generated onboarding from GitHub READMEs, and a skill that generates apps from descriptions — turning every employee into a tool builder.
