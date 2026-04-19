# Forge — Vision & Scope

## What Forge is

Forge is the internal AI app marketplace that lets any company —
not just Ramp — give every employee their own AI-powered workspace.
Apps, skills, and tools built by teammates, installed in one click,
governed by default.

## The three classes of apps

Forge handles three genuinely different app types. The UX should
reflect this, not pretend they're the same.

### Class A — Forge-hosted web apps (the core)
HTML + JS stored in Forge's database, served from /apps/:slug,
rendered inside Forge's iframe. Zero install friction, zero install
cost, runs anywhere Forge runs. Examples: Hebbia Signal Engine,
Chariot dashboard, Kanban boards, research tools, meeting prep.

This is the reason Forge exists. Employees build these in Claude
Code, `forge deploy`, teammates install and use them the same day.

### Class B — Backend-aware apps (the unlock)
Frontend is a Class A app served from Forge. Backend runs locally
in Docker, started by forge-agent. The backend overlay handles
"start your local backend" in 2 clicks. Example: Chariot Signal
Engine with Python Flask backend.

This is what Ramp Glass can't do. Glass is skills-only. Forge
bridges hosted frontends and local backends in one coherent UX.

### Class C — Native desktop apps (the bonus)
macOS apps with their own windows. Forge installs, launches, tracks
usage, checks for updates, uninstalls. Does NOT embed — can't,
they're native windows. Examples: Raycast, Pluely, Meetily.

Forge is not trying to be the launcher that replaces macOS. It's
the control panel for the apps you already use, with team signals
and usage tracking layered on top.

## The moat

Class A + Class B. That's the thing competitors can't replicate
without rebuilding Forge. Class C is a nice-to-have that proves
Forge plays well with the existing ecosystem.

When deciding what to build next: if it strengthens Class A or B,
prioritize. If it's Class C polish, defer unless it blocks a demo.

## What makes Forge defensible

Three things compound over time:

1. **Proprietary tool library per company**. Alice builds, Bob
   forks, Carol adopts. Six months in, the catalog is institutional
   knowledge nobody can buy.

2. **Usage data as behavioral signal**. Every tool run is logged.
   "Reps who run ICP Qualification before calls create 3x more
   deals." That's the weekly digest to sales leaders. Nobody else
   has this data.

3. **Governance as enterprise unlock**. Every app auto-scanned for
   CVEs, prompt injection, exfiltration patterns. IT approves Forge
   as infrastructure because it's governed by default. Glass at
   Ramp doesn't need this — they trust their own employees. Forge
   selling anywhere else does need it.

## What Forge is NOT

- Not a replacement for Spotlight, Dock, or macOS launchers
- Not a general-purpose IDE for building apps (use Claude Code)
- Not an npm/GitHub marketplace for all code (that's too broad)
- Not an AI agent that does work (Forge hosts apps that do work)
- Not a monitoring or observability product (though it logs usage)
- Not Ramp Glass — Forge is portable, Glass is Ramp-only

## Product principles

1. **Real apps only, no demos or filler**. The catalog is a
   curated library of real software with real authors. Every fake
   or placeholder app dilutes the signal.

2. **Governance invisible when working, visible when not**. Users
   never see the 6-agent review pipeline for approved apps. They
   see "trusted" badges and clean installs. When something's flagged
   or blocked, the reason is crystal clear.

3. **Security as architecture, not ceremony**. Sandbox isolation,
   CVE scanning, origin pinning, audit logs — all built in. Not
   features to sell, boundaries that can't be crossed.

4. **Social signals drive discovery, not taxonomies**. Categories
   exist but the primary organizing principle is "what your team
   uses." Role-aware recommendations, install counts, fork chains,
   co-install patterns.

5. **Publish must be as good as install**. 60 seconds from "I have
   this app" to "my team can use it." If publish is slow, the
   catalog dies because no one contributes.

## The 12-month bet

By April 2027, Forge is the default way every 50-500 person
company's internal AI tools are shared, installed, and governed.
One AE builds a pipeline reviewer. Their whole team uses it by
Friday. Their IT admin sleeps well at night because every tool
went through the review pipeline. The CEO sees a weekly digest
with real behavioral signals. That's the product.
