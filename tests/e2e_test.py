"""
End-to-end smoke test covering the happy-path lifecycle of a tool:

    submit  ->  pipeline (mocked)  ->  approve  ->  deploy (mocked)  ->
    run (mocked Claude)  ->  rate  ->  avg_rating updated
"""
import json
from unittest.mock import patch

import pytest


def test_end_to_end_tool_lifecycle(client, db, admin_headers):
    # 1. Submit — pipeline thread mocked out.
    body = {
        "name": "E2E Tool",
        "tagline": "tests the full lifecycle",
        "description": "Used by the e2e test",
        "category": "other",
        "output_type": "probabilistic",
        "system_prompt": "Respond to {{query}}",
        "input_schema": [{"name": "query", "type": "text", "required": True}],
        "author_name": "Tester",
        "author_email": "tester@navan.com",
    }
    with patch("api.server._launch_pipeline", return_value=None):
        submit_resp = client.post("/api/tools/submit", json=body)
    if submit_resp.status_code in (404, 405):
        pytest.skip("POST /api/tools/submit not implemented yet (T1)")
    assert submit_resp.status_code == 201
    submit_payload = submit_resp.get_json() or {}
    tool_id = submit_payload.get("id") or submit_payload.get("tool", {}).get("id")
    assert tool_id is not None

    # 2. Simulate the pipeline by writing a completed agent_reviews row and
    #    putting the tool into 'pending_review' status.
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO agent_reviews
                 (tool_id, classifier_output, security_scan_output,
                  red_team_output, hardener_output, qa_output, review_summary,
                  agent_recommendation, agent_confidence, hardened_prompt)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                tool_id,
                json.dumps({"output_type": "probabilistic", "reliability_score": 75}),
                json.dumps({"security_score": 90, "flags": []}),
                json.dumps({"attacks_attempted": 10, "attacks_succeeded": 0}),
                json.dumps({"hardened_prompt": "HARDENED {{query}}"}),
                json.dumps({"qa_pass_rate": 0.95}),
                "Looks good",
                "approve",
                0.95,
                "HARDENED {{query}}",
            ),
        )

    # 3. Approve with deploy mocked.
    with patch("api.admin._launch_deploy", return_value=None):
        approve_resp = client.post(
            f"/api/admin/tools/{tool_id}/approve",
            headers=admin_headers,
            json={"reviewer": "Nick"},
        )
    if approve_resp.status_code in (404, 405):
        pytest.skip("POST /api/admin/tools/:id/approve not implemented yet (T4)")
    assert approve_resp.status_code == 200

    with db.cursor() as cur:
        cur.execute("SELECT status FROM tools WHERE id = %s", (tool_id,))
        row = cur.fetchone()
        status = row[0] if isinstance(row, tuple) else row["status"]
        assert status == "approved"

    # 4. Run with mocked Claude
    mock_result = {
        "text": "mocked-e2e-output",
        "input_tokens": 5,
        "output_tokens": 10,
        "cost_usd": 0.0001,
    }
    with patch("api.executor.call_claude", return_value=mock_result):
        run_resp = client.post(
            f"/api/tools/{tool_id}/run",
            json={
                "inputs": {"query": "hello"},
                "user_name": "Tester",
                "user_email": "tester@navan.com",
            },
        )
    if run_resp.status_code in (404, 405):
        pytest.skip("POST /api/tools/:id/run not implemented yet (T1)")
    assert run_resp.status_code == 200
    run_payload = run_resp.get_json() or {}
    run_id = run_payload.get("run_id") or run_payload.get("id")
    assert run_id is not None

    # 5. Verify a run row was logged.
    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM runs WHERE tool_id = %s", (tool_id,))
        row = cur.fetchone()
        cnt = row[0] if isinstance(row, tuple) else list(row.values())[0]
        assert cnt >= 1

    # 6. Rate the run.
    rate_resp = client.post(
        f"/api/runs/{run_id}/rate", json={"rating": 5, "note": "great"},
    )
    if rate_resp.status_code in (404, 405):
        pytest.skip("POST /api/runs/:id/rate not implemented yet (T1)")
    assert rate_resp.status_code == 200

    # 7. Verify avg_rating was updated.
    with db.cursor() as cur:
        cur.execute("SELECT avg_rating FROM tools WHERE id = %s", (tool_id,))
        row = cur.fetchone()
        avg = row[0] if isinstance(row, tuple) else row["avg_rating"]
        assert avg is not None
        assert float(avg) >= 1.0
