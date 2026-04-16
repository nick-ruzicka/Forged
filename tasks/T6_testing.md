# T6 TESTING TASKS
## Rules
- Own ONLY: tests/ directory
- Use pytest, mock all Claude API calls with unittest.mock.patch
- Start after T1 is 50% done
- Mark [x] done, update PROGRESS.md

## Tasks
[x] tests/conftest.py - fixtures: app() Flask test app, client() test client, db() creates tables tears down after, sample_tool() approved tool, sample_pending_tool() pending tool, sample_run() run for sample_tool, admin_headers() X-Admin-Key dict.
[x] tests/test_health.py - GET /api/health returns 200 with status/version/timestamp.
[x] tests/test_tools_api.py - GET /api/tools: list, category filter, search, pagination, approved only. GET /:id: 200 approved 404 missing. POST /submit: valid=201, missing required=400, duplicate slug gets suffix. POST /fork: fork_of set.
[x] tests/test_executor.py - interpolate_prompt: substitution, missing var raises. sanitize_inputs: valid passes, missing required raises, PII logged. call_claude: mock client verify params. run_tool: mock Claude, run logged, run_count incremented.
[x] tests/test_runs_api.py - POST run: valid returns output, invalid tool=404. POST rate: valid updates avg_rating, invalid rating=400. POST flag: flags, increments, third sets needs_review.
[x] tests/test_skills_api.py - GET skills, POST skills valid/invalid, upvote increments, copy increments.
[x] tests/test_admin_api.py - all admin routes 401 without key. GET queue returns pending. POST approve sets approved calls deploy (mocked). POST reject sets rejected.
[x] tests/test_agents.py - each agent with mock Claude. Verify output structure. Invalid JSON handled.
[x] tests/test_pipeline.py - run_pipeline with mocked Claude. agent_reviews created, all fields populated, status=pending_review.
[x] tests/e2e_test.py - submit tool, mock pipeline, approve, verify deployed=true, run tool, verify run logged, rate, verify avg_rating updated.

## Cycle 2 Tasks (coverage expansion)

UNBLOCKED: SIX of 10 Cycle 2 tasks below are zero-dependency — start immediately. Zero-dep: test_deploy (line 21, mocks everything), test_trust_calculator (22, pure function), test_self_healer (23, mocks hardener+qa), test_slack_notify (28, mocks requests.post), test_instructions_generation (27, mocks Claude), test_pipeline_retry (30, mocks anthropic exceptions). FOUR need T1 Cycle 2 endpoints to exist first: test_versions_api (26 → GET /api/tools/:id/versions), test_rate_limit (25 → redis rate limiter), test_admin_bulk (29 → POST /admin/tools/bulk-approve). test_dlp (24) is ALREADY written by T3_NEW (21 passing tests) — mark it [x] after verifying with `venv/bin/python3 -m pytest tests/test_dlp.py -v`. Suggested pick order: test_trust_calculator FIRST (pure-function smoke) → test_deploy → test_self_healer → test_slack_notify → test_instructions_generation → test_pipeline_retry → then wait on T1 migration 002 + endpoints for the other three. Stub assertion skeletons for the T1-blocked tests today using `pytest.importorskip('api.server')` guards so the test files exist and run green until endpoints land.

[ ] tests/test_deploy.py - deploy_tool(): mock generate_instructions_content, send_slack_announcement, weasyprint; assert tool row updated deployed=true, access_token is UUID format, endpoint_url = FORGE_HOST+/tools/+slug, instructions_url set, returns shareable_url.
[ ] tests/test_trust_calculator.py - compute_trust_tier exhaustive matrix: TRUSTED (r=80,s=80,v=75), VERIFIED (r=60,s=60,v=50), RESTRICTED overrides when data_sensitivity in [pii,confidential], CAUTION when r<60 OR s<60 (and not restricted), UNVERIFIED default. Parametrize with pytest.mark.parametrize.
[ ] tests/test_self_healer.py - heal_underperforming_tools: seed tool with flag_count=3, avg_rating=2.5, status=approved. Mock PromptHardenerAgent + QATesterAgent. If qa_pass_rate=0.9 assert new tool_versions row with created_by='self-healer'. If 0.5 assert no row created.
[ ] tests/test_dlp.py - sanitize_inputs: HTML tags stripped, email/phone/SSN/credit-card regex each trigger PII log entry, dlp.log contents verified to contain pii_type but NOT raw value, required field missing raises ValueError with field name.
[ ] tests/test_rate_limit.py - loop POST /api/tools/1/run 30 times from same X-Forwarded-For = 200. 31st = 429 with retry_after header > 0. Second IP = 200. Reset window (patch time) = 200 again.
[ ] tests/test_versions_api.py - GET /api/tools/:id/versions: tool with 3 versions returns ordered DESC, fields {version, change_summary, created_by, created_at}; tool with 0 versions returns []; nonexistent tool returns 404.
[ ] tests/test_instructions_generation.py - generate_instructions_content: mock Claude to return sample Markdown. Assert output contains tool.name, trust tier string, every input_schema field label, author_name, "#forge-help" contact line.
[ ] tests/test_slack_notify.py - send_slack_announcement: no SLACK_WEBHOOK_URL returns False, no HTTP call made. Mock requests.post returning 200 returns True. 500 response returns False, logs error. Malformed URL returns False gracefully.
[ ] tests/test_admin_bulk.py - POST /api/admin/tools/bulk-approve body={ids:[1,2,3]}: all 3 transition to approved, deploy_tool called 3x (mocked), response {approved:[1,2,3], failed:[]}. Include one invalid id: partial success with failed entry.
[ ] tests/test_pipeline_retry.py - run_pipeline with mock Claude raising RateLimitError once then succeeding: agent_reviews.completed_at IS NOT NULL, status=pending_review. Three consecutive failures: status=review_failed, agent_reviews row has stage_failed populated.
