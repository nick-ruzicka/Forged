# T3_NEW — Runtime DLP Masking

## Rules
- Own ONLY: api/dlp.py, tests/test_dlp.py, modifications to api/executor.py (DLP integration only), api/admin.py (analytics stat only), frontend/js/admin.js (badge only), a new migration file in db/migrations/
- Do NOT touch other terminals' files
- Mark tasks [x] when done, update PROGRESS.md after each change
- Run `venv/bin/python3 -m py_compile` on every edited Python file
- Run `venv/bin/python3 -m pytest tests/test_dlp.py -v` after writing tests
- When all tasks done write `T3_NEW DONE` to PROGRESS.md

## Tasks
[x] Create `api/dlp.py` — DLPEngine class with: `detect_pii(text)` returns list of `{type, value, start, end}` matches for email, phone, SSN, credit card patterns. `mask_text(text)` replaces PII with tokens like `[EMAIL_1]`, `[PHONE_1]`. `unmask_text(masked_text, token_map)` restores original values. `get_token_map()` returns dict of token->original.
[x] Modify `api/executor.py` `run_tool()` — before calling Claude: run `DLPEngine.mask_text()` on all input values, store `token_map` in run record. After Claude responds: run `unmask_text()` to restore any tokens that appeared in output.
[x] Add `dlp_scan` column to runs table via new migration `db/migrations/002_dlp_runs.sql`: `ALTER TABLE runs ADD COLUMN IF NOT EXISTS dlp_tokens_found INTEGER DEFAULT 0`
[x] Update `api/executor.py` to store count of PII tokens found in `dlp_tokens_found` column
[x] Add DLP stats to GET `/api/admin/analytics` — include `total_pii_masked` count from runs table
[x] Create `tests/test_dlp.py` — test email masking, phone masking, SSN masking, unmask restores correctly, `run_tool` masks before Claude call (mock Claude, verify masked text sent)
[x] Update admin run monitor to show DLP badge if `dlp_tokens_found > 0` on a run

## Cycle 4 Tasks (DLP v2 — expanded patterns + audit trail)

CYCLE 17 DEMOLITION UNBLOCKED (2026-04-16): **TERMINAL FULLY INVALIDATED.** Files this terminal owns — `api/dlp.py` and `api/executor.py` (the DLP integration site) — were both deleted in commit `837ed88` ("demolish prompt stack (stage 2)"). Runtime DLP masking was a **prompt-tool runtime concern** that lived on the `run_tool()` execution path, which no longer exists (there are no prompt `runs` to mask PII in; `runs` table itself is dropped by migration `008_drop_prompt_stack.sql`). **Every Cycle 4 task below is obsolete** — the `dlp_audits` migration, expanded regex set, mask_level, per-tool policy, analytics rollup, admin detail endpoint all presuppose a runtime execution path that is gone. HUMAN-OPERATOR ACTION: park this file OR re-scope for **apps-era DLP** — e.g., an apps-submission-time secrets scanner for `app_html` (hook into `/api/submit/app` or the apps analyzer). T4_github_app Cycle 7 task 3 already sketches a pre-deploy DLP scan using the v1 `api/dlp.py` patterns; that may be the new home for the regex table. Do NOT pick up anything below until the repurposing decision is made.

LEGACY UNBLOCKED (pre-demolition, obsolete): All 10 tasks stay inside T3_NEW ownership (api/dlp.py, api/executor.py DLP-only, api/admin.py analytics-only, frontend/js/admin.js badge-only, tests/test_dlp.py, new migration file). No cross-terminal dependency: SPEC lines 626-652 describe the Runtime DLP Layer; Phase 2 masking is already live from Cycle 1 so these tasks extend pattern coverage, audit persistence, and per-tool policy knobs. Suggested pick order: migration 004 FIRST (unblocks audit-log writes) → expanded regex set → detect_category → executor audit insert → analytics categories rollup → per-tool policy → admin DLP detail endpoint → admin UI details panel → test coverage → mask_level parameter.

[ ] api/dlp.py - extend detect_pii regex set: IPv4 address, US passport (9 digits preceded by "passport"), AWS access key (AKIA[0-9A-Z]{16}), GitHub token (ghp_|gho_|ghu_|ghs_ + 36 chars), OpenAI API key (sk-[A-Za-z0-9]{32,}), generic JWT (3 base64url segments). Each new pattern gets a type label used in mask tokens ([IPV4_1], [AWS_KEY_1], etc.).
[ ] api/dlp.py - add mask_level parameter to DLPEngine.__init__(level="standard"): "strict" also masks capitalized name sequences (First Last regex); "standard" keeps Cycle 1 behavior; "permissive" only masks emails/SSN/credit-card. Default remains "standard".
[ ] api/dlp.py - detect_category(text) returns list[{type, count}] (no values) for analytics rollup; uses same regex table as detect_pii but returns counts grouped by type instead of match positions.
[ ] db/migrations/004_dlp_audit.sql - CREATE TABLE dlp_audits (id SERIAL PRIMARY KEY, run_id INTEGER REFERENCES runs(id) ON DELETE CASCADE, pii_type TEXT NOT NULL, field_name TEXT, token TEXT NOT NULL, created_at TIMESTAMP DEFAULT NOW()); CREATE INDEX idx_dlp_audits_run_id ON dlp_audits(run_id); CREATE INDEX idx_dlp_audits_type ON dlp_audits(pii_type). Also ALTER TABLE tools ADD COLUMN IF NOT EXISTS dlp_policy TEXT DEFAULT NULL for per-tool mask_level override.
[ ] api/executor.py - after DLPEngine.mask_text during run_tool(), INSERT one row per token into dlp_audits with run_id, pii_type, source field_name, token string (NEVER the original value). Wrap in same transaction as run INSERT so audit + run commit atomically.
[ ] api/admin.py - extend GET /api/admin/analytics payload with dlp_categories: SELECT pii_type, COUNT(*) FROM dlp_audits WHERE created_at > NOW() - INTERVAL '30 days' GROUP BY pii_type ORDER BY count DESC. Return [{type, count}].
[ ] api/admin.py - new GET /api/admin/runs/:id/dlp endpoint (admin-auth required via existing check_admin_key decorator): SELECT pii_type, field_name, token FROM dlp_audits WHERE run_id=:id ORDER BY id. Return [{pii_type, field_name, token}] — NEVER the original value.
[ ] frontend/js/admin.js - in the run-detail modal, add a "DLP Details" section: when run.dlp_tokens_found > 0, fetch /api/admin/runs/:id/dlp, render grouped by pii_type with counts and token list; existing badge in row stays untouched.
[ ] api/executor.py - read tools.dlp_policy (JSON string parsed to {level:"strict|standard|permissive"}) and pass level to DLPEngine constructor before masking; NULL policy falls back to standard. Log policy level used in dlp.log entry.
[ ] tests/test_dlp.py - coverage expansion: (a) each new regex (IPv4, AWS key, GitHub token, OpenAI key, JWT) masks correctly and unmask round-trips; (b) mask_level=permissive skips IP/AWS-key but still masks emails; (c) dlp_audits rows created with correct run_id and field_name after run_tool; (d) GET /api/admin/analytics dlp_categories returns sorted counts; (e) GET /api/admin/runs/:id/dlp returns tokens without raw values and returns [] for runs with dlp_tokens_found=0.
