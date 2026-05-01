# Design Patterns to Steal for Forged
Research on the internal AI tool platform category, what the leaders are doing, and what's worth copying.

---

## The market shape, fast

Three competitors that matter right now, ranked by how close they are to Forged's space:

**Retool AppGen (closest competitor, $3B valuation).** Already shipping exactly what Forged is designed to ship: enterprise-grade governed app generation via natural language, semantic objects (their name for company skills), SSO/RBAC/audit inherited by default, Claude Code + MCP integration, React output, customer-hosted deployments. Their public CEO framing in "Code is free. Now what?" is verbatim Forged's thesis — governance at the platform layer as the unlock for speed.

**Lovable (adjacent, not enterprise-focused).** Non-engineer app builder, chat-driven, React output, Supabase backend, community templates, remix pattern. Consumer-y. Focused on individuals and small teams, not internal enterprise tooling. Their weakness: no governance, no audit trail, no team primitives. Their strength: the fastest "idea to working app" experience in the market and genuinely polished UI by default.

**AgentUI (new challenger positioning against Retool).** Explicitly markets itself as "Retool alternative for non-technical teams." Their whole homepage is quotes from ops directors saying "we tried Retool for months and our non-technical team couldn't build anything." That framing tells you where Retool is vulnerable.

Plus several AI governance platforms (Credo AI, Holistic AI, CloudEagle, Singulr) but those sell to CISOs and compliance officers — different buyer, different category, not Forged's competition.

---

## Patterns worth stealing, ranked by value

### 1. Chat-left / preview-right split
The single most important UX pattern in this category. Every leader uses it: Retool AppGen, Lovable, UX Pilot, Bolt, v0, Cursor.

Left pane: natural language conversation with the AI. User types what they want, AI responds, changes happen live.

Right pane: the app as it actually renders, updating in real time as the conversation progresses.

Why this works: the builder stays in one place. No tab switching. The preview is always live, so trust builds incrementally — you see each change happen. The conversation history is the audit trail of how the app evolved.

**For Forged:** the "New Claude Code Project" flow should not be a five-step modal that dumps the user into a terminal. It should be this split view. Left: chat with Claude scaffolding the project through iterative prompts, with company skills surfaced as selectable context. Right: live preview of the generated CLAUDE.md, the project structure, and eventually the tool itself as it gets built.

This is a bigger change than it sounds. It moves Forged from "ceremony-heavy admin tool" to "conversational builder with governance baked in."

### 2. Semantic objects as company skills
Retool's "semantic objects" are exactly what you're calling company skills, but they've pushed the pattern further than you have. Worth studying.

Their version:
- Skills/objects package data, permissions, and actions into reusable units
- Professional developers (or admins) define them with the right queries, permissions, and UI templates
- Non-engineers compose apps from these objects via natural language
- Objects carry governance with them — if the "customer record" object has row-level permissions baked in, every app built with it inherits those permissions

What this unlocks that plain skills don't: the object is both a knowledge primitive AND a functional primitive. It's not just "here's the company's rules for how to query Salesforce." It's "here's a pre-built, permissioned, governed Salesforce customer-lookup component that any builder can drop into their app and have it just work."

**For Forged:** your current company skills are prompt snippets. The v2 version should be prompt snippets + working code scaffolds + permission configs + visual components. A "salesforce-queries" skill shouldn't just tell Claude Code to filter by org — it should ship with a working, governed Salesforce query handler and a pre-styled result renderer.

This is a lot more work than prompt text. It's also the difference between "a library of opinions" and "a library of building blocks."

### 3. Inspector-style selective editing
Both Lovable and Retool AppGen let users click any element in the preview and describe what they want changed about that specific element. "Make this button red." "Add a filter above this table." The AI acts on just that element rather than regenerating the whole thing.

Why this matters: early in a build, natural language is great for broad strokes. Later in a build, it's frustrating because every prompt rewrites more than you want. Element-level selection is the escape hatch from that frustration.

