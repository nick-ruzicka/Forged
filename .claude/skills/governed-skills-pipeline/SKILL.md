---
name: governed-skills-pipeline
description: Implement the governed skills review pipeline — schema migrations, 6-agent pipeline adaptation for SKILL.md submissions, QA harness, UX, and backfill. Use when working on any part of the skill governance system.
user-invocable: true
---

# Governed Skills Review Pipeline

You are implementing Forge's governed skills system. The full spec is at `docs/superpowers/specs/SPEC-governed-skills-v2.md` — read it before doing anything. v1 is superseded but preserved at `SPEC-governed-skills-v1.md` for decision history.

## What exists today

- `agent_reviews` table in `db/migrations/001_initial_schema.sql` (lines 109-155) — built for apps, needs extension for skills
- `skills` table in `db/migrations/001_initial_schema.sql` (lines 159-171) — basic columns only, no review state
- `api/inspector.py` — static HTML analysis for apps (not the 6-agent pipeline)
- `api/db.py` — has `create_review` (unified for tools+skills), `update_agent_review`, skill CRUD functions, `insert_skill_test_cases`, `insert_skill_admin_action`
- `api/models.py` — `Skill` dataclass includes governance fields (review_status, version, parent_skill_id, etc.)
- `forge_sandbox/tasks.py` — Celery task infrastructure (`hibernate_idle` + `skill_review_pipeline` behind `SKILL_REVIEW_MODE` flag)
- Frontend skills page at `web/app/skills/page.tsx`
- 18 migrations exist (`001` through `018`); next migration is `019`

## Config flags

- `SKILL_REVIEW_MODE`: `'stub'` (default) auto-approves all skills. `'real'` runs actual 6-agent pipeline (Phase 2+).

## The 6-agent pipeline

```
classifier → security_scanner → red_team → prompt_hardener → qa_tester → synthesizer
```

For apps, these already exist conceptually in `agent_reviews` columns. For skills, 5 of 6 apply as-is with minor prompt tweaks. The one new piece is the **QA harness** for skills.

### Agent-by-agent adaptation

| Agent | Change for skills |
|---|---|
| Classifier | Input is SKILL.md text, not tool manifest. Minor prompt tweak. |
| Security Scanner | Add skill-specific patterns: credential-path reads (`~/.ssh`, `~/.env`), unknown URL posts, destructive shell verbs (`rm -rf`, `--no-verify`), hook-skipping flags. |
| Red Team | New playbook: adversarial *conversations* that weaponize the skill. If `parent_skill_id` is set, diff against parent and flag added injection/exfiltration lines. |
| Prompt Hardener | Works as-is — the skill literally is a prompt. |
| QA Tester | **New harness.** See QA section below. |
| Synthesizer | Add cross-check: declared `data_sensitivity` vs red-team-observed behavior. Emit `data_class_mismatch` flag. |

## Phases (implement in order)

### Phase 1 — Schema + pipeline reuse (1-2 days)

Create migration `018_governed_skills.sql`:

