# Governed Skills — Calibration Results (2026-04-19)

**Scope:** 10 skills from the catalog, covering all categories (Development, Testing, Debugging, Planning, Code Review, Documents). No author-supplied test cases — QA generated all test prompts from skill descriptions.

**Reviewers:** Engineering (calibration run by Claude Code agent pipeline).

---

## Per-Agent Timing Distribution (n=11-15 runs)

| Agent | p25 | p50 | p75 | p90 | p95 | min | max |
|---|---|---|---|---|---|---|---|
| Classifier | 666ms | 900ms | 1,146ms | 1,276ms | 1,311ms | 655ms | 1,346ms |
| Security Scanner | 1,789ms | 2,116ms | 2,568ms | 2,928ms | 3,164ms | 1,670ms | 3,357ms |
| Red Team | 3,609ms | 3,752ms | 4,008ms | 4,205ms | 4,977ms | 3,034ms | 6,570ms |
| Prompt Hardener | 16,845ms | 26,247ms | 32,318ms | 60,195ms | 65,164ms | 10,389ms | 65,551ms |
| QA Tester | 19,414ms | 23,508ms | 26,663ms | 29,265ms | 29,961ms | 18,185ms | 31,153ms |
| Synthesizer | 6,344ms | 7,198ms | 8,990ms | 12,037ms | 13,200ms | 3,376ms | 14,904ms |

**Pipeline total:** p50 ~60s, p95 ~103s (~1.7 minutes)

**SLA status:** p50 well under 2min target. p95 well under 5min target. Comfortable margin.

**Bottleneck:** Prompt Hardener (p95=65s), not QA Tester as predicted. The hardener rewrites entire SKILL.md files, which takes longer for larger skills (9-10k chars). The hard timeout of 90s is appropriate — no runs exceeded it.

---

## Safety Metrics

| Metric | Observed | Threshold |
|---|---|---|
| Red team attack success rate | 0/50 attacks (0%) | Must be 0% |
| injection_risk flagged | 0/10 skills | Must be false |
| data_exfil_risk flagged | 0/10 skills | Must be false |
| data_class_mismatch | 0/10 skills | Must be false |

**All safety thresholds pass.** No skills in the existing catalog contain injection, exfiltration, or credential harvesting patterns. The safety pipeline is correctly permissive for clean skills.

---

## Quality Metrics

| Metric | p25 | p50 | p75 | min | max |
|---|---|---|---|---|---|
| Invocation precision | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| Output consistency | 0.0 | 0.1 | 0.55 | 0.0 | 0.95 |
| QA pass rate | 0.5 | 0.525 | 0.775 | 0.5 | 0.95 |

**Invocation precision:** Perfect (1.0) across all skills. The generated test prompts correctly distinguish which prompts should trigger each skill. This metric is working well.

**Output consistency:** Highly variable (0.0 to 0.95). Skills that produce procedural guidance (debugging, TDD, code review) naturally produce different output each time — different step orders, phrasings, examples. Only skills with concrete, deterministic outputs (git worktrees — specific commands) score high.

**Decision:** Output consistency is **advisory-only for v1**. The p75 is 0.55, below the 0.60 floor defined in the spec. Per the escalation path: "if a metric's p75 is below a floor the team considers meaningless, that metric goes to advisory-only for v1 with a note to revisit after 30 days of real submissions."

---

## Calibrated Thresholds

### Safety (strict — block on fail)

No change from spec. These are absolute:
- Red team attack success rate = 0
- injection_risk = false
- data_exfil_risk = false
- data_class_mismatch = false

### Quality (advisory — warn, do NOT block)

| Metric | Threshold | Rationale |
|---|---|---|
| Invocation precision | advisory warn if < 0.90 | p75 = 1.0, so 0.90 catches only genuinely poor skills |
| Output consistency | advisory-only for v1 | p75 = 0.55, below 0.60 floor. Revisit after 30 days. |

Quality warnings are included in the review response as `advisory_warnings` but do NOT change `agent_recommendation` from `approve` to `needs_revision`.

---

## Issues Found During Calibration

1. **Claude wraps JSON in markdown code fences.** All 6 agents failed on first run because `json.loads` can't parse ` ```json ... ``` `. Fixed by adding `parse_json_response()` to `agents/base.py`. Commit: `aab9163`.

2. **Synthesizer treated quality as blocking.** The prompt said "advisory" but the model interpreted low consistency as grounds for `needs_revision`. Fixed by making the decision logic explicit in the prompt: safety pass → approve, regardless of quality scores. Commit: `1035ee9`.

3. **`agent_reviews` table missing from running DB.** Migration 001's `CREATE TABLE IF NOT EXISTS` had silently failed (the table was referenced before creation in migration order). Fixed by creating the table directly. Root cause: migration ordering issue — should be tracked for production deployment.

---

## Recommendations

1. **Ship with these thresholds.** Safety pipeline is solid. Quality is advisory-only, which is correct for v1.

2. **Revisit output consistency after 30 days.** Once skills have author-supplied test cases (which provide stable, deterministic test prompts), consistency scores should improve. Re-calibrate then.

3. **Monitor prompt hardener timing.** It's the bottleneck (p95=65s). For skills >10k chars, consider truncating the skill text sent to the hardener to the first 5k chars + any sections flagged by the scanner/red team.

4. **Migration ordering.** Ensure `agent_reviews` is created before migration 018 runs. Add a pre-flight check to `init_db()` or reorder migrations.
