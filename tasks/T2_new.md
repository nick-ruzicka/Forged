# T2_NEW — Conversational Tool Creator

## Rules
- Own ONLY: api/creator.py, frontend/creator.html, frontend/js/creator.js, modifications to api/server.py (blueprint registration only) and frontend/index.html (one button only)
- Do NOT touch agents/, executor logic, db.py, or any other terminal's files
- Mark tasks [x] when done, update PROGRESS.md after each change
- Run `venv/bin/python3 -m py_compile api/creator.py` after edits
- When all tasks done write `T2_NEW DONE` to PROGRESS.md

## Tasks
[x] Create `api/creator.py` — Flask Blueprint at `/api/creator`. POST `/api/creator/generate` accepts `{description: "plain English description of what the tool should do", author_name, author_email}`
[x] In `api/creator.py` — build `generate_tool_from_description(description)` function that calls Claude Sonnet with a system prompt instructing it to return a complete tool submission JSON: `{name, tagline, description, category, output_type, system_prompt with {{variables}}, input_schema array, output_format, reliability_note, security_tier}`
[x] Validate the generated JSON has all required fields. If missing any, make a second Claude call to fix it.
[x] Auto-submit the generated tool by calling the existing submit logic. Return `{tool_id, slug, generated_tool}` so the frontend can redirect to the tool page.
[x] Add GET `/api/creator/preview` — same as generate but does NOT submit, just returns the generated tool JSON for user review before submitting
[x] Create `frontend/creator.html` — single input page: large textarea "Describe what you want this tool to do...", example suggestions below it, Generate button, loading state showing "AI is designing your tool...", output showing the generated tool preview with Edit/Submit buttons
[x] Create `frontend/js/creator.js` — calls `/api/creator/preview`, renders result in a readable card, allows editing key fields (name, tagline, prompt), Submit button calls `/api/creator/generate`
[x] Add "Create with AI" button to catalog page (`index.html`) that links to `creator.html`
[x] Register creator blueprint in `server.py`
[x] Test: describe "a tool that takes a company name and drafts a cold outreach email" — verify it generates a valid tool with correct input schema

## Verification Notes (2026-04-16)
- `venv/bin/python3 -m py_compile api/creator.py api/server.py` — OK
- Routes registered: `POST/GET /api/creator/preview`, `POST /api/creator/generate`
- Live test via `/api/creator/preview` with the required example returned a valid tool: `Cold Outreach Email Drafter`, category `Email Generation`, output_type `probabilistic`, output_format `email_draft`, 5 input fields with correct schema (`company_name`, `sender_company`, `value_proposition`, `call_to_action`, `tone` — select with options).
- Model: `claude-sonnet-4-6` via anthropic SDK 0.40.0.
- Submit reuse: `/api/creator/generate` dispatches to existing `/api/tools/submit` via Flask test_client so submit validation + pipeline launch stays in one place.

## Cycle 5 Tasks (Creator v2 — meta-agent pipeline per SPEC 1506-1516)

UNBLOCKED: All 10 tasks stay inside T2_NEW ownership (api/creator.py, frontend/creator.html, frontend/js/creator.js, new tests/test_creator.py). Zero cross-terminal dependency — generation path already proven live in Cycle 1. SPEC lines 1506-1516 describe the full meta-agent pipeline (intent parser → prompt generator → schema builder → governance estimator → test case generator). Suggested pick order: tests/test_creator.py FIRST (locks generation contract) → governance auto-fill → test case generator → variant batch → refinement loop → history → inline editor → best practices layer → description presets → category detection confidence.

[ ] T2_new - tests/test_creator.py - pytest coverage: mock Claude Sonnet responses for happy path + missing-field repair path + invalid-JSON repair path; assert /api/creator/preview returns valid schema for "company name → cold outreach email" fixture; assert /api/creator/generate returns {tool_id, slug} and writes tools row with status='pending_review'.
[ ] T2_new - api/creator.py - add governance auto-estimator step: after JSON generation, second Claude Haiku call classifies the proposed tool on reliability (0-100), safety (0-100), data_sensitivity, complexity; merge into returned JSON as `suggested_governance` so Step 4 of submit form is pre-filled.
[ ] T2_new - api/creator.py - add test_case generator step: POST /api/creator/generate-test-cases {generated_tool} returns 3 synthetic test cases (normal/edge/minimal) per SPEC line 511-515, formatted to match QA agent's test_cases contract so they can pre-seed QA tester inputs.
[ ] T2_new - api/creator.py - POST /api/creator/variants accepts {description, count=3}: runs generate_tool_from_description N times in parallel (asyncio.gather or ThreadPoolExecutor) with temperature=0.7 variance; returns [{generated_tool, reasoning}] for user to pick best.
[ ] T2_new - api/creator.py - POST /api/creator/refine accepts {generated_tool, user_tweak: "make the tone more formal"}: Claude Sonnet call with current tool JSON + tweak instruction returns revised JSON; validation + fixer reuse from Cycle 1.
[ ] T2_new - frontend/js/creator.js - localStorage-backed generation history (last 10 descriptions + generated tools), dropdown below textarea "Recent generations ▾"; click to reload a prior generation without re-calling Claude.
[ ] T2_new - frontend/creator.html + frontend/js/creator.js - inline prompt editor: replace read-only prompt preview with editable textarea that highlights {{variables}} (reuse submit.js patterns if available, else implement minimal regex-based span wrapping); live-validates variables against input_schema.
[ ] T2_new - api/creator.py - best-practices layer: after initial JSON generation, apply a Claude Sonnet "hardening lite" pass that adds common guardrails ("If uncertain, say unknown", output-format enforcement) per SPEC lines 484-491; stored in `generated_tool.system_prompt` (hardener still runs on submit).
[ ] T2_new - frontend/creator.html - replace 4 static example chips with 12 description presets grouped by category (Account Research, Email Generation, Data Lookup, Reporting, Onboarding, Forecasting); clicking preset fills textarea + auto-triggers preview.
[ ] T2_new - api/creator.py - category-detection confidence: when Claude's output_type/category fields are returned, also return confidence (0-1); if <0.7 frontend shows a "Category unclear — please pick one" dropdown override before submit.