**For Forged:** if the "approved tool" is rendering in an iframe, let users click directly on rendered elements to ask Claude to refine them. "Make this column sortable." "Add a confidence score next to this number." This is the surface where brand-kit enforcement (from the v2 design doc) actually becomes useful — click an element, the system shows you what brand tokens apply, ask for the change within the enforced design system.

### 4. Remix / template as the 80% solution
Lovable's "remix" feature. Community templates. Retool's app templates. Every successful builder platform has this.

Why: most builders don't start from scratch. They start from something close and modify it. A blank prompt is paralysis; a template with "edit me" is invitation.

**For Forged:** every approved tool in the catalog should have a "remix" option that scaffolds a new project using the existing tool as the starting template — not a copy-paste, but a genuine fork that inherits the original's skills, brand kit, and governance posture, then lets the builder modify from there. Over time, the catalog isn't just a list of deployed tools — it's a library of starting points.

### 5. Governance visualization at generate-time, not just review-time
Retool AppGen detects "logic and security issues in real time" as the app is being generated, not only at submission. The governance warning appears in the chat as the builder is still working.

Why this is stronger than post-hoc validation: the builder learns the rules as they go, not just at the end. By the time they submit, they've already corrected course 10 times. Submission-time validation becomes a final check rather than a gauntlet.

**For Forged:** the governance validator agent shouldn't only run at `forge submit` time. A lighter version should run continuously as Claude Code generates output in the session. "Heads up — this query doesn't have the org filter the salesforce-queries skill requires. Want me to fix that?" Real-time governance coaching.

This is ambitious but it's the difference between "governance is a wall" and "governance is a teacher."

### 6. "Show me what you built" recap
Lovable does this well. After every significant change, the AI produces a one-sentence summary of what just happened. "I added a filter bar above the table, connected to the customer status field."

Not logging, not audit trail — conversational summarization of progress, kept in the chat history.

**For Forged:** when a builder runs `forge submit`, the validator should produce not just pass/fail but a structured recap: "You built a Salesforce account lookup tool. It uses the salesforce-queries skill (checked — all requirements met), the veracity-scoring skill (checked — confidence scores rendered on 6 fields), and the sensitive-data-handling skill (failed — customer email is not tokenized in logs). Here's what I'd change."

This is already sort of what the synthesizer agent does, but framing it as a narrative recap rather than a verdict is warmer and more useful for builders.

### 7. Visual design system defaults
Both Lovable and Retool AppGen ship with strong default design. You don't have to ask for "a good-looking dashboard" — you get one automatically. Typography, spacing, color, component primitives — all set to professional defaults without the user specifying anything.

This is the single most important thing for non-engineer adoption. A non-engineer who ships an ugly tool feels embarrassed and stops using the platform. A non-engineer who ships a beautiful tool feels proud and builds five more.

**For Forged:** this is exactly your v2 brand-kit enforcement, and it should probably move up the priority list. Without good default visuals, Forged-built tools will look worse than Lovable-built tools, and builders will prefer Lovable regardless of Forged's governance story. Governance doesn't matter if nobody wants to ship on your platform in the first place.

### 8. Customer-hosted deployment options
Retool just announced customer-hosted, Retool-managed deployments. You run Retool inside your own VPC, they manage it for you. This is big for enterprise.

**For Forged:** probably out of scope for prototype, but worth knowing it exists. The pattern to plan toward: Docker Compose setup that can run on a customer's VPS/cloud, Forged team manages updates and config. This is how you pitch governance to security teams that don't want SaaS.

### 9. Builder survey / social proof
Retool published a 2025 Builder Report — 1,100 internal builders surveyed, 91% say AI changed how they work, 66% under AI productivity mandates. They use this as a pitch deck asset and a recruiting asset for new customers.

**For Forged:** not relevant at prototype stage, but worth remembering. When you have 10+ active users, start surveying. The data becomes marketing.

---

## The Retool weakness Forged could exploit

