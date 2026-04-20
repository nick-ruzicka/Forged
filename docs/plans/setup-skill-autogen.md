# Plan: Auto-Generated Setup Skills

## Vision

When a publisher adds an external app to Forge (via GitHub URL), Forge automatically generates a setup skill by reading the repo's README, config templates, and documentation. The generated skill walks new users through configuration conversationally. Publishers can review and improve it. Community can fork and improve it.

## Why This Matters

The gap between "installed" and "actually useful" kills adoption of every internal tool. Setup skills close that gap. But nobody will write setup skills manually for every app. Auto-generation solves the cold-start problem.

## Architecture

```
Publisher submits GitHub URL
  → Backend fetches: README.md, CLAUDE.md, *.example.*, .env.example
  → Backend sends to Claude: "Generate a setup skill for this app"
  → Generated skill stored in skills table, linked to tool via setup_skill_id
  → Publisher can edit the skill before publishing (or publish as-is)
  → Users see "AI-assisted setup available" on the app detail page
```

## Implementation Steps

### Step 1: Backend — GitHub repo analyzer (30 min CC time)

**File:** `api/server.py` — new endpoint `POST /api/admin/generate-setup-skill`

**Input:** `{ tool_id, github_url }`

**Logic:**
1. Fetch from GitHub API:
   - `README.md` (required)
   - `CLAUDE.md` or `AGENTS.md` (optional)
   - All files matching `*.example.*`, `*.sample.*`, `.env.example`
   - `package.json` or `go.mod` or `requirements.txt` (for dependency context)
   - Directory listing of `config/` if it exists
2. Truncate total content to ~30k chars (fit in Claude context)
3. Call Claude API with the meta-prompt (Step 2)
4. Parse the response as a SKILL.md
5. Insert into `skills` table, set `setup_skill_id` on the tool

**Dependencies:** Anthropic API key (already in .env)

### Step 2: The meta-prompt (15 min)

**File:** `api/prompts/generate_setup_skill.py` (or inline in server.py)

The prompt that generates setup skills. This is the product — get this right and every generated skill is useful.

```
You are generating a setup skill for a software tool.

A setup skill is a SKILL.md file that teaches Claude Code how to configure
this app for a new user. It asks questions one at a time and writes config
files based on the answers.

Here is the app's documentation:
<readme>{readme_content}</readme>
<config_files>{config_templates}</config_files>
<claude_md>{claude_md_content}</claude_md>

Generate a SKILL.md with:
1. YAML frontmatter (name, description)
2. A step-by-step setup flow that:
   - Identifies EVERY config file that needs to be created or edited
   - Asks the user for EACH required value (don't assume defaults)
   - Writes the config file after getting answers
   - Verifies each step works (run health checks, test commands)
3. A final verification step

Rules:
- Ask ONE question at a time
- Be specific about file paths
- If the README has a "Quick Start" section, follow that order
- If there's a doctor/health-check script, run it at the end
- Total setup should take 3-5 minutes
- Don't include the app's full documentation — just the setup flow
```

### Step 3: Frontend — "Generate Setup Skill" button (20 min)

**Where:** App detail page, in the metadata sidebar, only visible to the publisher (or admin)

**UI:** Button that says "Generate Setup Skill" → loading state → shows preview of generated skill → "Publish" or "Edit" buttons

**Flow:**
1. Click "Generate Setup Skill"
2. POST `/api/admin/generate-setup-skill` with tool_id and source_url
3. Show loading state ("Analyzing repo... Generating setup skill...")
4. When done, navigate to the skill detail page to review
5. Skill is auto-linked to the tool

### Step 4: Publish flow integration (15 min)

**Where:** `/publish` page, "From GitHub" mode

**Change:** After the app is created from a GitHub URL, auto-trigger setup skill generation in the background. Show a toast: "Setup skill generated — review it on the app detail page."

This makes the flow: Paste GitHub URL → Fill metadata → Publish → Setup skill auto-generated → Done.

### Step 5: Seed script update (5 min)

Update `scripts/seed_demo_apps.py` to call the generation endpoint for apps that have `source_url` but no `setup_skill_id`. This backfills setup skills for existing apps.

## What NOT to Build

- No in-browser chat UI for running the setup. Users run it in Claude Code.
- No auto-detection of "this app needs setup." The setup skill existing IS the signal.
- No versioning of generated skills. The publisher can edit and the community can fork — that's enough.
- No quality scoring of generated skills. Upvotes handle this.

## Demo Story

"Watch me add Fabric to Forge. I paste the GitHub URL, Forge reads the README, and automatically generates a setup skill. Now when someone installs Fabric, they don't need to read docs — the setup agent walks them through configuring API keys, choosing a model, and running their first pattern. In 3 minutes they're productive."

## Effort Estimate

| Step | CC Time | Human Time |
|------|---------|------------|
| Backend endpoint | 30 min | 5 min review |
| Meta-prompt | 15 min | 10 min tuning |
| Frontend button | 20 min | 5 min review |
| Publish integration | 15 min | 5 min review |
| Seed script | 5 min | 2 min review |
| **Total** | **~1.5 hours** | **~30 min review** |

## Success Criteria

1. Paste a GitHub URL → setup skill appears in < 30 seconds
2. Generated skill correctly identifies all config files that need editing
3. Generated skill asks for every required value (no assumed defaults)
4. Generated skill includes a verification step
5. The generated skill for Fabric is at least as good as the hand-written one
