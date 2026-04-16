# T2 AGENT PIPELINE TASKS
## Rules
- Own ONLY: agents/ directory, scripts/run_pipeline.py, scripts/run_self_healer.py
- Claude Haiku for fast agents, Claude Sonnet for quality agents
- All agents return structured dicts, never raw strings
- Mark [x] done, update PROGRESS.md

## Tasks
[x] agents/__init__.py - empty package marker
[x] agents/base.py - BaseAgent class: __init__(name, model), _call_claude(system_prompt, user_message, max_tokens=2000) calls Anthropic API returns text, _parse_json(text) safely parses JSON stripping markdown fences, log(message) writes to logs/agents.log with timestamp.
[x] agents/classifier.py - ClassifierAgent(BaseAgent) using Haiku. Returns JSON: {output_type (deterministic/probabilistic/mixed), reliability_score 0-100, safety_score 0-100, data_sensitivity (public/internal/confidential/pii), complexity_score 0-100 higher=simpler, detected_category, reasoning, confidence 0-1}.
[x] agents/security_scanner.py - SecurityScannerAgent(BaseAgent) using Haiku. Scans for injection risks, PII exposure, hallucination amplifiers, scope creep, data exfil. Returns {security_score 0-100, flags:[{type, severity, detail, suggestion}], pii_risk bool, injection_risk bool, data_exfil_risk bool, recommendation}.
[x] agents/red_team.py - RedTeamAgent(BaseAgent) using Haiku. Generates 10 adversarial attack scenarios (injection, jailbreak, goal hijacking, PII extraction, empty inputs, overflow, special chars, multilingual, system prompt extraction, combined). Analyzes vulnerability. Returns {attacks_attempted 10, attacks_succeeded N, vulnerability_score 0-100 lower=safer, vulnerabilities:[{attack_type, severity, example_input, analysis}], hardening_suggestions:[str]}.
[x] agents/prompt_hardener.py - PromptHardenerAgent(BaseAgent) using Sonnet. Takes original_prompt + security_flags + red_team results. Adds guardrails. Returns {hardened_prompt str, changes:[{original_text, changed_to, reason}], hardening_summary str, change_count int}.
[x] agents/qa_tester.py - QATesterAgent(BaseAgent) using Haiku. Generates 3 test cases from input_schema (normal/edge/minimal). Runs each against hardened_prompt via actual Claude call. Evaluates format_correct, scope_maintained, hallucination_detected, useful, score 0-5. Returns {test_cases:[{inputs, output, evaluation}], qa_pass_rate 0-1, avg_score, issues:[str], recommendation}.
[x] agents/synthesizer.py - SynthesizerAgent(BaseAgent) using Sonnet. Reads all 5 prior agent outputs. Computes final governance scores. Determines trust_tier. Returns {overall_recommendation, confidence, trust_tier, governance_scores:{reliability,safety,data_sensitivity,complexity,verified}, summary str, required_changes:[str], reviewer_checklist:[str]}.
[x] agents/pipeline.py - run_pipeline(tool_id) function. Load tool from DB. Set status=agent_reviewing. Create agent_reviews record. Run: classifier first, then security_scanner + red_team in parallel via threading, then prompt_hardener, then qa_tester, then synthesizer. Update agent_reviews after each. Handle failures gracefully. Final: set status=pending_review, store hardened_prompt, compute trust_tier. Return dict.
[x] agents/trust_calculator.py - compute_trust_tier(reliability, safety, data_sensitivity, complexity, verified) returns str. TRUSTED: r>=80 AND s>=80 AND v>=75. VERIFIED: r>=60 AND s>=60 AND v>=50. RESTRICTED: data_sensitivity in (pii, confidential). CAUTION: r<60 OR s<60. UNVERIFIED: default.
[x] agents/self_healer.py - SelfHealerAgent. heal_underperforming_tools() queries tools where flag_count>=2 AND avg_rating<=3.0. For each: run prompt_hardener, run qa_tester on result, if qa_pass_rate>0.8 insert tool_version record increment version. Log to logs/self_healer.log. Return summary dict.
[x] scripts/run_pipeline.py - CLI: python3 scripts/run_pipeline.py --tool-id 123. Calls run_pipeline(). Prints JSON.
[x] scripts/run_self_healer.py - CLI for cron. Calls heal_underperforming_tools(). Logs. Exit 0.

## Cycle 2 Tasks (hardening + SPEC compliance)

UNBLOCKED: Three tasks below are zero-dependency — start immediately while waiting for T1 migration 002: (a) retry_with_backoff on line 25 (pure Python wrapper, no schema), (b) JSON repair fallback on line 28 (agents/base.py local change), (c) red_team structured suggestions on line 29 (in-memory contract change). The three that DO need T1 coordination (progress_pct line 26, token accounting line 27, stage_failed in line 24) are now unblocked: T1 has been tasked to add progress_pct/review_tokens_used/stage_failed columns to migration 002. Watch db/migrations/002_phase2_fields.sql for commit, then proceed. QA real-execution task line 30 depends only on api/executor.call_claude (already in T1 Cycle 1, confirmed live). Self-healer safety gate line 31 and batch CLI line 33 are zero-dep — pick up anytime.

[ ] agents/pipeline.py - wrap each agent.run() call in timeout (60s default, override via AGENT_TIMEOUT env). On timeout write partial row to agent_reviews with stage_failed=agent_name, continue to next stage if non-critical, else abort with status=review_failed.
[ ] agents/pipeline.py - add retry_with_backoff(3 attempts, 2s/4s/8s) for anthropic.RateLimitError, anthropic.APITimeoutError, anthropic.InternalServerError. Log each retry to logs/agents.log. Raise after 3rd.
[ ] agents/pipeline.py - write progress_pct (int) into agent_reviews after each stage: preflight=0, classifier=17, security+redteam=33, hardener=50, qa=67, synth=83, completed_at=100. Frontend polls this.
[ ] agents/base.py - token accounting: _call_claude returns (text, usage) where usage={input_tokens, output_tokens}. Aggregate per review into agent_reviews.review_duration_ms sibling column review_tokens_used (add via migration coord with T1).
[ ] agents/base.py - JSON repair fallback in _parse_json: on json.JSONDecodeError make one follow-up Claude call "Return only the JSON object, no prose" with same model; if still fails raise AgentJSONError with raw text.
[ ] agents/red_team.py - structure hardening_suggestions as [{vulnerability_type, patch_prompt_fragment, insert_location}] matching PromptHardenerAgent's input contract so hardener can apply surgically.
[ ] agents/qa_tester.py - replace placeholder output generation with real call via api.executor.call_claude(hardened_prompt, rendered_inputs, tool.model, tool.max_tokens, tool.temperature); record actual text in test_cases[i].output.
[ ] agents/self_healer.py - safety gate: compute char-level diff ratio between original and proposed prompt; if >40% change, skip version creation, write log entry tool_id + diff_ratio + "requires_human", flag tool for admin review instead.
[ ] agents/synthesizer.py - reviewer_checklist specialization: CAUTION/RESTRICTED tiers get extra mandatory items ("Verify on real data", "Confirm data_sensitivity classification", "Review all red team vulnerabilities individually"); TRUSTED gets minimal checklist.
[ ] scripts/run_pipeline_batch.py - CLI: --status (default pending_review), --force flag. SELECT tools where status=X; for each run_pipeline(id) serially, skip if agent_reviews.completed_at IS NOT NULL and not --force. Print progress table.
