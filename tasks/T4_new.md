# T4_NEW — Tool Composability v1

## Rules
- Own ONLY: api/workflow.py, frontend/workflow.html, frontend/js/workflow.js, tests/test_workflow.py, a new migration file in db/migrations/, modifications to api/server.py (blueprint registration only) and frontend/index.html (one link only)
- Do NOT touch other terminals' files
- Mark tasks [x] when done, update PROGRESS.md after each change
- Run `venv/bin/python3 -m py_compile api/workflow.py` after edits
- Run `venv/bin/python3 -m pytest tests/test_workflow.py -v` after writing tests
- When all tasks done write `T4_NEW DONE` to PROGRESS.md

## Tasks
[x] Add `workflow_steps` column to tools table via new migration `db/migrations/003_workflow_steps.sql`: `ALTER TABLE tools ADD COLUMN IF NOT EXISTS workflow_steps TEXT` — JSON array of `{step_order, tool_id, input_mappings: {target_field: "{{step1.output}}"}}`
[x] Create `api/workflow.py` — Flask Blueprint at `/api/workflows`. POST `/api/workflows/run` accepts `{workflow_steps:[{tool_id, inputs}], user_name, user_email}`. Runs each step in sequence, substituting `{{stepN.output}}` in subsequent steps' inputs. Returns array of run results.
[x] Create `frontend/workflow.html` — simple two-tool chain builder: select Tool 1, select Tool 2, map output field to input field with dropdown, Run Chain button, shows results of both steps
[x] Create `frontend/js/workflow.js` — loads approved tools for selectors, builds input mapping UI, calls `/api/workflows/run`, shows step results sequentially
[x] Add "Chain Tools" link to catalog page (`index.html`)
[x] Create `tests/test_workflow.py` — test two-tool chain executes in sequence, output of step 1 correctly substituted into step 2 inputs
[x] Register workflow blueprint in `server.py`

## Cycle 5 Tasks (Workflow v2 — visual builder + branching per SPEC 1489-1496)

CYCLE 17 DEMOLITION UNBLOCKED (2026-04-16): **TERMINAL FULLY INVALIDATED.** Files this terminal owns — `api/workflow.py`, `frontend/workflow.html`, `frontend/js/workflow.js`, `tests/test_workflow.py` — were all deleted in commit `837ed88`. Migration `008_drop_prompt_stack.sql` additionally drops `tools.workflow_steps` (the column this terminal added in migration 003) and the `runs` table (what chained tool executions wrote to). **Every Cycle 5 task below is obsolete** — workflows-as-tools, typed-edge validation, conditional branching, shared context — all presupposed a prompt-tool runtime that is gone. HUMAN-OPERATOR ACTION: park this file. If an apps-era composability story is needed (e.g., an app invoking another app's data via `ForgeAPI.runTool` — which is also a prompt-era helper and may be vestigial), that would be a net-new T4_app_composability.md with a different contract. Do NOT pick up anything below.

LEGACY UNBLOCKED (pre-demolition, obsolete): All 10 tasks stay inside T4_NEW ownership (api/workflow.py, frontend/workflow.html, frontend/js/workflow.js, tests/test_workflow.py, new db/migrations/005_workflows.sql). Zero cross-terminal dependency — Cycle 1 chain runner + {{stepN.output}} substitution already live and tested. SPEC lines 1489-1496 describe: visual builder, typed edges, conditional branching, shared context, workflows-as-tools. Suggested pick order: migration 005 FIRST (unblocks persisted workflows) → list/get endpoints → 3-step chain → shared context → typed-edge validation → conditional branching → workflow-as-tool → visual builder SVG → save button → tests.

[ ] T4_new - db/migrations/005_workflows.sql - CREATE TABLE workflows (id SERIAL PRIMARY KEY, name TEXT NOT NULL, description TEXT, steps TEXT NOT NULL, author_name TEXT, author_email TEXT, run_count INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()); CREATE INDEX idx_workflows_author ON workflows(author_email).
[ ] T4_new - api/workflow.py - POST /api/workflows {name, description, steps, author_*} persists workflow row; GET /api/workflows lists workflows filterable by author_email; GET /api/workflows/:id returns full definition for load-into-builder.
[ ] T4_new - api/workflow.py - extend /api/workflows/run to accept 3+ steps (not just 2); execute serially; allow any step to reference any prior step via {{step1.output}}…{{stepN.output}}; verify substitution regex supports N>9 (escape numeric boundaries).
[ ] T4_new - api/workflow.py - shared context per SPEC line 1494: resolve {{stepN.output.field}} against parsed JSON output (when step's output_format='json'); fall back to raw string if parsing fails; errors surface with {step, field, reason} in response.
[ ] T4_new - api/workflow.py - typed-edge validation: before running, inspect each step's target tool.input_schema; reject with 400 if a {{stepN.output}} mapping targets a type-mismatched field (e.g., mapping into a number field when prior step output_format=text without explicit cast). Provide {violations:[{step, field, expected, got}]}.
[ ] T4_new - api/workflow.py - conditional branching per SPEC line 1493: workflow_steps items may include `condition: {field: "{{step1.output.risk_level}}", op: "eq", value: "high"}`; evaluate before invoking step; skipped steps return {skipped:true, reason}.
[ ] T4_new - api/workflow.py - workflow-as-tool: POST /api/workflows/:id/publish wraps workflow into a callable tool record (status='pending_review', tool_type='workflow'), input_schema derived from step 1's schema minus any fields satisfied by prior-step substitution. Dispatches normal agent pipeline.
[ ] T4_new - frontend/workflow.html + frontend/js/workflow.js - visual builder per SPEC line 1491: SVG canvas with draggable tool nodes (HTML absolute-positioned boxes); click-drag from node's output port to another's input field to create an edge (SVG <path> connecting endpoints); delete edges with right-click.
[ ] T4_new - frontend/js/workflow.js - "Save Workflow" button: POST /api/workflows with current canvas state serialized to {steps:[...], edges:[...]}; "My Workflows" panel lists saved workflows with Load + Delete + Publish-as-Tool buttons.
[ ] T4_new - tests/test_workflow.py - extend coverage: (a) 3-step chain with step3 referencing step1.output and step2.output; (b) typed-edge validation rejects type mismatch; (c) conditional branching skips step when condition false; (d) shared-context JSON field access works; (e) workflow-as-tool publish creates tools row with tool_type='workflow'.