```sql
-- Extend skills with review state
ALTER TABLE skills
  ADD COLUMN review_status     TEXT NOT NULL DEFAULT 'pending',
  ADD COLUMN review_id         INTEGER REFERENCES agent_reviews(id),
  ADD COLUMN version           INTEGER NOT NULL DEFAULT 1,
  ADD COLUMN parent_skill_id   INTEGER REFERENCES skills(id),
  ADD COLUMN data_sensitivity  TEXT,
  ADD COLUMN submitted_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  ADD COLUMN approved_at       TIMESTAMP,
  ADD COLUMN blocked_reason    TEXT,
  ADD COLUMN blocked_at        TIMESTAMP;

-- Make agent_reviews work for both tools and skills
ALTER TABLE agent_reviews
  ALTER COLUMN tool_id DROP NOT NULL,
  ADD COLUMN skill_id INTEGER REFERENCES skills(id),
  ADD CONSTRAINT agent_reviews_target_check
    CHECK ((tool_id IS NULL) <> (skill_id IS NULL));

-- Admin audit log
CREATE TABLE skill_admin_actions (
    id              SERIAL PRIMARY KEY,
    skill_id        INTEGER NOT NULL REFERENCES skills(id),
    action          TEXT NOT NULL,
    reason          TEXT NOT NULL,
    reviewer        TEXT NOT NULL,
    from_status     TEXT,
    to_status       TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Also create the `skill_test_cases` table (author-supplied positive/negative examples):

```sql
CREATE TABLE IF NOT EXISTS skill_test_cases (
    id          SERIAL PRIMARY KEY,
    skill_id    INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL CHECK (kind IN ('positive', 'negative')),
    prompt      TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Then:
- Add `skill_review_pipeline` Celery task in `forge_sandbox/tasks.py` (behind `SKILL_REVIEW_MODE` config flag)
- Use unified `create_review(target_id, target_type)` in `api/db.py` — don't duplicate per target type
- Wire `POST /api/skills` to enqueue the pipeline task on submission
- Pipeline dispatcher: accept `skill_id`, pass SKILL.md text to each agent

### Phase 2 — QA harness (2-3 days)

**Safety thresholds (strict — block on fail):**
- Red team attack success rate = 0
- `injection_risk` = false
- `data_exfil_risk` = false
- `data_class_mismatch` = false

**Quality thresholds (advisory — warn, don't block):**
- Invocation precision on author positives: warn if < calibrated baseline
- False-fire rate on author negatives: warn if > calibrated baseline
- Output consistency (judge-model rubric >= 4/5): warn if < calibrated %

**Author test set (required at submission):**
- 10 prompts that should trigger the skill
- 10 prompts that should not trigger the skill
- Harness generates 10 additional adversarial variants
- If author can't supply 10/10, harness generates all 20 but flags `author_no_examples`

**Output consistency rubric (5 = semantically equivalent, 1 = contradictory):**
Target: judge scores >= 4 on >= X% of pairs (X set during Phase 2.5 calibration).

### Phase 2.5 — Calibration (1 day)

Run top 20 most-installed skills through pipeline. Document results in `docs/superpowers/specs/governed-skills-calibration-YYYY-MM-DD.md`:
- Per-metric distribution (min/p25/p50/p75/p90/max)
- Quality thresholds set at 75th percentile
- If metric p75 < 0.60, make advisory-only for v1
- If > 50% fail a quality metric, advisory-only for v1
- Safety thresholds are absolute — never calibrate down

Requires sign-off from engineering lead + product lead.

### Phase 3 — UX (1-2 days)

Files to modify in `web/`:
- Skills catalog (`web/app/skills/page.tsx`): default filter to `approved`, admin toggle for pending/blocked
- Skill detail page: status badge, structured feedback rendering, fork badge + diff view
- Submit dialog: toast on submit, "View status" button
- Author's "My Skills" tab: show all statuses with `blocked_reason`
- Admin override UI: Approve/Block split button, reason capture (>= 20 chars), logged to `skill_admin_actions`

### Phase 4 — Backfill (1 day)

Run all existing skills through pipeline. Reviewer of record: `system:backfill:2026-04-19`. Passing = `approved`, failing = `needs_revision` with structured feedback.

### Phase 5 — Enforce (flip a flag)

Default catalog filter to `approved` only. New submissions blocked until reviewed.

## Key decisions already made

Read these before asking questions — they're settled:

- **Fail-closed on pipeline error.** Skill stays `pending`. Alert on stuck-pending > 1 hour.
- **Legacy reviewer:** `system:backfill:2026-04-19`
- **Attack narratives:** admin-only. Public UI shows aggregate counts.
- **`featured` and `approved` are orthogonal.** Must be approved to be featured.
- **Version pinning:** auto-update with toast + revert option for 30 days.
- **Retroactive blocks:** update the specific version row's `review_status`, `blocked_reason`, `blocked_at`. Other versions unaffected.
- **Repeat-block policy:** after 3 consecutive blocks (same category, same skill or author), human-in-the-loop gate.
- **Scanner patterns:** git-versioned prompt file for v1. TODO for runtime config in multi-tenant.

## Author feedback format

When `review_status = 'needs_revision'`, return 3-5 structured issues:

```json
{
  "issues": [
    {
      "line_ref": "SKILL.md:L12-14",
      "category": "prompt_injection_risk|credential_access|exfiltration_pattern|invocation_precision|output_consistency|data_class_mismatch",
      "summary": "...",
      "suggested_fix": "..."
    }
  ],
  "advisory_warnings": [
    { "metric": "invocation_precision", "observed": 0.82, "baseline": 0.88 }
  ]
}
```

Synthesizer must produce line refs and actionable fixes. Vibes-only feedback is rejected and re-prompted once.

## Observability (wire up in admin dashboard)

| Metric | SLO |
|---|---|
| `reviews_by_outcome_daily` | No SLO — baseline |
| `red_team_attack_success_rate_weekly` | Must remain 0 |
| `qa_false_positive_rate` | < 10% |
| `pipeline_duration_p50_p95` | p50 < 90s, p95 < 300s |
| `pipeline_error_rate` | < 1% |
| `override_frequency` | Baseline; spike = recalibrate |

## Non-goals (don't build these)

- Runtime skill execution sandboxing
- Per-org governance tiers
- Skill composition / bundling / attribution
- Automatic re-review on new CVEs (manual `manual_rereview` action only)
