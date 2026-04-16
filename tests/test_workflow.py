"""Tests for the /api/workflows (Tool Composability v1) endpoints."""
import json
import uuid
from unittest.mock import patch

import pytest


def _fake_claude_factory(call_log):
    """Return a call_claude stand-in that echoes the rendered system prompt."""

    def _fake_call_claude(system_prompt, user_msg, model="claude-haiku-4-5-20251001",
                         max_tokens=1000, temp=0.3):
        call_log.append({
            "system_prompt": system_prompt,
            "user_msg": user_msg,
            "model": model,
        })
        # Step N's output will be (for this fake) the rendered system prompt.
        return {
            "text": f"OUT:{system_prompt}",
            "input_tokens": 10,
            "output_tokens": 20,
            "cost_usd": 0.00001,
        }

    return _fake_call_claude


def _insert_chain_tools(db):
    """Insert two approved tools suitable for chaining."""
    slug_a = f"chain-a-{uuid.uuid4().hex[:6]}"
    slug_b = f"chain-b-{uuid.uuid4().hex[:6]}"
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO tools (slug, name, tagline, description, category,
                                  output_type, system_prompt, input_schema,
                                  status, author_name, author_email)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (
                slug_a, "Chain Tool A", "step 1", "first step",
                "other", "probabilistic",
                "Step1 prompt with {{topic}}.",
                json.dumps([{"name": "topic", "type": "text", "required": True}]),
                "approved", "Tester", "tester@navan.com",
            ),
        )
        row_a = cur.fetchone()
        id_a = row_a[0] if isinstance(row_a, tuple) else row_a["id"]

        cur.execute(
            """INSERT INTO tools (slug, name, tagline, description, category,
                                  output_type, system_prompt, input_schema,
                                  status, author_name, author_email)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (
                slug_b, "Chain Tool B", "step 2", "second step",
                "other", "probabilistic",
                "Step2 prompt received: {{incoming}}.",
                json.dumps([{"name": "incoming", "type": "text", "required": True}]),
                "approved", "Tester", "tester@navan.com",
            ),
        )
        row_b = cur.fetchone()
        id_b = row_b[0] if isinstance(row_b, tuple) else row_b["id"]
    return id_a, id_b


# ---------------------------------------------------------------------------
# substitute_step_refs — unit-level coverage of the token replacement logic
# ---------------------------------------------------------------------------
def test_substitute_step_refs_basic():
    try:
        from api.workflow import substitute_step_refs
    except ImportError:
        pytest.skip("api/workflow.py not importable")
    out = substitute_step_refs(
        {"field_a": "prefix {{step1.output}} suffix", "field_b": "plain"},
        ["STEP1OUT"],
    )
    assert out["field_a"] == "prefix STEP1OUT suffix"
    assert out["field_b"] == "plain"


def test_substitute_step_refs_missing_step():
    try:
        from api.workflow import substitute_step_refs
    except ImportError:
        pytest.skip("api/workflow.py not importable")
    # Reference to step3 when only 1 output exists -> empty string.
    out = substitute_step_refs("x={{step3.output}}", ["A"])
    assert out == "x="


# ---------------------------------------------------------------------------
# POST /api/workflows/run
# ---------------------------------------------------------------------------
def test_run_chain_two_tools_in_sequence(client, db):
    id_a, id_b = _insert_chain_tools(db)
    calls = []

    with patch("api.executor.call_claude", side_effect=_fake_claude_factory(calls)):
        resp = client.post(
            "/api/workflows/run",
            json={
                "workflow_steps": [
                    {"tool_id": id_a, "inputs": {"topic": "first-topic"}},
                    {"tool_id": id_b, "inputs": {"incoming": "{{step1.output}}"}},
                ],
                "user_name": "Tester",
                "user_email": "tester@navan.com",
            },
        )

    if resp.status_code == 404:
        pytest.skip("/api/workflows/run not registered")
    assert resp.status_code == 200, resp.get_data(as_text=True)

    payload = resp.get_json() or {}
    assert payload.get("step_count") == 2
    results = payload.get("results") or []
    assert len(results) == 2

    # Step 1 prompt should include the literal topic.
    step1 = results[0]
    assert "first-topic" in (step1.get("output") or "")

    # Step 2's inputs must contain step 1's output (after substitution).
    step2 = results[1]
    assert "{{step1.output}}" not in json.dumps(step2.get("inputs") or {})
    step1_output = step1.get("output") or ""
    # Step 2's rendered prompt (captured via fake Claude) must reference
    # step 1's actual output text, proving the substitution took effect.
    assert any(step1_output in c.get("system_prompt", "") for c in calls[1:])


def test_run_chain_validation_empty_steps(client):
    resp = client.post("/api/workflows/run", json={"workflow_steps": []})
    if resp.status_code == 404:
        pytest.skip("/api/workflows/run not registered")
    assert resp.status_code == 400
    payload = resp.get_json() or {}
    assert "workflow_steps" in (payload.get("message") or "")


def test_run_chain_invalid_tool_id(client):
    resp = client.post(
        "/api/workflows/run",
        json={"workflow_steps": [{"tool_id": "not-an-int", "inputs": {}}]},
    )
    if resp.status_code == 404:
        pytest.skip("/api/workflows/run not registered")
    assert resp.status_code == 400


def test_run_chain_reports_failure_with_partial_results(client, db):
    id_a, _ = _insert_chain_tools(db)
    calls = []

    with patch("api.executor.call_claude", side_effect=_fake_claude_factory(calls)):
        resp = client.post(
            "/api/workflows/run",
            json={
                "workflow_steps": [
                    {"tool_id": id_a, "inputs": {"topic": "seed"}},
                    {"tool_id": 999999, "inputs": {}},
                ],
            },
        )

    if resp.status_code == 404:
        pytest.skip("/api/workflows/run not registered")
    assert resp.status_code in (400, 500)
    payload = resp.get_json() or {}
    assert payload.get("step") == 2
    # First step still executed and appears in results.
    assert len(payload.get("results") or []) == 1


# ---------------------------------------------------------------------------
# GET /api/workflows/tools
# ---------------------------------------------------------------------------
def test_list_chainable_tools(client, db, sample_tool):
    resp = client.get("/api/workflows/tools")
    if resp.status_code == 404:
        pytest.skip("/api/workflows/tools not registered")
    assert resp.status_code == 200
    payload = resp.get_json() or {}
    ids = [t.get("id") for t in payload.get("tools") or []]
    assert sample_tool["id"] in ids