Retool is winning on enterprise and on developer-first users. They're actively vulnerable on:

**Non-engineer accessibility.** Every review in the search mentions "Retool has a learning curve" and "non-technical users struggle." Their own CEO admitted they were engineer-first for a decade. AppGen is their attempt to fix this, but the platform underneath is still developer-shaped.

**Cost at the low end.** Retool enterprise pricing is steep. A 10-person RevOps team inside a mid-market company has a budget problem trying to justify it, even though the tool would be useful for them.

**Opinionation on governance specifically.** Retool provides governance infrastructure but doesn't have strong opinions on what governance should *look like* for GTM use cases. They give you RBAC and SSO; they don't give you veracity scoring or sensitive-data-handling as first-class primitives. Forged's specific governance skills are the opinionated wedge.

**AI-native from the start.** Retool retrofitted AI onto a 10-year-old low-code platform. Forged can be AI-native by design, which means the chat interface, the live preview, the semantic objects, and the governance validation can all be tightly integrated from day one rather than bolted on.

**Vertical focus.** Retool is horizontal. "Forged: the AI tool platform for revenue teams, with built-in GTM governance primitives" is a real wedge. Same category, narrower ICP, stronger opinions.

---

## What I'd take back to the Forged build

Priority order, based on what moves the needle most for demo-ability:

1. **Migrate to chat-left / preview-right as the primary build surface.** Biggest UX unlock. Required to compete with anything in this category.

2. **Brand-kit enforcement moves up from v2-nice-to-have to v1.5-critical.** Without good default visuals, Forged loses to Lovable on aesthetics regardless of governance story.

3. **Inspector-style selective editing** as the second-phase build surface. Click element, describe change, governance-aware modification happens.

4. **Real-time governance coaching** during generation, not just submission validation. Governance as teacher, not wall.

5. **Remix flow** on every approved catalog tool. Fork-as-a-starting-point.

6. **Semantic objects upgrade** for the skills library — evolve from prompt snippets to prompt + code + permissions + component bundles.

7. **Customer-hosted deployment path** — plan for it, don't build yet.

---

## The honest read on competing here

Retool has the resources, distribution, and head start to win horizontal enterprise. They'll keep shipping. Their recent announcements mean the category is closing fast.

Forged has three realistic paths:

**Path A — portfolio piece.** Keep building, use it as capability proof for your job search. Don't try to commercialize. Every good pattern you implement from this doc strengthens it as a portfolio asset. This is the lowest-risk path and still the most useful for your career right now.

**Path B — opinionated vertical wedge.** "Forged: the AI tool platform for revenue operations teams, with built-in GTM governance primitives." Narrow enough that Retool doesn't fight you for the specific customer, opinionated enough that builders feel the product was made for them. This is a real business but requires commitment.

**Path C — open source category influence.** Publish Forged's governance-skills pattern as open source. Let the industry fork your opinions. You don't win commercially but you win mindshare, which compounds into career and advisory capital over time. The Figma-for-AI-governance move. Also realistic, also useful.

You don't have to pick today. Paths A, B, and C are all reachable from continued building. But they diverge quickly once you start charging customers or raising money, so be aware of which one you're walking toward as the decisions pile up.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | ISSUES_OPEN | HOLD_SCOPE mode; premise challenged (Forge vs Retool category); Path D (Claude Code enterprise control plane) surfaced; 3 unresolved decisions; 1 critical gap (no explicit path commitment) |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | ISSUES_OPEN | 8 issues (1 P0, 2 P1, 2 P2, 2 P3), 4 critical gaps, 2 unresolved decisions. Biggest finding: 5 of 6 governance agents are defined but not invoked (pre-existing regression). Pattern #1 is an execution-model rewrite, not a UI pattern. Pattern #2 is a schema rewrite with a trust boundary. |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **UNRESOLVED:** 5 total (3 CEO + 2 eng)
- **VERDICT:** NOT CLEARED — eng review has open issues; fix the 6-agent-pipeline regression before any plan priority ships

